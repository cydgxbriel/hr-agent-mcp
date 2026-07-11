import sqlite3

import pytest

from etl.extract import gerar_dados
from etl.load import carregar_sqlite
from etl.transform import enriquecer_batidas
from mcp_server.db import aprovar_ajuste, consultar_batidas, listar_ajustes_pendentes


@pytest.fixture()
def db(tmp_path):
    dados = gerar_dados(seed=42)
    caminho = tmp_path / "hr.db"
    carregar_sqlite(dados, enriquecer_batidas(dados["batidas"]), caminho)
    return str(caminho)


def test_consultar_batidas_por_nome_parcial(db):
    conn = sqlite3.connect(db)
    nome = conn.execute(
        "SELECT nome FROM colaboradores WHERE id = 2").fetchone()[0]
    data = conn.execute(
        "SELECT data FROM batidas WHERE colaborador_id = 2 LIMIT 1").fetchone()[0]
    conn.close()

    primeiro_nome = nome.split()[0]
    resultado = consultar_batidas(primeiro_nome, data, data, db_path=db)
    assert nome in resultado
    assert data in resultado


def test_consultar_batidas_nome_inexistente(db):
    resultado = consultar_batidas("Zebrino Inexistente", "2026-06-01", "2026-06-30",
                                  db_path=db)
    assert "não encontrei" in resultado.lower()


def test_listar_ajustes_pendentes(db):
    resultado = listar_ajustes_pendentes(db_path=db)
    assert "pendente" in resultado.lower() or "#1" in resultado
    assert "motivo" in resultado.lower()


def test_aprovar_ajuste_atualiza_e_audita(db):
    resultado = aprovar_ajuste(1, "Justificativa válida, sistema fora do ar.", db_path=db)
    assert "aprovado" in resultado.lower()

    conn = sqlite3.connect(db)
    status = conn.execute("SELECT status FROM ajustes WHERE id = 1").fetchone()[0]
    assert status == "aprovado"
    campo, valor, colab_id, data = conn.execute(
        "SELECT campo, valor_proposto, colaborador_id, data FROM ajustes WHERE id = 1"
    ).fetchone()
    aplicado = conn.execute(
        f"SELECT {campo} FROM batidas WHERE colaborador_id = ? AND data = ?",
        (colab_id, data)).fetchone()[0]
    assert aplicado == valor
    trilha = conn.execute(
        "SELECT acao, autor FROM audit_log WHERE ajuste_id = 1").fetchone()
    assert trilha == ("aprovado", "Ana Souza (gestora)")
    conn.close()


def test_aprovar_ajuste_id_inexistente(db):
    resultado = aprovar_ajuste(9999, "tanto faz", db_path=db)
    assert "não encontrei" in resultado.lower() or "não existe" in resultado.lower()


def test_aprovar_ajuste_ja_aprovado(db):
    aprovar_ajuste(1, "primeira vez", db_path=db)
    resultado = aprovar_ajuste(1, "segunda vez", db_path=db)
    assert "já" in resultado.lower()
