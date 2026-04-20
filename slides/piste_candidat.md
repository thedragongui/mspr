# Piste D'Evolution: Prediction Par Candidat

## Positionnement dans le projet
- **Mode principal conserve**: prediction par **blocs politiques** (extreme_gauche, gauche, centre, droite, extreme_droite).
- **Pourquoi**: plus robuste avec peu d'elections historiques et moins sensible aux changements de personnes.
- **Resultat actuel (test 2022, commune)**: tous les R2 des blocs sont > 0.

## Idee sauvegardee pour la soutenance
- Ajouter un mode **par candidat** en complement du mode bloc.
- Utiliser une couche de **normalisation historique**:
  - alias de noms candidats (ex: variantes d'ecriture),
  - lineage de parti (ex: FN -> RN),
  - gestion des changements de candidat dans un meme courant politique.

## Prototype deja implemente
- Script dedie: `python -m src.ml.train_entity`
- Deux modes:
  - `--entity-mode candidate` (ex: `LE PEN`, `MACRON`, `MELENCHON`)
  - `--entity-mode party` (lineage parti, ex: `RN`)
- Controle qualite des donnees inclus avant entrainement.
- Evaluation temporelle conforme:
  - train sur l'historique disponible,
  - test sur la derniere annee (`--test-years latest`).

## Limites expliquees au jury
- Mode candidat = moins de donnees par entite, donc variance plus forte.
- Certains candidats n'ont qu'une election exploitable (historique insuffisant).
- Le mode bloc reste la base decisionnelle la plus stable pour la production.

## Message a presenter
- "Nous avons fiabilise la prediction en bloc politique en production."
- "Nous avons deja prepare l'extension par candidat, avec normalisation historique et pipeline dedie."
- "Cette extension est integree comme feuille de route data science, sans casser la fiabilite du coeur de modele."
