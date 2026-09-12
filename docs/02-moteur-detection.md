# Étape 2 & 3 — Moteur de détection par règles et scoring

## Objectif

Construire un moteur qui analyse chaque transaction **sans jamais lire
la colonne `is_fraud`**, lui attribue un score de risque, puis classe
ce score en niveau de priorité pour un analyste (Faible / Moyen / Élevé).
La colonne `is_fraud` sert uniquement, à la fin, à évaluer la qualité
du moteur — comme le ferait un vrai audit de performance.

## Les 4 règles implémentées

### Règle 1 — Montant anormal (30 points)
Une transaction est marquée suspecte si son montant dépasse
`moyenne_habituelle_du_client + 3 × écart-type`. Statistiquement, un
tel écart a très peu de chances d'être un hasard normal.

### Règle 2 — Voyage impossible (40 points)
Si le pays de la transaction change par rapport à la transaction
précédente du même client, et que moins de 3h se sont écoulées entre
les deux, c'est physiquement suspect (aucun déplacement réel n'est
possible aussi vite).

### Règle 3 — Heure inhabituelle (20 points)
Pour chaque client, la plage horaire habituelle d'achat est déduite
directement des données (5e au 95e percentile de ses heures d'achat
passées — pas d'information "théorique" préexistante, comme dans un
vrai système). Toute transaction en dehors de cette plage est marquée
suspecte.

### Règle 4 — Rafale de transactions (35 points)
Si un client effectue 4 transactions ou plus dans une fenêtre glissante
de 10 minutes, toutes ces transactions sont marquées suspectes —
signature typique d'une carte volée/clonée testée rapidement.

## Résultats individuels de chaque règle

| Règle | Transactions marquées | Rappel | Précision |
|---|---|---|---|
| Montant anormal | 112 | 8,4% | 91,1% |
| Voyage impossible | 59 | 2,1% | 42,4% |
| Heure inhabituelle | 520 | 9,3% | 21,7% |
| Rafale de transactions | 613 | 50,3% | 99,3% |
| **Combiné (≥1 règle)** | **1301** | **69,9%** | **65,0%** |

**Rappel** = % des vraies fraudes effectivement retrouvées par la règle.
**Précision** = % des alertes de la règle qui sont de vraies fraudes
(le reste étant des fausses alertes).

## Analyse — le compromis rappel/précision

Ce tableau illustre un arbitrage central en détection de fraude :

- La règle **montant anormal** est très précise (peu de fausses alertes)
  mais rate la majorité des fraudes (elle ne voit qu'un seul type de
  comportement suspect).
- La règle **heure inhabituelle** attrape plus de fraudes mais avec
  beaucoup de fausses alertes (78% de ses alertes sont infondées) — un
  seuil statistique large capte aussi des comportements légitimes mais
  rares.
- La règle **rafale de transactions** est à la fois la plus efficace
  ET la plus fiable (99,3% de précision) : ce pattern comportemental
  est très rarement légitime.
- **Combiner les règles augmente le rappel** (on attrape plus de
  fraudes au total) mais peut faire baisser la précision globale si
  une règle faible (comme "voyage impossible" avec son seuil actuel)
  ajoute plus de bruit que de signal.

## Étape 3 — Scoring et priorisation

Chaque règle contribue des points à un `risk_score` cumulé par
transaction. Ce score est ensuite converti en niveau de risque :

- **0 point** → Faible
- **1 à 34 points** → Moyen
- **35 points et plus** → Élevé

### Résultat de la classification

| Niveau | Volume | Vraies fraudes | Taux de fraude |
|---|---|---|---|
| Faible | 17 459 | 364 | 2,1% |
| Moyen | 627 | 210 | 33,5% |
| **Élevé** | **674** | **636** | **94,4%** |

### Pourquoi c'est utile en pratique

Un analyste fraude ne peut pas vérifier 18 760 transactions à la main.
En se concentrant uniquement sur la catégorie "Élevé" (674 transactions,
soit 3,6% du volume total), il traite déjà 94,4% de vrais cas — un
gain de temps considérable par rapport à une revue manuelle exhaustive
ou à une seule règle isolée.

## Limites connues et pistes d'amélioration

- Le seuil de la règle "voyage impossible" (3h) est arbitraire et
  pourrait être affiné avec de vraies données de temps de trajet par
  paire de pays.
- Les règles sont calculées sur l'historique complet du client
  (passé + futur), ce qui n'est pas réaliste en production — un vrai
  système ne connaît que le passé au moment de la transaction. Une
  version future du projet pourrait recalculer les statistiques
  client de façon strictement rétroactive (rolling historique).
- Les poids de chaque règle (30, 40, 20, 35) ont été fixés
  arbitrairement en fonction de leur gravité perçue — une vraie
  optimisation (ex. régression logistique sur les résultats) pourrait
  affiner ces poids automatiquement.

## Prochaine étape

Dashboard de visualisation des alertes (voir `docs/03-dashboard.md`).