# Étape 1 — Génération des données de transactions

## Objectif

Avant de pouvoir détecter des fraudes, il faut un jeu de données de
transactions bancaires à analyser. En l'absence de données réelles
(confidentielles par nature), on génère un jeu de données simulé mais
réaliste, avec une "vérité terrain" (`is_fraud`) permettant d'évaluer
la qualité du moteur de détection développé dans les étapes suivantes.

## Démarche

### 1. Profils clients

200 clients fictifs sont créés, chacun avec un profil de comportement
"normal" propre :
- pays de résidence habituel
- montant moyen dépensé et écart-type associé
- plage horaire d'activité habituelle
- catégories de commerces préférées

### 2. Transactions normales

Pour chaque client, plusieurs dizaines de transactions sont générées
sur une période de 30 jours, respectant son profil habituel (montant
tiré d'une loi normale autour de sa moyenne, horaires dans sa plage
habituelle, catégories parmi ses préférées).

### 3. Transactions frauduleuses (injectées volontairement)

Environ 2% des transactions générées suivent un des 4 patterns de
fraude bancaire classiques, volontairement injectés pour s'écarter du
profil habituel du client :

| Pattern | Description |
|---|---|
| `high_amount` | Montant 8 à 20 fois supérieur à la moyenne habituelle du client |
| `impossible_travel` | Transaction dans un pays différent du pays habituel (scénario "impossible travel" — le client ne peut pas être physiquement à deux endroits en même temps) |
| `odd_hour` | Transaction en pleine nuit (1h-4h), hors de la plage horaire habituelle du client |
| `high_frequency` | Rafale de 6 à 12 transactions en quelques minutes, à petits montants — typique d'une carte volée/clonée testée automatiquement |

### 4. Résultat

Un fichier `data/transactions.csv` contenant environ 18 800
transactions, dont ~6,5% de fraude (le pattern `high_frequency`
génère plusieurs lignes par occurrence, ce qui remonte artificiellement
ce taux par rapport aux 2% de tirage initial — point à garder en tête
pour l'interprétation des résultats du détecteur).

Colonnes du dataset :
- `transaction_id`, `client_id`, `timestamp`, `amount`, `country`,
  `merchant_category`
- `is_fraud` (0/1) — vérité terrain, à ne pas utiliser dans le moteur
  de détection (seulement pour évaluer ses résultats a posteriori)
- `fraud_pattern` — quel type de fraude a été injecté (NaN si transaction
  normale)

## Reproductibilité

Une graine aléatoire fixe (`random.seed(42)`) est utilisée pour que
le dataset généré soit identique à chaque exécution du script — utile
pour comparer les résultats de différentes versions du moteur de
détection sur exactement les mêmes données.

## Prochaine étape

Construction du moteur de détection par règles métier (voir
`docs/02-moteur-detection.md`), qui va tenter de retrouver les
transactions frauduleuses sans utiliser la colonne `is_fraud`.
