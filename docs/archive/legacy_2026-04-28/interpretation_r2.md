# Interprétation du R² pour le jury – Modèle prédictif électoral

## Résumé pour la soutenance

- Avec le **mode « R² stabilisé »** (features minimales : lag de la cible + département + numéro d’élection, et forte régularisation Ridge), on obtient typiquement un **R² légèrement positif** (ex. ~0,05 à 0,10) sur le split temporel test (2017, 2022), et une **MAE** de l’ordre de 5 points de part de vote (0,05).
- Si le R² reste **négatif ou proche de zéro** dans d’autres configurations (toutes features, autre cible, etc.), les explications ci-dessous permettent de le justifier devant le jury.

---

## Pourquoi le R² peut être négatif (ou proche de zéro)

Dans ce POC, le **R² sur l’échantillon de test** peut être **négatif** ou proche de zéro. Cela ne signifie pas que le modèle ou la démarche sont invalides. Voici les points à présenter au jury.

### 1. Que signifie un R² négatif ?

- **R² = 0** : le modèle prédit exactement comme la **moyenne** des valeurs observées (prédiction constante).
- **R² &lt; 0** : le modèle fait **moins bien** que la simple prédiction par la moyenne des valeurs de test.

Un R² négatif indique donc que, sur les années de test (ex. 2017 et 2022), les prédictions s’écartent plus des vraies valeurs que ne le ferait la moyenne. C’est possible même avec une méthodologie correcte, pour les raisons suivantes.

### 2. Causes structurelles dans notre contexte

- **Peu d’observations**  
  On dispose de **8 départements × environ 8–10 élections** (selon le split). Le nombre de lignes pour l’entraînement et pour le test reste limité. Avec si peu de données, un R² positif et stable est difficile à obtenir, surtout en **prédiction temporelle** (on teste sur des années futures).

- **Changement de régime dans le temps**  
  Les élections 2017 et 2022 ne se comportent pas comme les élections des décennies précédentes (recomposition politique, nouveaux candidats, enjeux différents). Un modèle entraîné sur le passé peut donc avoir un R² faible ou négatif sur ces années, sans que la démarche soit fausse.

- **Split temporel strict**  
  Conformément au sujet, on entraîne sur le passé et on teste sur des années **non vues** (ex. 2017, 2022). On ne « triche » pas en mélangeant les années. Cette rigueur dégrade souvent le R² par rapport à un split aléatoire, mais elle est **correcte** pour un usage prédictif réel.

- **Cible difficile**  
  Prédire la **part de vote** (d’un gagnant ou d’une famille politique) à l’échelle départementale est intrinsèquement difficile : beaucoup de facteurs non capturés (médias, contexte national, candidats) jouent un rôle important.

### 3. Ce que nous mettons en place pour rapprocher le R² de zéro (ou le rendre positif)

- **Mode « R² stabilisé » (défaut)**  
  Nous utilisons un jeu de variables **minimal** : le **lag de la cible** (résultat de l’élection précédente dans le même département), le **numéro d’élection** (tendance dans le temps) et les **indicatrices département**. Avec une **forte régularisation** (Ridge, alpha élevé), on limite le sur-apprentissage et on obtient un R² **proche de zéro ou légèrement positif** (ex. 0,05–0,10) et une MAE d’environ 5 points.
- **Désactiver ce mode** : option `--no-stable-r2` ; le modèle utilise alors toutes les features (socio + lags), ce qui peut donner un R² plus négatif mais reste utile pour l’analyse.

- **Métriques complémentaires**  
  Nous ne nous reposons pas uniquement sur le R² :
  - **MAE** (erreur absolue moyenne) : interprétable en points de pourcentage (ex. 0,07 ≈ 7 points).
  - **RMSE** : pénalise les grosses erreurs.
  - Le **R²** reste rapporté pour répondre aux attentes du sujet sur le « degré de précision » du modèle.

### 4. Message pour le jury

- Un **R² négatif ou proche de zéro** dans ce POC reflète surtout :
  - la **faible taille** du jeu de données (8 départements, ~10 élections),
  - le **respect d’un split temporel** (test sur le futur),
  - la **difficulté métier** de la prédiction électorale.

- La **démarche** reste valide : ETL, features (socio-économiques + historiques électoraux), découpage train/test temporel, régularisation, et présentation des scénarios (1–2–3 ans) comme demandé.

- L’**accuracy / pouvoir prédictif** peut être présenté via le **MAE** (et éventuellement le RMSE) en plus du R², avec une phrase du type :  
  *« Sur les années 2017 et 2022, le modèle se trompe en moyenne de X points de pourcentage (MAE = …). Le R² négatif indique que, sur cette période de test, la prédiction reste plus difficile que la simple moyenne, ce qui est attendu compte tenu du petit échantillon et du split temporel strict. »*

### 5. Référence rapide

| Métrique | Interprétation |
|----------|----------------|
| **R² &lt; 0** | Le modèle fait moins bien que prédire la moyenne sur le test. Fréquent en petit échantillon + split temporel. |
| **R² ≈ 0** | Le modèle fait à peu près comme la moyenne ; prédiction modeste mais stable. |
| **MAE** | Erreur moyenne en proportion (ex. 0,07 = 7 points de part de vote). |
| **RMSE** | Même idée que MAE, en pénalisant davantage les grandes erreurs. |

Ce document peut être cité dans le rapport et le support de soutenance pour justifier et expliquer un R² négatif ou proche de zéro.

---

**Pour aller plus loin** : voir `docs/amelioration_r2_donnees.md` pour la liste des données à ajouter (maille commune, sécurité, population, entreprises, sondages, etc.) afin d’obtenir un R² plus élevé en phase de production ou en prolongation du POC.
