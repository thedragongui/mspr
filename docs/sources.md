# Sources de donnees (a confirmer)

Objectif: couvrir la region Ile-de-France avec des donnees election + indicateurs socio-economiques.

## Elections
- Portail elections data.gouv: https://www.data.gouv.fr/fr/pages/donnees-des-elections/
- API datasets data.gouv: https://www.data.gouv.fr/api/1/datasets/?q=election+presidentielle
- Cible technique ETL:
  - 1969, 1974, 1981, 1988, 1995, 2002, 2007, 2012:
    CSV `cdsp_presi{annee}t1_circ.csv` (dataset data.gouv `elections-presidentielles-1965-2012`),
    puis agregation au departement (somme `Inscrits`, `Votants`, `Exprimes`, `voix`).
  - Fallback technique:
    XLSX "resultats par departement" (ressources data.gouv) si lecture CSV indisponible.
  - 2022:
    xlsx "resultats par departement" (ressource data.gouv) au 1er tour.
  - 2017:
    txt "resultats definitifs du 1er tour par bureaux de vote", agrege ensuite au departement.
  - Migration progressive au niveau commune (scope `commune`):
    - 1981: `cdsp_presi1981t1_commp9000.csv` (communes > 9000 hab.)
    - 1988: `cdsp_presi1988t1_commp9000.csv` (communes > 9000 hab.)
    - 1995: `cdsp_presi1995t1_commp9000.csv` (communes > 9000 hab.)
    - 2002: `cdsp_presi2002t1_commp9000.csv` (communes > 9000 hab.)
    - 2012: `PR12_Bvot_T1T2.txt` (tour 1 filtre + agregation commune)
    - 2017: `PR17_BVot_T1_FE.txt` (agregation commune)
    - 2022: `resultats-par-niveau-burvot-t1-france-entiere.txt` (agregation commune)
    - Note couverture: 1981-2002 est partiel (grandes communes), 2012-2022 est quasi exhaustif.
    - Filtre geographique IDF applique: 75, 77, 78, 91, 92, 93, 94, 95.

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
  - `unemployment_rate_youth_15_24` -> variable `taux_chom_bit` (`sous_champ=15_24`)
  - `unemployment_rate_women` -> variable `taux_chom_bit` (`sous_champ=femme`)
  - `unemployment_rate_men` -> variable `taux_chom_bit` (`sous_champ=homme`)
  - `poverty_rate` -> variable `taux_pvt` (`sous_champ=total`)
  - `median_standard_of_living` -> variable `niveau_vie_median`
  - `no_diploma_rate_20_24` -> variable `part_20_24_sortis_nondip`
  - `social_housing_share` -> variable `part_pls`
  - `life_expectancy_women` -> variable `esper_vie` (`sous_champ=femme`)
  - `life_expectancy_men` -> variable `esper_vie` (`sous_champ=homme`)
  - `long_term_jobseekers_share` -> variable `part_deld`
  - `jobseekers_de_count` -> variable `nb_deld`
  - `jobseekers_abc_count` -> variable `nb_deABC`
  - `overindebtedness_cases_count` -> variable `nb_dossiers_deposes`

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
