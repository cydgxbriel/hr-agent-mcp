import sqlite3

from etl.extract import gerar_dados
from etl.load import carregar_sqlite
from etl.transform import enriquecer_batidas


def test_carregar_sqlite(tmp_path):
    dados = gerar_dados(seed=42)
    enriquecidas = enriquecer_batidas(dados["batidas"])
    db = tmp_path / "hr.db"

    carregar_sqlite(dados, enriquecidas, db)

    conn = sqlite3.connect(db)
    tabelas = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"colaboradores", "batidas", "ajustes", "audit_log"} <= tabelas
    assert conn.execute("SELECT COUNT(*) FROM colaboradores").fetchone()[0] == 9
    assert conn.execute("SELECT COUNT(*) FROM batidas").fetchone()[0] == len(enriquecidas)
    assert conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 0
    # colunas enriquecidas presentes
    cols = {c[1] for c in conn.execute("PRAGMA table_info(batidas)")}
    assert {"atraso_minutos", "hora_extra_minutos", "batida_incompleta"} <= cols
    conn.close()


def test_recarga_e_idempotente(tmp_path):
    dados = gerar_dados(seed=42)
    enriquecidas = enriquecer_batidas(dados["batidas"])
    db = tmp_path / "hr.db"
    carregar_sqlite(dados, enriquecidas, db)
    carregar_sqlite(dados, enriquecidas, db)  # nao duplica
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM colaboradores").fetchone()[0] == 9
    conn.close()


def test_bigquery_degrada_sem_credencial(monkeypatch):
    import pandas as pd

    from etl.load import carregar_bigquery

    monkeypatch.delenv("GCP_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    ok = carregar_bigquery(pd.DataFrame({"equipe": ["X"], "mes": ["2026-06"]}))
    assert ok is False
