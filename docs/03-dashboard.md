# Étape 4 — Dashboard de visualisation

## Objectif

Rendre les résultats du moteur de détection consultables visuellement,
comme le ferait un vrai outil de travail pour un analyste fraude,
plutôt que de rester dans un terminal.

## Choix technique

Un dashboard HTML autonome (un seul fichier, généré par script Python)
plutôt qu'une application web complète (React + serveur) — suffisant
pour ce stade du projet, sans dépendance supplémentaire à installer.
Le graphique utilise Chart.js, chargé depuis un CDN.

## Fonctionnement

Le script `src/generate_dashboard.py` :

1. Charge les transactions brutes (`data/transactions.csv`)
2. Applique les 4 règles de détection + le scoring (fonction
   `run_all_rules`, réutilisée depuis `detection_engine.py`)
3. Sauvegarde le résultat scoré dans `data/scored_transactions.csv`
4. Génère `dashboard.html` à la racine du projet, contenant :
   - 3 cartes de synthèse (total transactions, vraies fraudes,
     alertes "Élevé")
   - Un graphique en anneau montrant la répartition Faible/Moyen/Élevé
   - Un tableau des 30 alertes "Élevé" les plus fortes, triées par
     score de risque décroissant, avec indication si c'est une vraie
     fraude (à des fins de validation ici — dans un vrai outil, cette
     colonne n'existerait pas puisqu'elle ne serait pas connue à
     l'avance)

## Usage

```bash
python src/generate_dashboard.py
```

Puis ouvrir `dashboard.html` directement dans un navigateur
(double-clic — aucun serveur nécessaire).

## Limites et pistes d'amélioration

- Dashboard statique (généré une fois, pas de rafraîchissement en
  temps réel) — une vraie version en production lirait un flux de
  transactions en continu.
- Pas d'authentification ni de multi-utilisateur — hors du périmètre
  d'un projet de démonstration.
- Amélioration possible : ajouter un filtre par client ou par période,
  ou un graphique d'évolution du taux de fraude dans le temps.

## Bilan du projet

| Étape | Résultat |
|---|---|
| Génération de données | ~18 800 transactions simulées, 6,45% de fraude injectée |
| Détection par règles | 4 règles combinées, 69,9% de rappel, 65% de précision |
| Scoring | Catégorie "Élevé" (3,6% du volume) capture 94,4% des vraies fraudes |
| Dashboard | Visualisation HTML autonome des alertes prioritaires |

Ce pipeline complet (génération → détection → scoring → visualisation)
illustre une approche de bout en bout de la détection de fraude
transactionnelle, avec un principe clé transférable au secteur
bancaire réel : prioriser l'attention humaine limitée sur les
transactions à plus fort risque plutôt que de tout traiter à volume
égal.