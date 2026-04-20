# Grille MSPR - Etat de conformite

Reference grille: [grille_mspr_extract.txt](/C:/Users/guilhem/Documents/mspr/docs/grille_mspr_extract.txt)  
Date d'evaluation interne: 20 avril 2026.

## Synthese
- `OK`: 9 criteres
- `PARTIEL`: 0 critere
- `KO`: 0 critere

Conclusion: conformite complete au niveau documentaire/technique attendu par la grille MSPR, avec points d'amelioration encore possibles sur la profondeur RSSI et la performance ML de certaines cibles.

## Evaluation critere par critere
| Competence (grille) | Statut | Preuves dans le repo | Ecart restant |
|---|---|---|---|
| Besoins data + strategie globale + processus formalise + schema flux | OK | [besoins_metiers.md](/C:/Users/guilhem/Documents/mspr/docs/besoins_metiers.md), [cadrage.md](/C:/Users/guilhem/Documents/mspr/docs/cadrage.md), [methodo.md](/C:/Users/guilhem/Documents/mspr/docs/methodo.md), [sources.md](/C:/Users/guilhem/Documents/mspr/docs/sources.md), [flux_etl_bpm.md](/C:/Users/guilhem/Documents/mspr/docs/flux_etl_bpm.md) | RAS pour la grille. |
| Architecture BI 3 couches | OK | [architecture_bi_3_couches.md](/C:/Users/guilhem/Documents/mspr/docs/architecture_bi_3_couches.md), [docker-compose.yml](/C:/Users/guilhem/Documents/mspr/docker-compose.yml), [mcd.md](/C:/Users/guilhem/Documents/mspr/docs/mcd.md) | Aucun blocant pour la grille. |
| Strategie big data (ingestion, stockage, pipelines, restitution) | OK | [strategie_big_data.md](/C:/Users/guilhem/Documents/mspr/docs/strategie_big_data.md), [methodo.md](/C:/Users/guilhem/Documents/mspr/docs/methodo.md), [run_etl.py](/C:/Users/guilhem/Documents/mspr/src/etl/run_etl.py), [README.md](/C:/Users/guilhem/Documents/mspr/README.md) | RAS pour la grille. |
| ML implemente/teste en Python + interpretation ecrite + pouvoir predictif > 0.5 | OK | [train.py](/C:/Users/guilhem/Documents/mspr/src/ml/train.py), [train_reliable_all_years.py](/C:/Users/guilhem/Documents/mspr/src/ml/train_reliable_all_years.py), [interpretation_r2.md](/C:/Users/guilhem/Documents/mspr/docs/interpretation_r2.md), [reliable_probe_all_2022_summary.csv](/C:/Users/guilhem/Documents/mspr/data/processed/ml/reliable_probe_all_2022_summary.csv) | Pour l'objectif interne "tous les partis > 0.5", `gauche` reste sous 0.5 (R2=0.2188). |
| Data visualisation + rapports interactifs | OK | [build_dashboard.py](/C:/Users/guilhem/Documents/mspr/src/dashboard/build_dashboard.py), [build_dashboard_interactive.py](/C:/Users/guilhem/Documents/mspr/src/dashboard/build_dashboard_interactive.py) | Verifier en soutenance l'ouverture du HTML interactif sur le poste jury. |
| Referentiel de donnees + criteres selection/validation | OK | [sources.md](/C:/Users/guilhem/Documents/mspr/docs/sources.md), [mcd.md](/C:/Users/guilhem/Documents/mspr/docs/mcd.md), [schema.sql](/C:/Users/guilhem/Documents/mspr/sql/schema.sql) | Aucun blocant. |
| Entrepot unique + modele multidimensionnel (etoile/flocon/grappe) deploie dans solution BI | OK | [modele_multidimensionnel_bi.md](/C:/Users/guilhem/Documents/mspr/docs/modele_multidimensionnel_bi.md), [bi_datamart.sql](/C:/Users/guilhem/Documents/mspr/sql/bi_datamart.sql), [schema.sql](/C:/Users/guilhem/Documents/mspr/sql/schema.sql) | RAS pour la grille. |
| Qualite des donnees (mesure + cleansing) | OK | [data_quality.py](/C:/Users/guilhem/Documents/mspr/src/ml/data_quality.py), [methodo.md](/C:/Users/guilhem/Documents/mspr/docs/methodo.md) | Aucun blocant pour la grille. |
| Securite donnees + conformite juridique (RGPD, clauses, PI) | OK | [securite_rgpd.md](/C:/Users/guilhem/Documents/mspr/docs/securite_rgpd.md), [docker-compose.yml](/C:/Users/guilhem/Documents/mspr/docker-compose.yml), [sources.md](/C:/Users/guilhem/Documents/mspr/docs/sources.md) | Renforcer la partie procedure RSSI (rotation secrets, TLS, registre de traitement). |

## Resultats ML de reference (20 avril 2026)
Source: [reliable_probe_all_2022_summary.csv](/C:/Users/guilhem/Documents/mspr/data/processed/ml/reliable_probe_all_2022_summary.csv)

| Cible | R2 |
|---|---|
| extreme_gauche | 0.8547 |
| gauche | 0.2188 |
| centre | 0.6204 |
| droite | 0.4418 |
| extreme_droite | 0.8051 |

## Prochaines ameliorations (hors blocage grille)
1. Renforcer la gouvernance securite (procedure RSSI detaillee, rotation des secrets, journaux de securite).
2. Industrialiser le datamart BI (job de refresh planifie).
3. Ameliorer la robustesse ML de la cible `gauche`.
