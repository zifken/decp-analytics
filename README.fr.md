# decp-analytics

Prevision d'echeance et couche d'analyse sur les donnees ouvertes de la
commande publique francaise (DECP). Construit a partir des [fichiers
consolides annuels DECP](https://www.data.gouv.fr/datasets/donnees-essentielles-de-la-commande-publique-fichiers-consolides)
(Licence Ouverte / Etalab 2.0, aucune donnee personnelle).

**Ce que ca fait**

- Reconstruit le jeu de donnees complet depuis les consolides annuels
  (2019-2026) : 1 355 661 marchés exploitables apres ecart des enregistrements
  remplaces.
- Estime l'echeance comme `dateNotification + dureeMois` et produit la
  fenetre de re-tender 6-12 mois : 55 957 marchés arrivant a echeance dans
  les 12 mois, filtrables par famille CPV, departement et acheteur.
- Construit `data/marches.parquet|.csv` depuis les deltas quotidiens (pour le
  dashboard) et livre un dashboard Streamlit (filtres CPV / departement /
  periode, KPIs, benchmark de prix, vues acheteur et fournisseur).
- Publie un echantillon public gratuit de 60 lignes du fichier d'echeances
  (`samples/sample-expirations.csv`).

## Chiffres du pipeline

- Remplissage 99,7% ou mieux sur chaque champ utilise (mesure sur les deltas
  quotidiens ; voir le depot compagnon `decp-digest` pour la mesure).
- Environ 750 nouveaux avis d'attribution ingérés par semaine (fichiers delta
  quotidiens, dedoublonnes sur `(acheteur.id, id)`).
- 1,36 M de marchés 2019-2026 depuis les consolides ; la reconstruction
  complete est la seule etape lourde et tient dans un budget < 2 h/semaine.

## Utilisation

```sh
./refresh.sh            # telecharge le fichier de l'annee, reconstruit echeances, rapports, echantillon
python3 expiry_report.py --cpv 48 72 --dept 75 --acheteur SIRET   # rapport filtre
streamlit run app.py --server.port 8501 --server.headless true    # dashboard
python3 -m pytest test_expiry.py            # tests unitaires
python3 -m pytest test_expiry.py -m slow    # + invariants sur le dataset construit
```

## Qualite des donnees (documentee, pas masquee)

- Les marchés sans `dureeMois` exploitable, ou avec duree <= 0 / > 360 mois,
  sont ecartes (voir `data/build_stats.json`).
- 38,8% des marchés sont des accords-cadres ; leur `montant` est un MAXIMUM
  d'accord-cadre, toujours etiquete comme tel. Les acheteurs sont classes par
  NOMBRE de marchés arrivant a echeance, jamais par montants d'accord-cadre.
- ~1,2% des identifiants gagnants sont anonymises (ids 14 chiffres non-SIRET)
  - signales, jamais affiches comme noms de societes.
- Aucun champ « prolongation » n'existe dans les DECP : les prolongements
  tacites sont invisibles et une echeance est un signal de fenetre de
  re-tender, pas une fin de contrat garantie.

Depot compagnon : `decp-digest` (digest hebdomadaire des avis d'attribution,
Python stdlib).
