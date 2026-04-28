# Procedure RSSI - MSPR BI/Big Data

Date de reference: 28 avril 2026.

## 1. Objet
Definir les procedures de securite applicables au POC MSPR pour garantir:
- confidentialite,
- integrite,
- disponibilite,
- tracabilite,
- conformite RGPD.

## 2. Perimetre
- Services: `db`, `pgadmin`, `airflow`, `dashboard`.
- Donnees: resultats electoraux agreges + indicateurs socio-economiques publics.
- Livrables couverts: code, scripts ETL/ML, fichiers de sortie `data/processed/*` et `data/clean/*`.

## 3. Roles et responsabilites
- Responsable securite projet (role RSSI): valide les regles d'acces et les exceptions.
- Responsable data/BI: applique les controles qualite et la politique de retention.
- Exploitant plateforme: maintient les secrets, les services et les journaux.
- Equipe projet: respecte les regles d'hygiene (mots de passe, acces, commits, partage).

## 4. Controle d'acces
1. Principe du moindre privilege:
- 1 compte nominatif par utilisateur.
- Pas de compte partage pour les acces admin.

2. Regles comptes techniques:
- identifiants admin par defaut interdits en usage courant;
- rotation des mots de passe a chaque nouvelle soutenance / environnement.

3. Droits base de donnees:
- separation lecture/ecriture si possible (`reader`, `writer`).
- suppression des privileges inutiles sur les schemas non utilises.

## 5. Gestion des secrets
1. Stockage:
- secrets uniquement dans `.env` local (jamais en clair dans Git).
- `.env` exclu du versionning.

2. Rotation:
- a chaque changement d'equipe ou incident;
- minimum trimestriel si environnement persistant.

3. Diffusion:
- transmission hors canal public (pas de mail non chiffre, pas de ticket public).

## 6. Chiffrement et reseau
1. En transit:
- activer TLS pour les interfaces exposees (pgAdmin, Airflow, dashboard) si acces externe.

2. En interne:
- services limites au reseau Docker du projet.
- ports externes exposes uniquement si necessaire a la demo.

## 7. Journalisation et supervision
1. Logs a conserver:
- logs ETL/ML (execution, erreurs, stats),
- logs applicatifs des services,
- traces d'administration (creation/suppression comptes, changements de secrets).

2. Retention minimale:
- 90 jours pour les logs techniques de demo/projet.

3. Alertes minimales:
- echecs repetes de connexion admin,
- crashs repetes d'un service critique (db/etl),
- echec de pipeline ETL.

## 8. Gestion d'incident
1. Detection:
- anomalie detectee via logs, supervision ou retour utilisateur.

2. Qualification:
- criticite `haute`, `moyenne`, `basse`.

3. Reponse:
- isoler le service impacte,
- revoquer/rotater les secrets potentiellement exposes,
- restaurer le service depuis une configuration saine,
- verifier l'integrite des donnees.

4. Cloture:
- compte-rendu court (cause, impact, action corrective, date).

## 9. Exigences RGPD
1. Base legale:
- traitement de donnees ouvertes et agregees a des fins d'analyse.

2. Minimisation:
- pas de donnees nominatives citoyennes exploitees dans le POC.

3. Registre de traitement (format projet):
- finalite,
- categories de donnees,
- source,
- duree de conservation,
- mesures de securite.

4. Droits et obligations:
- si ajout futur de donnees personnelles: realiser une analyse d'impact (AIPD) et mettre a jour la base legale.

## 10. Controle qualite securite avant soutenance
Checklist minimale:
1. Mots de passe par defaut remplaces.
2. `.env` present localement et non commite.
3. Export `data/clean/*` genere.
4. Pipeline ETL rejouable sans erreur bloquante.
5. Documentation securite et RGPD a jour.
