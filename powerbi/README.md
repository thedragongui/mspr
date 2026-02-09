# PowerBI

## Connexion a Postgres
1) Get Data -> PostgreSQL
2) Server: localhost, Database: mspr_electio
3) Auth: user/password de `.env`
4) Charger les tables `election_result`, `indicator_value`, `geo_commune`

## Alternative CSV
- Utiliser `data/clean/` si exporte en CSV
- Verifier la cle `insee_code`

## Recommandations
- Cartes par commune (code INSEE)
- Courbes temporelles par election
