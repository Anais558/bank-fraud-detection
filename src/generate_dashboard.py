"""
Génère un dashboard HTML autonome (un seul fichier, pas besoin de
serveur) à partir des transactions scorées par le moteur de détection.

Usage :
    python src/generate_dashboard.py

Produit : dashboard.html à la racine du projet — à ouvrir directement
dans un navigateur (double-clic).
"""

import json

import pandas as pd

from detection_engine import run_all_rules

TOP_N_ALERTS = 30  # nombre d'alertes "Élevé" affichées dans le tableau


def build_dashboard_data(df: pd.DataFrame) -> dict:
    """Prépare les données nécessaires au dashboard, au format JSON-friendly."""
    risk_counts = df["risk_level"].value_counts().to_dict()

    top_alerts = (
        df[df["risk_level"] == "Élevé"]
        .sort_values("risk_score", ascending=False)
        .head(TOP_N_ALERTS)
    )

    alerts_records = top_alerts[
        ["transaction_id", "client_id", "timestamp", "amount", "country",
         "merchant_category", "risk_score", "is_fraud"]
    ].to_dict(orient="records")

    return {
        "risk_counts": {
            "Faible": int(risk_counts.get("Faible", 0)),
            "Moyen": int(risk_counts.get("Moyen", 0)),
            "Élevé": int(risk_counts.get("Élevé", 0)),
        },
        "top_alerts": alerts_records,
        "total_transactions": int(len(df)),
        "total_fraud": int(df["is_fraud"].sum()),
    }


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Dashboard — Détection de fraude</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
  body {{ font-family: Arial, sans-serif; margin: 2rem; background: #f5f6fa; color: #222; }}
  h1 {{ margin-bottom: 0.2rem; }}
  .subtitle {{ color: #666; margin-bottom: 2rem; }}
  .cards {{ display: flex; gap: 1rem; margin-bottom: 2rem; }}
  .card {{ background: white; padding: 1rem 1.5rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); flex: 1; }}
  .card .value {{ font-size: 2rem; font-weight: bold; }}
  .card .label {{ color: #666; font-size: 0.9rem; }}
  #chart-container {{ background: white; padding: 1.5rem; border-radius: 8px; max-width: 500px; margin-bottom: 2rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  table {{ width: 100%; border-collapse: collapse; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  th, td {{ padding: 0.6rem 0.8rem; text-align: left; border-bottom: 1px solid #eee; font-size: 0.9rem; }}
  th {{ background: #2c3e50; color: white; }}
  tr:hover {{ background: #f9f9f9; }}
  .fraud-yes {{ color: #c0392b; font-weight: bold; }}
  .fraud-no {{ color: #27ae60; }}
</style>
</head>
<body>

<h1>Dashboard — Détection de fraude transactionnelle</h1>
<p class="subtitle">Top {top_n} alertes de niveau "Élevé", triées par score de risque</p>

<div class="cards">
  <div class="card"><div class="value">{total}</div><div class="label">Transactions analysées</div></div>
  <div class="card"><div class="value">{fraud}</div><div class="label">Vraies fraudes (référence)</div></div>
  <div class="card"><div class="value">{eleve}</div><div class="label">Alertes "Élevé"</div></div>
</div>

<div id="chart-container">
  <canvas id="riskChart"></canvas>
</div>

<table>
  <thead>
    <tr>
      <th>Client</th><th>Date/Heure</th><th>Montant</th><th>Pays</th>
      <th>Catégorie</th><th>Score</th><th>Vraie fraude ?</th>
    </tr>
  </thead>
  <tbody>
    {rows}
  </tbody>
</table>

<script>
const data = {{
  labels: ['Faible', 'Moyen', 'Élevé'],
  datasets: [{{
    data: [{faible}, {moyen}, {eleve}],
    backgroundColor: ['#27ae60', '#f39c12', '#c0392b']
  }}]
}};
new Chart(document.getElementById('riskChart'), {{
  type: 'doughnut',
  data: data,
  options: {{ plugins: {{ legend: {{ position: 'bottom' }} }} }}
}});
</script>

</body>
</html>
"""


def build_table_rows(alerts: list[dict]) -> str:
    rows = []
    for a in alerts:
        fraud_class = "fraud-yes" if a["is_fraud"] == 1 else "fraud-no"
        fraud_label = "Oui" if a["is_fraud"] == 1 else "Non"
        rows.append(
            f"<tr><td>{a['client_id']}</td><td>{str(a['timestamp'])[:19]}</td>"
            f"<td>{a['amount']:.2f}</td><td>{a['country']}</td>"
            f"<td>{a['merchant_category']}</td><td>{a['risk_score']}</td>"
            f"<td class='{fraud_class}'>{fraud_label}</td></tr>"
        )
    return "\n".join(rows)


if __name__ == "__main__":
    df = pd.read_csv("data/transactions.csv")
    df = run_all_rules(df)
    df.to_csv("data/scored_transactions.csv", index=False)

    dashboard_data = build_dashboard_data(df)

    html = HTML_TEMPLATE.format(
        top_n=TOP_N_ALERTS,
        total=dashboard_data["total_transactions"],
        fraud=dashboard_data["total_fraud"],
        faible=dashboard_data["risk_counts"]["Faible"],
        moyen=dashboard_data["risk_counts"]["Moyen"],
        eleve=dashboard_data["risk_counts"]["Élevé"],
        rows=build_table_rows(dashboard_data["top_alerts"]),
    )

    with open("dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("Dashboard généré : dashboard.html")
    print(f"Répartition : {dashboard_data['risk_counts']}")