"""Pipeline ETL completo: extract -> transform -> load. Uso: python -m etl.pipeline"""

import os

from dotenv import load_dotenv

from etl.extract import gerar_dados, salvar_csvs
from etl.load import carregar_bigquery, carregar_sqlite
from etl.transform import agregados_mensais, enriquecer_batidas


def main() -> None:
    load_dotenv()
    print("[1/3] Extract: gerando dados sinteticos (seed=42)...")
    dados = gerar_dados(seed=42)
    salvar_csvs(dados, "data/raw")

    print("[2/3] Transform: enriquecendo batidas e agregando...")
    enriquecidas = enriquecer_batidas(dados["batidas"])
    agregados = agregados_mensais(enriquecidas, dados["colaboradores"])

    print("[3/3] Load: SQLite + BigQuery...")
    db_path = os.environ.get("HR_DB_PATH", "data/hr.db")
    carregar_sqlite(dados, enriquecidas, db_path)
    try:
        carregar_bigquery(agregados)
    except Exception as exc:  # noqa: BLE001 — BigQuery fora do ar não pode derrubar o app
        print(f"BigQuery: falha na carga ({type(exc).__name__}) — seguindo sem analytics.")
    print(f"Pipeline concluido. SQLite em {db_path}.")


if __name__ == "__main__":
    main()
