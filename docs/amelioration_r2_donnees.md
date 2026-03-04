# Données à ajouter pour améliorer le R²

Ce document liste les **données supplémentaires** qui permettraient d’obtenir un **R² plus élevé** et un meilleur pouvoir prédictif. Il s’appuie sur le cahier des charges Electio-Analytics (sécurité, emploi, vie associative, population, vie économique, pauvreté) et sur les limites actuelles du POC.

---

## 1. Plus d’observations (volumétrie)

Aujourd’hui : **8 départements × ~10 élections ≈ 80 lignes** (après exclusion de la première année pour les lags). Plus le nombre d’observations est faible, plus le modèle peine à généraliser et plus le R² sur un petit test set est instable.

| Type de donnée | Effet attendu | Source / mise en œuvre |
|----------------|---------------|-------------------------|
| **Résultats à la commune** | Beaucoup plus de lignes (centaines de communes en IDF × 10 élections). Même indicateurs agrégés ou communaux si disponibles. | data.gouv : résultats présidentielles par commune ou par bureau (ex. 2017 déjà en bureau ; étendre à d’autres années si dispo). |
| **Autres types d’élections** | Plus de lignes par territoire et par date (législatives, municipales, européennes). Réutiliser les mêmes indicateurs socio. | data.gouv – élections législatives, municipales, européennes par département/commune. |
| **Élargir la zone** | Plus de départements (ex. toute la France métropolitaine) → plus de lignes, mais attention à l’hétérogénéité. | Même pipeline ETL, en élargissant la liste des départements cibles. |

**Priorité** : passer à la **maille commune** (ou bureau) pour les résultats électoraux dès que possible, tout en gardant des indicateurs socio au même niveau ou en les agrégant (moyenne départementale par commune, etc.).

---

## 2. Indicateurs du sujet pas encore intégrés

Le sujet cite des indicateurs « fortement corrélés » aux résultats. Ceux **déjà utilisés** : chômage, pauvreté, niveau de vie médian, part sans diplôme 20–24 ans, logements sociaux, participation. Ceux **à ajouter** pour mieux coller au sujet et potentiellement améliorer le R² :

| Indicateur (sujet) | Intérêt pour le modèle | Source possible |
|--------------------|------------------------|-----------------|
| **Sécurité** | Délits/criminalité par territoire souvent liés au vote (perception de l’ordre). | data.gouv – données sécurité (faits constatés par commune/EPCI) ; ministère de l’Intérieur. |
| **Vie associative** | Proxy de capital social, lien avec participation et ancrage politique. | INSEE, associations (répertoire des associations), enquêtes « Vie associative » ; ODD ou jeux locaux si dispo. |
| **Population / densité** | Structure du territoire (urbain/rural, taille) très liée aux comportements électoraux. | INSEE – population légale, densité par commune/département (recensement, ODD). |
| **Vie économique / nombre d’entreprises** | Créations d’entreprises, nombre d’établissements par zone. | SIRENE (API ou fichiers) – créations, établissements par commune/département ; INSEE. |
| **Dépenses publiques locales** | Investissement communal/départemental (équipement, social) peut refléter le positionnement politique. | Comptes des collectivités (DGCL, data.gouv), agrégés par commune/département. |

**Priorité** : **population/densité** et **sécurité** (souvent disponibles et interprétables) ; puis **nombre d’entreprises** (SIRENE) et **dépenses publiques** si temps.

---

## 3. Contexte temporel et national

Les évolutions entre deux élections (changement de majorité, crise, candidats) ne sont pas capturées par les seuls indicateurs territoriaux. Des variables **temporelles / nationales** aident à expliquer les ruptures et à améliorer le R² :

| Donnée | Rôle | Source / mise en œuvre |
|--------|------|-------------------------|
| **Sondages nationaux** (intentions de vote) | Tendance nationale à la date de l’élection ou en moyenne sur la campagne. | Enquêtes d’opinion (sites agrégateurs, instituts) ; à associer à l’année d’élection. |
| **Indicateurs macro** | PIB, chômage national, inflation. | INSEE, Banque de France – séries annuelles. |
| **Taux de participation national** (ou régional) | Contexte de mobilisation. | Déjà partiellement capté par la participation départementale ; ajouter la part nationale si utile. |
| **Candidat sortant / type de scrutin** | Binaire ou catégoriel (élection avec sortant ou non, second tour ou pas). | Données électorales (liste des candidats, résultat 2ᵉ tour). |

---

## 4. Enrichissements mentionnés dans le sujet

Le cahier des charges indique qu’il est possible d’enrichir avec :

- **Enquêtes d’opinion** : intentions de vote, thèmes prioritaires (sécurité, emploi, pouvoir d’achat) – à lier à l’année ou au trimestre de l’élection.
- **Flux réseaux sociaux** : volume ou sentiment par candidat/région (complexe à collecter et à normaliser).
- **Dépenses publiques locales** : déjà citées ci-dessus.

Ces éléments peuvent servir de **variables explicatives supplémentaires** (features) une fois alignés sur la maille (département/commune) et l’année.

---

## 5. Synthèse : ordre de priorité pour un meilleur R²

1. **Augmenter le nombre d’observations**  
   Passer aux **résultats par commune** (ou bureau) pour garder 8 départements mais avoir des centaines de lignes par élection → effet fort sur la stabilité et le R².

2. **Ajouter des indicateurs du sujet**  
   **Population / densité**, **sécurité**, puis **nombre d’entreprises** (SIRENE) et **dépenses publiques** si possible. Tous à la maille département (ou commune si vous passez en communal).

3. **Contexte temporel**  
   **Sondages nationaux** (intentions de vote) et éventuellement **indicateurs macro** (PIB, chômage national) par année d’élection.

4. **Autres élections**  
   Législatives, municipales, européennes par même maille pour multiplier les observations et réutiliser les mêmes features.

En pratique, **maille commune + indicateurs population/densité et sécurité** constituent le meilleur compromis effort / gain pour viser un R² « correct » (par ex. > 0,3–0,5) tout en restant aligné avec le sujet et les livrables du POC.
