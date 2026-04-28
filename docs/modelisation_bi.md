# Modelisation de donnees (MCD + BI)

Date de reference: 28 avril 2026.

## MCD (modele conceptuel)
Entites principales:
1. `geo_department`
2. `geo_commune`
3. `election`
4. `candidate`
5. `election_result`
6. `indicator`
7. `indicator_value`

Relations clefs:
1. Un departement possede plusieurs communes.
2. Une election possede plusieurs resultats.
3. Un candidat peut apparaitre dans plusieurs resultats.
4. Un indicateur possede plusieurs valeurs par annee et territoire.

Regles de gestion:
1. `vote_share` doit rester dans `[0,1]`.
2. La cle `insee_code` structure les jointures territoriales.
3. Les objets sont historises par `year` et/ou `election_date`.

## Modele BI multidimensionnel
Modele principal: etoile.

Dimensions:
1. `bi.dim_time`
2. `bi.dim_geo`
3. `bi.dim_candidate`
4. `bi.dim_election`

Fait:
1. `bi.fact_election_result`

Extension possible:
1. Variante flocon sur la geographie (`departement` / `commune`).

## Deploiement
- Script: [bi_datamart.sql](/C:/Users/guilhem/Documents/mspr/sql/bi_datamart.sql)
- Schema relationnel source: [schema.sql](/C:/Users/guilhem/Documents/mspr/sql/schema.sql)

## Requete type (restitution)
```sql
SELECT
  f.year_key AS year,
  g.dept_code,
  g.dept_name,
  c.candidate_name,
  AVG(f.vote_share) AS avg_vote_share
FROM bi.fact_election_result f
JOIN bi.dim_geo g ON g.insee_code = f.insee_code
JOIN bi.dim_candidate c ON c.candidate_id = f.candidate_id
JOIN bi.dim_election e ON e.election_id = f.election_id
WHERE e.election_type = 'presidentielle'
  AND e.round = 1
GROUP BY f.year_key, g.dept_code, g.dept_name, c.candidate_name
ORDER BY year, dept_code, avg_vote_share DESC;
```
