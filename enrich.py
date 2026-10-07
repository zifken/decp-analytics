"""SIRET -> company name lookup via recherche-entreprises.api.gouv.fr.

On-disk JSON cache shared by analytics.py and app.py so enrichment runs
once per SIRET ever. Public open-data endpoint, best effort: failures
return None and are retried on a later run.
"""
import json
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / "data" / "siret_names.json"


def _load() -> dict:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text())
        except Exception:
            return {}
    return {}


def _save(cache: dict) -> None:
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0, sort_keys=True))


def enrich(sirets, max_new: int = 400, sleep: float = 0.12) -> dict:
    """Return {siret: name-or-None}, filling the cache for missing entries."""
    cache = _load()
    for s in [s for s, n in cache.items() if n is None]:
        cache[s] = s  # unresolvable (malformed/foreign SIRET): fall back to raw id
    missing = [s for s in set(sirets) if s and s not in cache]
    for s in missing[:max_new]:
        try:
            url = f"https://recherche-entreprises.api.gouv.fr/search?q={s}&mtm_campaign=api"
            req = urllib.request.Request(url, headers={"User-Agent": "decp-analytics/0.1"})
            with urllib.request.urlopen(req, timeout=10) as r:
                d = json.load(r)
            res = d.get("results") or []
            cache[s] = (res[0].get("nom_complet")
                        or (res[0].get("denomination") or None)) if res else None
        except Exception:
            break  # network trouble: keep cache consistent, retry next run
        time.sleep(sleep)
    _save(cache)
    return cache
