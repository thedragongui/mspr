# Sources de donnees (a confirmer)

Objectif: couvrir la region Ile-de-France avec des donnees election + indicateurs socio-economiques.

## Elections
- Portail elections data.gouv: https://www.data.gouv.fr/fr/pages/donnees-des-elections/
- API datasets data.gouv: https://www.data.gouv.fr/api/1/datasets/?q=election+presidentielle
- Cible technique ETL:
  - 1969, 1974, 1981, 1988, 1995, 2002, 2007, 2012, 2022:
    xlsx "resultats par departement" (ressources data.gouv) au 1er tour.
  - 2017:
    txt "resultats definitifs du 1er tour par bureaux de vote", agrege ensuite au departement.

## Securite
- data.gouv.fr: https://www.data.gouv.fr/fr/pages/donnees-securite/
  Attendu: faits constates par commune ou EPCI si dispo.

## Emploi / Economie
- data.gouv.fr: https://www.data.gouv.fr/datasets/search?q=emploi
- INSEE datasets: https://www.data.gouv.fr/fr/organizations/institut-national-de-la-statistique-et-des-etudes-economiques-insee/
  Attendu: taux de chomage, categories socio-pro, revenus.

## Demographie / Pauvrete / Entreprises
- INSEE: population, densite, niveau de vie, pauvrete
- Entreprises: nombre d'entreprises, creation d'entreprises (SIRENE si besoin)

## Source socio-economique integree dans l'ETL
- Dataset: https://www.data.gouv.fr/datasets/indicateurs-territoriaux-de-developpement-durable
- Fichier exploite: `ODD_DEP.csv` dans `ODD_CSV.zip`
- URL de telechargement: `https://www.insee.fr/fr/statistiques/fichier/4505239/ODD_CSV.zip`
- Indicateurs charges:
  - `unemployment_rate` -> variable `taux_chom_bit` (`sous_champ=total`)
  - `poverty_rate` -> variable `taux_pvt` (`sous_champ=total`)
  - `median_standard_of_living` -> variable `niveau_vie_median`
  - `no_diploma_rate_20_24` -> variable `part_20_24_sortis_nondip`
  - `social_housing_share` -> variable `part_pls`

## Notes
- Filtrer sur les departements IDF: 75, 77, 78, 91, 92, 93, 94, 95
- Normaliser la cle geo en `insee_code` de type `XX000` pour la maille departementale
- Prioriser les sources avec identifiants INSEE stables

## Criteres d'analyse des donnees (grille d'evaluation MSPR)
- [ ] Besoins en donnees des metiers collectes a partir du cahier des charges.
- [ ] Processus de collecte, structuration, gestion et valorisation des donnees formalise.
- [ ] Descriptif ecrit du processus fourni avec sources de donnees listees et timing coherent.
- [ ] Schema de flux du pipeline (BPM/ETL) produit et lisible.
- [ ] Architecture BI decrite sur 3 couches: collecte, stockage/modelisation, restitution.
- [ ] Technologies d'ingestion choisies en fonction des types de donnees et justifiees.
- [ ] Choix de stockage (ELT, entrepot, datalake) argumente selon le besoin.
- [ ] Traitements de donnees modelises (pipeline, parallelisation/distribution si necessaire).
- [ ] Referentiel de donnees defini avec criteres de selection et de validation explicites.
- [ ] Qualite des donnees mesuree (completude, coherence, doublons, tracabilite).
- [ ] Nettoyage des donnees realise avec un outil/methode identifiee (data cleansing).
- [ ] Restitution preparee avec visualisations pertinentes et rapports exploitables par les metiers.
- [ ] Securite et conformite juridique integrees (RGPD, clauses contractuelles, propriete intellectuelle).
