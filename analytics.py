#!/usr/bin/env python3
"""Build the DECP analytics dataset from the decp-digest raw deltas.

Reads ~/src/decp-digest/data/raw/decp-*.json, dedupes by marche id, keeps
awards (dateNotification present), and emits data/marches.parquet (or .csv)
with one row per marche: montant, CPV family, departement, buyer SIRET,
titulaires. Stdlib + pandas only, deterministic.
"""
import json
import sys
from pathlib import Path

import pandas as pd

from enrich import enrich as enrich_names

DIGEST_RAW = Path.home() / "src" / "decp-digest" / "data" / "raw"
HERE = Path(__file__).resolve().parent
OUT = HERE / "data"
OUT.mkdir(exist_ok=True)

CPV_DIV = {
    "03": "Produits agricoles", "09": "Carburants", "14": "Mines/minéraux",
    "15": "Alimentation", "16": "Vêtements/cuir", "18": "Papier/impression",
    "19": "Produits chimiques", "22": "Textiles", "24": "Produits divers",
    "30": "Informatique (matériel)", "31": "Électronique/optique",
    "32": "Équipements électriques", "33": "Équipements médicaux/précision",
    "34": "Transports (matériel)", "35": "Sécurité/défense",
    "37": "Sport/loisirs", "38": "Instruments de mesure",
    "39": "Mobilier", "41": "Eau", "42": "Travaux (génie civil)",
    "43": "Bâtiment (travaux)", "44": "Matériaux construction",
    "45": "Travaux de construction", "48": "Logiciels/services IT",
    "50": "Réparation/maintenance", "51": "Installation",
    "55": "Hôtellerie/restauration", "60": "Services de transport",
    "63": "Services logistiques", "64": "Services postaux",
    "66": "Services financiers", "71": "Services d'ingénierie/études",
    "72": "Services IT (conseil, dev)", "73": "R&D",
    "75": "Services publics/administratifs", "79": "Services aux entreprises",
    "80": "Enseignement/formation", "85": "Santé/social",
    "90": "Environnement/propreté", "92": "Services juridiques",
    "98": "Autres services",
}


def load_marches() -> dict:
    marches = {}
    for f in sorted(DIGEST_RAW.glob("decp-*.json")):
        try:
            d = json.loads(f.read_text())
        except Exception as e:
            print(f"WARN skip {f.name}: {e}", file=sys.stderr)
            continue
        for m in d.get("marches", {}).get("marche", []):
            if m.get("id"):
                marches[m["id"]] = m
    return marches


def titulaires_str(m):
    names = []
    for t in (m.get("titulaires") or []):
        tid = (t.get("titulaire") or {}).get("id")
        if tid:
            names.append(tid)
    return "; ".join(names)


def build() -> pd.DataFrame:
    marches = load_marches()
    rows = []
    for m in marches.values():
        if not m.get("dateNotification"):
            continue  # analytics on awarded marches only
        dep = (m.get("lieuExecution") or {}).get("code")
        cpv = m.get("codeCPV") or ""
        rows.append({
            "id": m["id"],
            "objet": m.get("objet"),
            "date_notification": m.get("dateNotification"),
            "montant": m.get("montant"),
            "cpv": cpv,
            "cpv_div": CPV_DIV.get(cpv[:2], cpv[:2] + "?"),
            "departement": dep,
            "acheteur_siret": (m.get("acheteur") or {}).get("id"),
            "titulaires_siret": titulaires_str(m),
            "duree_mois": m.get("dureeEnMois"),
            "forme_prix": (m.get("typesPrix") or {}).get("typePrix") or "",
            "nature": m.get("nature"),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        sys.exit("no data")
    # enrich all titulaire + acheteur SIRETs with company names (cached on disk)
    siren = set()
    for t in df["titulaires_siret"].dropna():
        siren.update(s for s in str(t).split("; ") if s)
    siren.update(df["acheteur_siret"].dropna().astype(str))
    names = enrich_names(siren)
    df["titulaire_nom"] = df["titulaires_siret"].map(
        lambda ts: "; ".join(filter(None, (names.get(s) or s
                                           for s in str(ts).split("; ")))) or None
        if pd.notna(ts) else None)
    df["acheteur_nom"] = df["acheteur_siret"].map(
        lambda s: (names.get(str(s)) or str(s)) if pd.notna(s) else None)
    return df


if __name__ == "__main__":
    df = build()
    csv = OUT / "marches.csv"
    df.to_csv(csv, index=False)
    try:
        df.to_parquet(OUT / "marches.parquet", index=False)
    except Exception:
        pass  # parquet engine optional
    print(f"{len(df)} marchés attribués -> {csv}")
    print(df["montant"].describe().to_string())
