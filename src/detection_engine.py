"""
Moteur de détection de fraude — approche par règles métier.

Chaque règle examine une transaction et lui attribue des points de
risque si elle semble suspecte. On construit les règles une par une,
en partant de la plus simple.

IMPORTANT : le moteur ne doit JAMAIS lire la colonne `is_fraud` pour
prendre ses décisions — elle ne sert qu'à la toute fin, pour évaluer
si le moteur a bien deviné juste. Un vrai système de détection en
production n'a pas cette information à l'avance.
"""

import pandas as pd


def compute_client_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcule, pour chaque client, sa moyenne et son écart-type de montant
    habituels — à partir de l'historique de TOUTES ses transactions.

    Note pédagogique : dans un vrai système, on calculerait ces stats
    uniquement sur l'historique *passé* du client, pas sur l'ensemble
    du dataset (qui inclut le futur) — on simplifie ici pour l'étape 1
    du moteur, on affinera ça plus tard si besoin.
    """
    stats = df.groupby("client_id")["amount"].agg(["mean", "std"]).reset_index()
    stats.columns = ["client_id", "avg_amount", "std_amount"]
    return stats


def rule_high_amount(df: pd.DataFrame, client_stats: pd.DataFrame, n_std: float = 3.0) -> pd.DataFrame:
    """
    Règle 1 — Montant anormal.

    Marque une transaction comme suspecte si son montant dépasse
    (moyenne_habituelle_du_client + n_std x écart-type_habituel).

    Ajoute deux colonnes au dataframe :
    - rule_high_amount (0/1) : la règle s'est-elle déclenchée ?
    - risk_score : score de risque cumulé (ici, +30 points si déclenchée)
    """
    df = df.merge(client_stats, on="client_id", how="left")

    df["amount_threshold"] = df["avg_amount"] + n_std * df["std_amount"]
    df["rule_high_amount"] = (df["amount"] > df["amount_threshold"]).astype(int)

    if "risk_score" not in df.columns:
        df["risk_score"] = 0
    df["risk_score"] += df["rule_high_amount"] * 30

    return df


def rule_impossible_travel(df: pd.DataFrame, max_hours: float = 3.0) -> pd.DataFrame:
    """
    Règle 2 — Voyage impossible.

    Pour chaque client, on trie ses transactions par ordre chronologique
    et on compare chaque transaction à la précédente. Si le pays a changé
    ET que moins de `max_hours` heures se sont écoulées, c'est physiquement
    suspect (personne ne peut changer de pays aussi vite).

    Limite connue : si l'écart de temps est plus long (ex. un vrai vol
    long-courrier légitime, ou une fraude générée avec un grand écart),
    cette règle ne se déclenchera pas — c'est pour ça qu'on la combine
    avec d'autres règles plutôt que de compter dessus seule.
    """
    df = df.sort_values(["client_id", "timestamp"]).reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    df["prev_country"] = df.groupby("client_id")["country"].shift(1)
    df["prev_timestamp"] = df.groupby("client_id")["timestamp"].shift(1)

    df["hours_since_prev"] = (df["timestamp"] - df["prev_timestamp"]).dt.total_seconds() / 3600

    df["rule_impossible_travel"] = (
        (df["country"] != df["prev_country"])
        & (df["prev_country"].notna())
        & (df["hours_since_prev"] <= max_hours)
    ).astype(int)

    if "risk_score" not in df.columns:
        df["risk_score"] = 0
    df["risk_score"] += df["rule_impossible_travel"] * 40

    return df


def rule_odd_hour(df: pd.DataFrame) -> pd.DataFrame:
    """
    Règle 3 — Heure inhabituelle.

    On ne connaît pas à l'avance les horaires "habituels" de chaque
    client (contrairement au montant, cette info n'a pas été gardée
    dans le CSV final) — on les redéduit donc directement des données,
    comme le ferait une vraie banque à partir de l'historique réel
    d'un client.

    Pour chaque client, on calcule la plage d'heures où il effectue
    habituellement 90% de ses achats (du 5e au 95e percentile). Toute
    transaction en dehors de cette plage est marquée suspecte.
    """
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["hour"] = df["timestamp"].dt.hour

    hour_bounds = df.groupby("client_id")["hour"].agg(
        hour_low=lambda h: h.quantile(0.05),
        hour_high=lambda h: h.quantile(0.95),
    ).reset_index()

    df = df.merge(hour_bounds, on="client_id", how="left")

    df["rule_odd_hour"] = (
        (df["hour"] < df["hour_low"]) | (df["hour"] > df["hour_high"])
    ).astype(int)

    if "risk_score" not in df.columns:
        df["risk_score"] = 0
    df["risk_score"] += df["rule_odd_hour"] * 20

    return df


def rule_high_frequency(df: pd.DataFrame, window_minutes: int = 10, min_count: int = 4) -> pd.DataFrame:
    """
    Règle 4 — Rafale de transactions.

    Pour chaque client, on compte combien de transactions ont eu lieu
    dans les `window_minutes` minutes précédentes. Si ce nombre atteint
    ou dépasse `min_count`, la transaction est marquée suspecte — un
    client normal ne fait jamais autant d'achats en si peu de temps.

    Implémentation : on utilise une fenêtre temporelle glissante (via
    rolling sur un index de dates), par client.
    """
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(["client_id", "timestamp"]).reset_index(drop=True)

    def count_in_window(group: pd.DataFrame) -> pd.Series:
        g = group.set_index("timestamp")
        # rolling compte, pour chaque transaction, combien de transactions
        # (elle incluse) sont tombées dans les X minutes précédentes
        counts = g["transaction_id"].rolling(f"{window_minutes}min").count()
        return counts

    df["txn_count_in_window"] = (
        df.groupby("client_id", group_keys=False)[["timestamp", "transaction_id"]]
        .apply(count_in_window, include_groups=False)
        .values
    )

    df["rule_high_frequency"] = (df["txn_count_in_window"] >= min_count).astype(int)

    if "risk_score" not in df.columns:
        df["risk_score"] = 0
    df["risk_score"] += df["rule_high_frequency"] * 35

    return df


def classify_risk_level(df: pd.DataFrame) -> pd.DataFrame:
    """
    Étape 3 — Scoring et priorisation.

    Convertit le score de risque numérique cumulé (somme des points de
    chaque règle déclenchée) en un niveau de risque lisible, comme le
    verrait un analyste fraude dans son outil de travail :

    - 0 point           -> Faible (rien de suspect détecté)
    - 1 à 34 points      -> Moyen (une seule règle légère déclenchée)
    - 35 points et plus  -> Élevé (règle forte déclenchée, ou plusieurs
                             règles combinées -> à traiter en priorité)
    """
    def level(score: int) -> str:
        if score == 0:
            return "Faible"
        elif score < 35:
            return "Moyen"
        else:
            return "Élevé"

    df["risk_level"] = df["risk_score"].apply(level)
    return df


def run_all_rules(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applique les 4 règles + le scoring, dans l'ordre, sur un dataframe
    de transactions brutes. Fonction pratique réutilisée par le script
    principal et par le générateur de dashboard.
    """
    client_stats = compute_client_stats(df)
    df = rule_high_amount(df, client_stats)
    df = rule_impossible_travel(df)
    df = rule_odd_hour(df)
    df = rule_high_frequency(df)
    df = classify_risk_level(df)
    return df


if __name__ == "__main__":
    df = pd.read_csv("data/transactions.csv")

    client_stats = compute_client_stats(df)
    df = rule_high_amount(df, client_stats)
    df = rule_impossible_travel(df)
    df = rule_odd_hour(df)
    df = rule_high_frequency(df)

    for rule_col, rule_name in [
        ("rule_high_amount", "Montant anormal"),
        ("rule_impossible_travel", "Voyage impossible"),
        ("rule_odd_hour", "Heure inhabituelle"),
        ("rule_high_frequency", "Rafale de transactions"),
    ]:
        n_flagged = df[rule_col].sum()
        n_real_fraud_flagged = df[(df[rule_col] == 1) & (df["is_fraud"] == 1)].shape[0]
        n_real_fraud_total = df["is_fraud"].sum()

        print(f"--- Règle : {rule_name} ---")
        print(f"Transactions marquées suspectes : {n_flagged}")
        print(f"Dont vraies fraudes : {n_real_fraud_flagged}")
        print(f"Rappel (sur {n_real_fraud_total} fraudes totales) : {n_real_fraud_flagged / n_real_fraud_total * 100:.1f}%")
        print(f"Précision : {n_real_fraud_flagged / n_flagged * 100:.1f}%" if n_flagged else "N/A")
        print()

    # Score combiné des quatre règles ensemble
    any_rule = (
        (df["rule_high_amount"] == 1)
        | (df["rule_impossible_travel"] == 1)
        | (df["rule_odd_hour"] == 1)
        | (df["rule_high_frequency"] == 1)
    )
    n_flagged_either = df[any_rule].shape[0]
    n_caught_either = df[any_rule & (df["is_fraud"] == 1)].shape[0]
    print(f"--- Combiné (au moins une des quatre règles) ---")
    print(f"Transactions marquées : {n_flagged_either}")
    print(f"Rappel combiné : {n_caught_either / df['is_fraud'].sum() * 100:.1f}%")
    print(f"Précision combinée : {n_caught_either / n_flagged_either * 100:.1f}%")

    # Etape 3 - Scoring et priorisation
    df = classify_risk_level(df)
    print("\n--- Répartition par niveau de risque ---")
    for level_name in ["Faible", "Moyen", "Élevé"]:
        subset = df[df["risk_level"] == level_name]
        n_total = subset.shape[0]
        n_fraud = subset[subset["is_fraud"] == 1].shape[0]
        taux_fraude = (n_fraud / n_total * 100) if n_total else 0
        print(f"{level_name:8s} : {n_total:6d} transactions, dont {n_fraud:4d} vraies fraudes ({taux_fraude:.1f}%)")