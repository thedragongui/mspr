-- BI datamart deployment (star schema) for MSPR Electio Analytics
-- Safe to rerun.

CREATE SCHEMA IF NOT EXISTS bi;

CREATE TABLE IF NOT EXISTS bi.dim_time (
  year_key integer PRIMARY KEY,
  year integer NOT NULL,
  decade integer NOT NULL
);

CREATE TABLE IF NOT EXISTS bi.dim_geo (
  insee_code char(5) PRIMARY KEY,
  dept_code char(2) NOT NULL,
  dept_name text,
  commune_name text,
  population integer,
  area_km2 numeric,
  latitude numeric,
  longitude numeric
);

CREATE TABLE IF NOT EXISTS bi.dim_candidate (
  candidate_id integer PRIMARY KEY,
  candidate_name text NOT NULL,
  party_name text,
  party_code text
);

CREATE TABLE IF NOT EXISTS bi.dim_election (
  election_id integer PRIMARY KEY,
  election_type text NOT NULL,
  election_date date NOT NULL,
  round smallint NOT NULL,
  scope text NOT NULL
);

CREATE TABLE IF NOT EXISTS bi.fact_election_result (
  election_id integer NOT NULL,
  insee_code char(5) NOT NULL,
  candidate_id integer NOT NULL,
  year_key integer NOT NULL,
  registered integer,
  votes_cast integer,
  votes_valid integer,
  votes integer,
  vote_share numeric(6,5),
  PRIMARY KEY (election_id, insee_code, candidate_id),
  FOREIGN KEY (election_id) REFERENCES bi.dim_election (election_id),
  FOREIGN KEY (insee_code) REFERENCES bi.dim_geo (insee_code),
  FOREIGN KEY (candidate_id) REFERENCES bi.dim_candidate (candidate_id),
  FOREIGN KEY (year_key) REFERENCES bi.dim_time (year_key)
);

-- Refresh dimensions
INSERT INTO bi.dim_time (year_key, year, decade)
SELECT DISTINCT
  EXTRACT(YEAR FROM e.election_date)::int AS year_key,
  EXTRACT(YEAR FROM e.election_date)::int AS year,
  (FLOOR(EXTRACT(YEAR FROM e.election_date)::numeric / 10) * 10)::int AS decade
FROM election e
ON CONFLICT (year_key) DO UPDATE
SET
  year = EXCLUDED.year,
  decade = EXCLUDED.decade;

INSERT INTO bi.dim_geo (
  insee_code,
  dept_code,
  dept_name,
  commune_name,
  population,
  area_km2,
  latitude,
  longitude
)
SELECT
  gc.insee_code,
  gc.dept_code,
  gd.dept_name,
  gc.commune_name,
  gc.population,
  gc.area_km2,
  gc.latitude,
  gc.longitude
FROM geo_commune gc
LEFT JOIN geo_department gd ON gd.dept_code = gc.dept_code
ON CONFLICT (insee_code) DO UPDATE
SET
  dept_code = EXCLUDED.dept_code,
  dept_name = EXCLUDED.dept_name,
  commune_name = EXCLUDED.commune_name,
  population = EXCLUDED.population,
  area_km2 = EXCLUDED.area_km2,
  latitude = EXCLUDED.latitude,
  longitude = EXCLUDED.longitude;

INSERT INTO bi.dim_candidate (candidate_id, candidate_name, party_name, party_code)
SELECT candidate_id, candidate_name, party_name, party_code
FROM candidate
ON CONFLICT (candidate_id) DO UPDATE
SET
  candidate_name = EXCLUDED.candidate_name,
  party_name = EXCLUDED.party_name,
  party_code = EXCLUDED.party_code;

INSERT INTO bi.dim_election (election_id, election_type, election_date, round, scope)
SELECT election_id, election_type, election_date, round, scope
FROM election
ON CONFLICT (election_id) DO UPDATE
SET
  election_type = EXCLUDED.election_type,
  election_date = EXCLUDED.election_date,
  round = EXCLUDED.round,
  scope = EXCLUDED.scope;

-- Refresh fact table
INSERT INTO bi.fact_election_result (
  election_id,
  insee_code,
  candidate_id,
  year_key,
  registered,
  votes_cast,
  votes_valid,
  votes,
  vote_share
)
SELECT
  er.election_id,
  er.insee_code,
  er.candidate_id,
  EXTRACT(YEAR FROM e.election_date)::int AS year_key,
  er.registered,
  er.votes_cast,
  er.votes_valid,
  er.votes,
  er.vote_share
FROM election_result er
JOIN election e ON e.election_id = er.election_id
ON CONFLICT (election_id, insee_code, candidate_id) DO UPDATE
SET
  year_key = EXCLUDED.year_key,
  registered = EXCLUDED.registered,
  votes_cast = EXCLUDED.votes_cast,
  votes_valid = EXCLUDED.votes_valid,
  votes = EXCLUDED.votes,
  vote_share = EXCLUDED.vote_share;

CREATE INDEX IF NOT EXISTS idx_bi_fact_year ON bi.fact_election_result (year_key);
CREATE INDEX IF NOT EXISTS idx_bi_fact_geo ON bi.fact_election_result (insee_code);
CREATE INDEX IF NOT EXISTS idx_bi_fact_candidate ON bi.fact_election_result (candidate_id);

CREATE OR REPLACE VIEW bi.vw_fact_presidentielle_t1 AS
SELECT
  f.election_id,
  f.year_key AS year,
  g.insee_code,
  g.dept_code,
  g.dept_name,
  g.commune_name,
  c.candidate_id,
  c.candidate_name,
  c.party_name,
  c.party_code,
  f.registered,
  f.votes_cast,
  f.votes_valid,
  f.votes,
  f.vote_share
FROM bi.fact_election_result f
JOIN bi.dim_election e ON e.election_id = f.election_id
JOIN bi.dim_geo g ON g.insee_code = f.insee_code
JOIN bi.dim_candidate c ON c.candidate_id = f.candidate_id
WHERE e.election_type = 'presidentielle'
  AND e.round = 1;
