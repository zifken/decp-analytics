"""DECP Analytics — dashboard v1 (privé, démo interne).

Marchés publics français : attributions, prix, concurrence.
Source : API DECP (data.gouv.fr), deltas quotidiens via decp-digest.
"""
from collections import Counter
from collections import defaultdict
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="DECP Analytics", page_icon="chart_with_upwards_trend", layout="wide")

HERE = Path(__file__).resolve().parent


@st.cache_data
def load() -> pd.DataFrame:
    pq = HERE / "data" / "marches.parquet"
    csv = HERE / "data" / "marches.csv"
    return pd.read_parquet(pq) if pq.exists() else pd.read_csv(csv, dtype={"departement": str})


df = load()
df["date_notification"] = pd.to_datetime(df["date_notification"], errors="coerce")
df = df.dropna(subset=["date_notification"])

st.title("DECP Analytics")
st.caption("Qui achète quoi, à quel prix, à qui — marché public français. "
           "Source : API DECP (deltas quotidiens). v1 démo.")

# ---- filtres ----
c1, c2, c3 = st.columns([2, 2, 3])
with c1:
    fams = ["(toutes)"] + sorted(df["cpv_div"].dropna().unique())
    fam = st.selectbox("Famille d'achat", fams)
with c2:
    deps = ["(tous)"] + sorted(df["departement"].dropna().astype(str).unique())
    dep = st.selectbox("Département", deps)
with c3:
    dates = df["date_notification"].dt.date
    today = pd.Timestamp.now().date()
    # sanity: DECP delta feeds carry a few wrong/future dates — exclude them
    sane = dates[(dates >= today - pd.Timedelta(days=1095))
                 & (dates <= today)]
    dmin, dmax = sane.min(), sane.max()
    r = st.date_input("Période de notification", (dmin, dmax),
                      min_value=dmin, max_value=dmax)

sub = df.copy()
if fam != "(toutes)":
    sub = sub[sub["cpv_div"] == fam]
if dep != "(tous)":
    sub = sub[sub["departement"].astype(str) == dep]
if isinstance(r, tuple) and len(r) == 2:
    sub = sub[(sub["date_notification"].dt.date >= r[0])
              & (sub["date_notification"].dt.date <= r[1])]

# ---- KPIs ----
k1, k2, k3, k4 = st.columns(4)
k1.metric("Marchés attribués", f"{len(sub):,}")
tot = sub["montant"].sum()
k2.metric("Volume connu", f"{tot/1e6:,.1f} M€")
known = sub["montant"].notna().mean()
k3.metric("Montant publié", f"{known:.0%}")
med = sub["montant"].median()
k4.metric("Montant médian", "n/d" if pd.isna(med) else f"{med/1e3:,.0f} k€")

st.divider()

# ---- benchmark de prix par famille ----
st.subheader("Benchmark de prix par famille d'achat")
ben = (sub.dropna(subset=["montant"]).groupby("cpv_div")["montant"]
       .agg(marches="count", mediane="median", p25=lambda s: s.quantile(.25),
            p75=lambda s: s.quantile(.75), total="sum")
       .sort_values("total", ascending=False).head(15))
ben["mediane"] = (ben["mediane"] / 1e3).round(0)
ben["p25"] = (ben["p25"] / 1e3).round(0)
ben["p75"] = (ben["p75"] / 1e3).round(0)
ben["total"] = (ben["total"] / 1e6).round(1)
ben = ben.rename(columns={"mediane": "médiane (k€)", "p25": "P25 (k€)",
                          "p75": "P75 (k€)", "total": "volume (M€)"})
ben = ben.rename_axis("Famille")
st.dataframe(ben, use_container_width=True)

cL, cR = st.columns(2)
with cL:
    st.subheader("Concurrence : attributaires les plus fréquents")
    win = Counter()
    for _, row in sub[["titulaires_siret", "titulaire_nom"]].dropna(
            subset=["titulaires_siret"]).iterrows():
        sirs = str(row["titulaires_siret"]).split("; ")
        noms = str(row.get("titulaire_nom") or "").split("; ") \
            if pd.notna(row.get("titulaire_nom")) else []
        for i, s in enumerate(sirs):
            if s:
                win[noms[i] if i < len(noms) and noms[i] else s] += 1
    if win:
        w = pd.DataFrame(win.most_common(10), columns=["Attributaire", "marchés gagnés"])
        w = w.set_index("Attributaire")
        st.bar_chart(w)
        st.dataframe(w, use_container_width=True)
    else:
        st.info("Aucun attributaire sur la sélection.")

with cR:
    st.subheader("Acheteurs les plus actifs")
    sub_a = sub.copy()
    sub_a["acheteur_nom"] = (sub_a["acheteur_nom"]
                             .fillna(sub_a["acheteur_siret"].astype(str)))
    by_ach = (sub_a.groupby("acheteur_nom")["montant"]
              .agg(nb="count", volume="sum").sort_values("volume", ascending=False).head(10))
    by_ach["volume"] = (by_ach["volume"] / 1e6).round(1)
    by_ach = by_ach.rename(columns={"nb": "marchés", "volume": "volume (M€)"})
    by_ach = by_ach.rename_axis("Acheteur")
    st.dataframe(by_ach, use_container_width=True)

st.subheader("Attributions par jour")
per_day = sub.set_index("date_notification").resample("D").size()
st.line_chart(per_day)

st.divider()
st.caption("v1 — échantillon gratuit sur demande · API 9-29 €/mois · datasets sectoriels 19-79 €")
