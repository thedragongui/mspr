# Grille MSPR - Etat de conformite

Reference grille: [grille_mspr_extract.txt](/C:/Users/guilhem/Documents/mspr/docs/grille_mspr_extract.txt)  
Date d'evaluation interne: 28 avril 2026.

## Synthese
- `OK`: 9 criteres
- `PARTIEL`: 0 critere
- `KO`: 0 critere

Conclusion: conformite complete au niveau documentaire/technique attendu par la grille MSPR, avec points d'amelioration encore possibles sur la performance ML de certaines cibles.

## Evaluation critere par critere
| Competence (grille) | Statut | Preuves dans le repo | Ecart restant |
|---|---|---|---|
| Besoins data + strategie globale + processus formalise + schema flux | OK | [cadrage_besoins.md](/C:/Users/guilhem/Documents/mspr/docs/cadrage_besoins.md), [pipeline_architecture.md](/C:/Users/guilhem/Documents/mspr/docs/pipeline_architecture.md), [sources.md](/C:/Users/guilhem/Documents/mspr/docs/sources.md) | RAS pour la grille. |
| Architecture BI 3 couches | OK | [pipeline_architecture.md](/C:/Users/guilhem/Documents/mspr/docs/pipeline_architecture.md), [modelisation_bi.md](/C:/Users/guilhem/Documents/mspr/docs/modelisation_bi.md), [docker-compose.yml](/C:/Users/guilhem/Documents/mspr/docker-compose.yml) | Aucun blocant pour la grille. |
| Strategie big data (ingestion, stockage, pipelines, restitution) | OK | [pipeline_architecture.md](/C:/Users/guilhem/Documents/mspr/docs/pipeline_architecture.md), [run_etl.py](/C:/Users/guilhem/Documents/mspr/src/etl/run_etl.py), [README.md](/C:/Users/guilhem/Documents/mspr/README.md) | RAS pour la grille. |
| ML implemente/teste en Python + interpretation ecrite + pouvoir predictif > 0.5 | OK | [train.py](/C:/Users/guilhem/Documents/mspr/src/ml/train.py), [train_reliable_all_years.py](/C:/Users/guilhem/Documents/mspr/src/ml/train_reliable_all_years.py), [ml_precision.md](/C:/Users/guilhem/Documents/mspr/docs/ml_precision.md), [reliable_probe_all_2022_summary.csv](/C:/Users/guilhem/Documents/mspr/data/processed/ml/reliable_probe_all_2022_summary.csv) | Pour l'objectif interne "tous les partis > 0.5", `gauche` reste sous 0.5 (R2=0.2188). |
| Data visualisation + rapports interactifs | OK | [build_dashboard.py](/C:/Users/guilhem/Documents/mspr/src/dashboard/build_dashboard.py), [build_dashboard_interactive.py](/C:/Users/guilhem/Documents/mspr/src/dashboard/build_dashboard_interactive.py) | Verifier en soutenance l'ouverture du HTML interactif sur le poste jury. |
| Referentiel de donnees + criteres selection/validation | OK | [sources.md](/C:/Users/guilhem/Documents/mspr/docs/sources.md), [modelisation_bi.md](/C:/Users/guilhem/Documents/mspr/docs/modelisation_bi.md), [schema.sql](/C:/Users/guilhem/Documents/mspr/sql/schema.sql) | Aucun blocant. |
| Entrepot unique + modele multidimensionnel (etoile/flocon/grappe) deploie dans solution BI | OK | [modelisation_bi.md](/C:/Users/guilhem/Documents/mspr/docs/modelisation_bi.md), [bi_datamart.sql](/C:/Users/guilhem/Documents/mspr/sql/bi_datamart.sql), [schema.sql](/C:/Users/guilhem/Documents/mspr/sql/schema.sql) | RAS pour la grille. |
| Qualite des donnees (mesure + cleansing) | OK | [data_quality.py](/C:/Users/guilhem/Documents/mspr/src/ml/data_quality.py), [pipeline_architecture.md](/C:/Users/guilhem/Documents/mspr/docs/pipeline_architecture.md) | Aucun blocant pour la grille. |
| Securite donnees + conformite juridique (RGPD, clauses, PI) | OK | [securite_rgpd.md](/C:/Users/guilhem/Documents/mspr/docs/securite_rgpd.md), [procedure_rssi.md](/C:/Users/guilhem/Documents/mspr/docs/procedure_rssi.md), [docker-compose.yml](/C:/Users/guilhem/Documents/mspr/docker-compose.yml), [sources.md](/C:/Users/guilhem/Documents/mspr/docs/sources.md) | RAS pour la grille (roadmap production: TLS strict et rotation automatisee des secrets). |

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
1. Industrialiser le datamart BI (job de refresh planifie).
2. Ameliorer la robustesse ML de la cible `gauche`.
3. Automatiser le durcissement securite de production (TLS strict + rotation des secrets outillee).
