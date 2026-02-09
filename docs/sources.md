# Sources de donnees (a confirmer)

Objectif: couvrir le departement 34 avec des donnees election + indicateurs socio-economiques.

## Elections
- data.gouv.fr: https://www.data.gouv.fr/fr/pages/donnees-des-elections/
  Attendu: resultats par commune, tour, candidat/parti, voix, inscrits.
- Cible: presidentielle 2002 (communes, 2 tours)
  Dataset: https://www.data.gouv.fr/datasets/resultats-des-elections-persidentielles-2002
  Fichier: resultats_elections_presidentielles_2002.tgz (PR02_T1_BVot.csv, PR02_T2_BVot.csv)

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

## Notes
- Filtrer sur code departement = 34 et codes INSEE commune (5 chiffres)
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
