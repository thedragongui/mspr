# Securite et conformite RGPD

Date de reference: 28 avril 2026.

## Perimetre juridique
- Donnees manipulees: resultats electoraux agreges + indicateurs territoriaux publics.
- Sources: open data (`data.gouv`, `INSEE`, `geo.api.gouv.fr`).
- Nature des donnees: pas de donnees personnelles directes dans le perimetre fonctionnel du POC.

## Mesures appliquees sur le projet
1. Minimisation des donnees
- Conservation uniquement des attributs necessaires a l'analyse BI/ML.
- Exclusion des champs nominatifs individuels.

2. Tracabilite des sources et de la PI
- Inventaire des sources, formats et conditions d'usage: [sources.md](/C:/Users/guilhem/Documents/mspr/docs/sources.md).
- Versionning des scripts ETL/ML et des artefacts de sortie.

3. Confidentialite operationnelle
- Secrets hors code dans `.env`.
- Segmentation des services (`db`, `pgadmin`, `airflow`, `dashboard`) via Docker Compose.
- Acces base restreint au reseau de la stack.

4. Integrite et qualite des donnees
- Controles qualite explicites avant entrainement: [data_quality.py](/C:/Users/guilhem/Documents/mspr/src/ml/data_quality.py).
- Regles: bornes `[0,1]`, contraintes de coherence sur les comptes de vote, dedoublonnage.

5. Rejouabilite et auditabilite
- Pipeline reproductible: `python -m src.etl.run_etl`.
- Export des jeux nettoyes: `python -m src.etl.export_clean_datasets`.
- Livraison des datasets nettoyes dans `data/clean/`.

## Procedure RSSI de reference
- Procedure detaillee formalisee: [procedure_rssi.md](/C:/Users/guilhem/Documents/mspr/docs/procedure_rssi.md).
- Couvre notamment:
  - gouvernance et responsabilites,
  - controle d'acces et gestion des comptes,
  - gestion et rotation des secrets,
  - journalisation / supervision,
  - gestion d'incident,
  - exigences RGPD et registre de traitement.

## Position par rapport a la grille MSPR
- Critere securite/juridique: couvert sur le plan documentaire et organisationnel.
- Pour une mise en production: activer TLS de bout en bout sur les interfaces d'administration et industrialiser la rotation des secrets.
