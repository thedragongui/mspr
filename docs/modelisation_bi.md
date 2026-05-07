# Modelisation de donnees (MCD + BI)

Date de reference: 7 mai 2026.

## MCD (modele conceptuel)
Le MCD detaille et a jour est documente dans:
- [mcd.md](/C:/Users/guilhem/Documents/mspr/docs/mcd.md)

Resume fonctionnel:
1. Referentiel geographique: `geo_department`, `geo_commune`.
2. Coeur electoral: `election`, `candidate`, `election_result`.
3. Contexte socio: `indicator`, `indicator_value`.
4. Datamarts thematiques annuels (commune): `commune_year_economy`, `commune_year_education`, `commune_year_demography`, `commune_year_environment`, `commune_year_election_context`.

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
