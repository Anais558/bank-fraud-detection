"""
Générateur de transactions bancaires simulées.

Génère un jeu de données réaliste de transactions pour N clients,
chacun ayant un profil de comportement "normal" (pays habituel,
montant moyen, plage horaire habituelle), puis injecte volontairement
un pourcentage de transactions frauduleuses qui s'écartent de ce profil.

La colonne `is_fraud` sert de "vérité terrain" (ground truth) pour
évaluer ensuite la qualité du moteur de détection — dans la vraie vie,
on ne l'aurait évidemment pas à l'avance.
"""

import random
import uuid
from datetime import datetime, timedelta

import pandas as pd

random.seed(42)  # reproductibilité

COUNTRIES = ["MA", "FR", "ES", "DE", "US", "NG", "RU", "CN"]
MERCHANT_CATEGORIES = [
    "grocery", "restaurant", "electronics", "travel",
    "fuel", "clothing", "online_gaming", "jewelry", "cash_withdrawal",
]

N_CLIENTS = 200
N_DAYS = 30
AVG_TRANSACTIONS_PER_CLIENT_PER_DAY = 3
FRAUD_RATE = 0.02  # 2% des transactions seront frauduleuses


def build_client_profiles(n_clients: int) -> list[dict]:
    """Crée un profil de comportement 'normal' pour chaque client."""
    profiles = []
    for i in range(n_clients):
        home_country = random.choice(COUNTRIES)
        profiles.append({
            "client_id": f"CUST{i:04d}",
            "home_country": home_country,
            "avg_amount": round(random.uniform(15, 300), 2),
            "std_amount": round(random.uniform(5, 50), 2),
            "active_hour_start": random.randint(6, 10),
            "active_hour_end": random.randint(18, 23),
            "preferred_categories": random.sample(MERCHANT_CATEGORIES, k=3),
        })
    return profiles


def generate_normal_transaction(profile: dict, timestamp: datetime) -> dict:
    """Génère une transaction cohérente avec le profil du client."""
    amount = max(1.0, round(random.gauss(profile["avg_amount"], profile["std_amount"]), 2))
    category = random.choice(profile["preferred_categories"])
    return {
        "transaction_id": str(uuid.uuid4()),
        "client_id": profile["client_id"],
        "timestamp": timestamp.isoformat(),
        "amount": amount,
        "country": profile["home_country"],
        "merchant_category": category,
        "is_fraud": 0,
        "fraud_pattern": None,
    }


def generate_fraud_transaction(profile: dict, timestamp: datetime) -> list[dict]:
    """
    Génère une ou plusieurs transactions frauduleuses selon un des patterns
    classiques de fraude bancaire. Retourne une LISTE (le pattern
    high_frequency génère plusieurs transactions d'un coup, les autres
    n'en génèrent qu'une).
    """
    pattern = random.choice([
        "high_amount",       # montant anormalement élevé
        "impossible_travel", # pays différent, temporellement incohérent
        "odd_hour",          # heure inhabituelle (nuit profonde)
        "high_frequency",    # rafale de transactions rapprochées
    ])

    base_txn = {
        "transaction_id": str(uuid.uuid4()),
        "client_id": profile["client_id"],
        "timestamp": timestamp.isoformat(),
        "amount": profile["avg_amount"],
        "country": profile["home_country"],
        "merchant_category": random.choice(MERCHANT_CATEGORIES),
        "is_fraud": 1,
        "fraud_pattern": pattern,
    }

    if pattern == "high_amount":
        # 8 à 20 fois le montant moyen habituel du client
        base_txn["amount"] = round(profile["avg_amount"] * random.uniform(8, 20), 2)
        return [base_txn]

    elif pattern == "impossible_travel":
        foreign = random.choice([c for c in COUNTRIES if c != profile["home_country"]])
        base_txn["country"] = foreign
        base_txn["merchant_category"] = "cash_withdrawal"
        return [base_txn]

    elif pattern == "odd_hour":
        odd_hour = random.choice([1, 2, 3, 4])
        base_txn["timestamp"] = timestamp.replace(hour=odd_hour, minute=random.randint(0, 59)).isoformat()
        return [base_txn]

    elif pattern == "high_frequency":
        # Génère 6 à 12 transactions en l'espace de quelques minutes,
        # ce qu'un client normal ne fait jamais (carte clonée/testée en rafale)
        n_burst = random.randint(6, 12)
        burst = []
        for i in range(n_burst):
            burst_ts = timestamp + timedelta(seconds=random.randint(5, 40) * i)
            burst.append({
                "transaction_id": str(uuid.uuid4()),
                "client_id": profile["client_id"],
                "timestamp": burst_ts.isoformat(),
                "amount": round(random.uniform(5, 50), 2),  # petits montants (carte testée)
                "country": profile["home_country"],
                "merchant_category": "online_gaming",
                "is_fraud": 1,
                "fraud_pattern": "high_frequency",
            })
        return burst

    return [base_txn]


def generate_dataset() -> pd.DataFrame:
    profiles = build_client_profiles(N_CLIENTS)
    transactions = []
    start_date = datetime.now() - timedelta(days=N_DAYS)

    for profile in profiles:
        n_txns = max(1, int(random.gauss(
            AVG_TRANSACTIONS_PER_CLIENT_PER_DAY * N_DAYS, 5
        )))
        for _ in range(n_txns):
            day_offset = random.uniform(0, N_DAYS)
            hour = random.randint(profile["active_hour_start"], profile["active_hour_end"])
            minute = random.randint(0, 59)
            ts = start_date + timedelta(days=day_offset)
            ts = ts.replace(hour=hour, minute=minute)

            if random.random() < FRAUD_RATE:
                transactions.extend(generate_fraud_transaction(profile, ts))
            else:
                transactions.append(generate_normal_transaction(profile, ts))

    df = pd.DataFrame(transactions)
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


if __name__ == "__main__":
    df = generate_dataset()
    output_path = "/home/claude/fraud-detection-lab/data/transactions.csv"
    df.to_csv(output_path, index=False)

    print(f"{len(df)} transactions générées -> {output_path}")
    print(f"Dont {df['is_fraud'].sum()} frauduleuses ({df['is_fraud'].mean()*100:.2f}%)")
    print("\nRépartition des patterns de fraude :")
    print(df[df.is_fraud == 1]["fraud_pattern"].value_counts())
