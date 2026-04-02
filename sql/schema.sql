-- Postgres schema for MSPR Electio Analytics POC (Ile-de-France)

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

-- Thematic yearly feature marts (commune code can be a real commune INSEE
-- or a department proxy code like XX000).
CREATE TABLE IF NOT EXISTS commune_year_economy (
  insee_code char(5) NOT NULL REFERENCES geo_commune (insee_code),
  year integer NOT NULL,
  median_standard_of_living numeric,
  declared_income_median numeric,
  taxable_households_share numeric,
  social_benefits_income_share numeric,
  establishments_count numeric,
  business_creations_count numeric,
  business_creation_rate numeric,
  unemployment_rate numeric,
  poverty_rate numeric,
  PRIMARY KEY (insee_code, year)
);

CREATE TABLE IF NOT EXISTS commune_year_education (
  insee_code char(5) NOT NULL REFERENCES geo_commune (insee_code),
  year integer NOT NULL,
  no_diploma_rate_20_24 numeric,
  school_leavers_20_24_count numeric,
  school_leavers_20_24_no_diploma_count numeric,
  PRIMARY KEY (insee_code, year)
);

CREATE TABLE IF NOT EXISTS commune_year_demography (
  insee_code char(5) NOT NULL REFERENCES geo_commune (insee_code),
  year integer NOT NULL,
  population_total numeric,
  population_age_75_plus_count numeric,
  population_age_75_plus_share numeric,
  life_expectancy_women numeric,
  life_expectancy_men numeric,
  PRIMARY KEY (insee_code, year)
);

CREATE TABLE IF NOT EXISTS commune_year_environment (
  insee_code char(5) NOT NULL REFERENCES geo_commune (insee_code),
  year integer NOT NULL,
  social_housing_share numeric,
  catnat_communes_flood_count numeric,
  catnat_communes_storm_count numeric,
  catnat_communes_drought_count numeric,
  PRIMARY KEY (insee_code, year)
);

CREATE TABLE IF NOT EXISTS commune_year_election_context (
  election_type text NOT NULL,
  round smallint NOT NULL,
  year integer NOT NULL,
  insee_code char(5) NOT NULL REFERENCES geo_commune (insee_code),
  registered integer,
  votes_cast integer,
  votes_valid integer,
  turnout_rate numeric,
  valid_ballot_rate numeric,
  invalid_ballot_rate numeric,
  winner_share numeric,
  candidate_count integer,
  PRIMARY KEY (election_type, round, year, insee_code)
);

CREATE INDEX IF NOT EXISTS idx_commune_year_economy_year
  ON commune_year_economy (year);
CREATE INDEX IF NOT EXISTS idx_commune_year_education_year
  ON commune_year_education (year);
CREATE INDEX IF NOT EXISTS idx_commune_year_demography_year
  ON commune_year_demography (year);
CREATE INDEX IF NOT EXISTS idx_commune_year_environment_year
  ON commune_year_environment (year);
CREATE INDEX IF NOT EXISTS idx_commune_year_election_context_year
  ON commune_year_election_context (year);
