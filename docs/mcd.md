# MCD (modele conceptuel de donnees)

## Entites
- geo_department (dept_code, dept_name)
- geo_commune (insee_code, commune_name, dept_code, population, area_km2, latitude, longitude)
- election (election_id, election_type, election_date, round, scope)
- candidate (candidate_id, candidate_name, party_name, party_code)
- election_result (election_id, insee_code, candidate_id, votes, vote_share, registered, votes_cast, votes_valid)
- indicator (indicator_id, indicator_code, indicator_name, unit, source)
- indicator_value (indicator_id, insee_code, year, value, source_file)

## Relations
- geo_department 1--N geo_commune
- geo_commune 1--N election_result
- election 1--N election_result
- candidate 1--N election_result
- indicator 1--N indicator_value
- geo_commune 1--N indicator_value
