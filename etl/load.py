"""Load: grava dados operacionais no SQLite e agregados no BigQuery."""

import sqlite3
from pathlib import Path

import pandas as pd

from core.bq import get_bq_client

DATASET = "rh_analytics"
TABELA_AGREGADOS = "agregados_mensais"


def carregar_sqlite(
    dados: dict[str, pd.DataFrame],
    batidas_enriquecidas: pd.DataFrame,
    db_path: str | Path,
) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        dados["colaboradores"].to_sql("colaboradores", conn, if_exists="replace", index=False)
        batidas_enriquecidas.to_sql("batidas", conn, if_exists="replace", index=False)
        dados["ajustes"].to_sql("ajustes", conn, if_exists="replace", index=False)
        conn.execute("DROP TABLE IF EXISTS audit_log")
        conn.execute(
            """CREATE TABLE audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ajuste_id INTEGER NOT NULL,
                acao TEXT NOT NULL,
                justificativa TEXT NOT NULL,
                autor TEXT NOT NULL,
                criado_em TEXT NOT NULL
            )"""
        )
        conn.commit()
    finally:
        conn.close()


def carregar_bigquery(agregados: pd.DataFrame) -> bool:
    cliente = get_bq_client()
    if cliente is None:
        print("BigQuery: credenciais ausentes — pulando carga (esperado em dev/CI).")
        return False

    from google.cloud import bigquery

    cliente.create_dataset(DATASET, exists_ok=True)
    destino = f"{cliente.project}.{DATASET}.{TABELA_AGREGADOS}"
    config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    cliente.load_table_from_dataframe(agregados, destino, job_config=config).result()
    print(f"BigQuery: {len(agregados)} linhas carregadas em {destino}.")
    return True
