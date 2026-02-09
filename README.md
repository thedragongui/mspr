# MSPR Big Data - Electio Analytics POC

Perimetre: departement Herault (code 34) uniquement.
Election cible: presidentielle 2002 (2 tours).
Objectif: predire la part de vote d'un candidat/parti a partir d'indicateurs socio-economiques et d'historiques electoraux.
Stack: Python + PostgreSQL (Docker) + PowerBI.

## Demarrage rapide
1) Copier `.env.example` vers `.env` et ajuster les variables.
2) Lancer Postgres: `docker compose up -d`
3) Creer l'env Python et installer les deps:
   - `python -m venv .venv`
   - `.venv\Scripts\Activate.ps1`
   - `pip install -r requirements.txt`
4) Le schema est charge au premier demarrage via `sql/schema.sql`.
   Si vous changez le schema: `docker compose down -v` puis `docker compose up -d`.
5) Placer les fichiers sources dans `data/raw/` (voir `docs/sources.md`).
6) Lancer le pipeline: `python src/etl/run_etl.py`
7) Ouvrir les notebooks ou PowerBI.

## Livrables
- Dossier de synthese: `docs/` (cadrage, sources, mcd, methodo)
- Jeu de donnees nettoye: `data/clean/` (CSV ou export SQL)
- Code: `src/` et `sql/`
- Support de soutenance: `slides/`

## Clefs de jointure attendues
- `insee_code` (commune) + `year` pour les indicateurs
- `insee_code` + `election_date` + `round` pour les resultats electoraux

## Arborescence
- `docs/` documentation projet
- `sql/` schema Postgres
- `src/` scripts ETL
- `data/raw/` sources brutes
- `data/clean/` donnees nettoyees
- `data/processed/` jeux de travail
- `notebooks/` EDA + modele
- `powerbi/` consignes PowerBI
- `slides/` support soutenance
