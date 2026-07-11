"""Cliente BigQuery compartilhado (ETL e tool de analytics)."""

import json
import os


def get_bq_client():
    """Retorna bigquery.Client ou None se nao houver credencial configurada."""
    projeto = os.environ.get("GCP_PROJECT_ID")
    sa_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
    sa_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not projeto or not (sa_json or sa_path):
        return None

    from google.cloud import bigquery
    from google.oauth2 import service_account

    if sa_json:
        credenciais = service_account.Credentials.from_service_account_info(
            json.loads(sa_json))
        return bigquery.Client(project=projeto, credentials=credenciais)
    return bigquery.Client(project=projeto)
