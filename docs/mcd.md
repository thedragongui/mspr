# MCD (Modele Conceptuel de Donnees)

Version: 2026-04-02

## Entites
- `geo_department` : departements
  - PK: `dept_code`
  - Attributs: `dept_name`
- `geo_commune` : communes
  - PK: `insee_code`
  - FK: `dept_code -> geo_department.dept_code`
  - Attributs: `commune_name`, `population`, `area_km2`, `latitude`, `longitude`
- `election` : metadata des elections
  - PK: `election_id`
  - Attributs: `election_type`, `election_date`, `round`, `scope`
  - Domaines utilises:
    - `election_type`: `presidentielle`, `municipale`
    - `scope`: `departement`, `commune`
  - Contrainte: `UNIQUE (election_type, election_date, round, scope)`
- `candidate` : candidats
  - PK: `candidate_id`
  - Attributs: `candidate_name`, `party_name`, `party_code`
- `election_result` : resultats par candidat et commune
  - PK composite: (`election_id`, `insee_code`, `candidate_id`)
  - FK: `election_id -> election.election_id`
  - FK: `insee_code -> geo_commune.insee_code`
  - FK: `candidate_id -> candidate.candidate_id`
  - Attributs: `registered`, `votes_cast`, `votes_valid`, `votes`, `vote_share`
- `indicator` : dictionnaire des indicateurs socio-economiques
  - PK: `indicator_id`
  - Attributs: `indicator_code` (unique), `indicator_name`, `unit`, `source`
- `indicator_value` : valeurs annuelles des indicateurs par commune
  - PK composite: (`indicator_id`, `insee_code`, `year`)
  - FK: `indicator_id -> indicator.indicator_id`
  - FK: `insee_code -> geo_commune.insee_code`
  - Attributs: `value`, `source_file`

## Cardinalites
- `geo_department` (1,1) -> (0,N) `geo_commune`
- `geo_commune` (1,1) -> (0,N) `election_result`
- `election` (1,1) -> (0,N) `election_result`
- `candidate` (1,1) -> (0,N) `election_result`
- `indicator` (1,1) -> (0,N) `indicator_value`
- `geo_commune` (1,1) -> (0,N) `indicator_value`

## Regles De Gestion
- Les resultats au niveau departement sont stockes avec un `insee_code` synthetique de type `XX000` dans `geo_commune`.
- Les resultats au niveau commune utilisent le vrai code INSEE a 5 caracteres.
- Le catalogue `indicator` est extensible (nouvelles variables socio, revenus, education, demographie, environnement/CatNat) sans changer le schema relationnel.

## Schema MCD (Mermaid)
```mermaid
erDiagram
    GEO_DEPARTMENT ||--o{ GEO_COMMUNE : contient
    GEO_COMMUNE ||--o{ ELECTION_RESULT : porte
    ELECTION ||--o{ ELECTION_RESULT : genere
    CANDIDATE ||--o{ ELECTION_RESULT : obtient
    INDICATOR ||--o{ INDICATOR_VALUE : definit
    GEO_COMMUNE ||--o{ INDICATOR_VALUE : mesure_sur

    %% Domaines metier utilises:
    %% ELECTION.election_type = presidentielle | municipale
    %% ELECTION.scope = departement | commune

    GEO_DEPARTMENT {
        char2 dept_code PK
        text dept_name
    }

    GEO_COMMUNE {
        char5 insee_code PK
        text commune_name
        char2 dept_code FK
        int population
        numeric area_km2
        numeric latitude
        numeric longitude
    }

    ELECTION {
        int election_id PK
        text election_type
        date election_date
        smallint round
        text scope
    }

    CANDIDATE {
        int candidate_id PK
        text candidate_name
        text party_name
        text party_code
    }

    ELECTION_RESULT {
        int election_id PK,FK
        char5 insee_code PK,FK
        int candidate_id PK,FK
        int registered
        int votes_cast
        int votes_valid
        int votes
        numeric vote_share
    }

    INDICATOR {
        int indicator_id PK
        text indicator_code
        text indicator_name
        text unit
        text source
    }

    INDICATOR_VALUE {
        int indicator_id PK,FK
        char5 insee_code PK,FK
        int year PK
        numeric value
        text source_file
    }
```
