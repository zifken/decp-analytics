# decp-analytics

Expiry-forecast and analysis layer over French public-procurement (DECP)
open data. Built from the [annual consolidated DECP files](https://www.data.gouv.fr/datasets/donnees-essentielles-de-la-commande-publique-fichiers-consolides)
(Licence Ouverte / Etalab 2.0, no personal data).

**What it does**

- Rebuilds the full dataset from the consolidated annual files (2019-2026):
  1,355,661 usable contracts after removing superseded records.
- Estimates contract expiry as `dateNotification + dureeMois` and produces
  the 6-12 month re-tender window: 55,957 contracts expiring within 12
  months, filterable by CPV family, departement and buyer.
- Builds `data/marches.parquet|.csv` from daily award deltas (for the
  dashboard) and ships a Streamlit dashboard (CPV / departement / period
  filters, KPIs, price benchmark, buyer and supplier views).
- Publishes a free 60-row public sample of the expiry output
  (`samples/sample-expirations.csv`).

## Pipeline stats

- 99.7%+ field fill on every field the pipeline uses (measured on the daily
  delta files; see the companion repo `decp-digest` for the measurement).
- ~750 new award notices ingested per week (daily delta files, deduped on
  `(acheteur.id, id)`).
- 1.36M contracts 2019-2026 from the consolidated files; full rebuild is
  the only heavy step and fits a <2 h/week budget.

## Run

```sh
./refresh.sh            # download current-year file, rebuild expiries, reports, sample
python3 expiry_report.py --cpv 48 72 --dept 75 --acheteur SIRET   # filtered report
streamlit run app.py --server.port 8501 --server.headless true    # dashboard
python3 -m pytest test_expiry.py            # unit tests
python3 -m pytest test_expiry.py -m slow    # + built-dataset invariants
```

## Data quality notes (documented, not hidden)

- Contracts without usable `dureeMois`, or with duration <= 0 / > 360
  months, are excluded (see `data/build_stats.json`).
- 38.8% of contracts are accords-cadres; their `montant` is a framework
  MAXIMUM, always labelled as such. Buyers are ranked by number of expiring
  contracts, never by framework amounts.
- ~1.2% of winner ids are anonymized (non-SIRET 14-digit ids) - flagged,
  never rendered as company names.
- There is no "extension" field in DECP: tacit renewals are invisible and an
  expiry is a re-tender-window signal, not a guaranteed contract end.

Companion repo: `decp-digest` (weekly award-notices digest, Python stdlib).
Version francaise : [README.fr.md](README.fr.md).
