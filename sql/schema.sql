-- Postgres schema for MSPR Electio Analytics POC (Herault / 34)

CREATE TABLE IF NOT EXISTS geo_department (
  dept_code char(2) PRIMARY KEY,
  dept_name text NOT NULL
);

CREATE TABLE IF NOT EXISTS geo_commune (
  insee_code char(5) PRIMARY KEY,
  commune_name text NOT NULL,
  dept_code char(2) NOT NULL REFERENCES geo_department (dept_code),
  population integer,
  area_km2 numeric,
  latitude numeric,
  longitude numeric
);

CREATE TABLE IF NOT EXISTS election (
  election_id serial PRIMARY KEY,
  election_type text NOT NULL,
  election_date date NOT NULL,
  round smallint NOT NULL,
  scope text NOT NULL,
  UNIQUE (election_type, election_date, round, scope)
);

CREATE TABLE IF NOT EXISTS candidate (
  candidate_id serial PRIMARY KEY,
  candidate_name text NOT NULL,
  party_name text,
  party_code text
);

CREATE TABLE IF NOT EXISTS election_result (
  election_id integer NOT NULL REFERENCES election (election_id),
  insee_code char(5) NOT NULL REFERENCES geo_commune (insee_code),
  candidate_id integer NOT NULL REFERENCES candidate (candidate_id),
  registered integer,
  votes_cast integer,
  votes_valid integer,
  votes integer,
  vote_share numeric(6,5),
  PRIMARY KEY (election_id, insee_code, candidate_id)
);

CREATE TABLE IF NOT EXISTS indicator (
  indicator_id serial PRIMARY KEY,
  indicator_code text NOT NULL UNIQUE,
  indicator_name text NOT NULL,
  unit text,
  source text
);

CREATE TABLE IF NOT EXISTS indicator_value (
  indicator_id integer NOT NULL REFERENCES indicator (indicator_id),
  insee_code char(5) NOT NULL REFERENCES geo_commune (insee_code),
  year integer NOT NULL,
  value numeric,
  source_file text,
  PRIMARY KEY (indicator_id, insee_code, year)
);

INSERT INTO geo_department (dept_code, dept_name)
VALUES ('34', 'Herault')
ON CONFLICT (dept_code) DO NOTHING;
