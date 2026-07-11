from mcp_server.analytics import analytics_rh, validar_sql


def test_sql_valida_passa():
    sql = ("SELECT equipe, SUM(total_hora_extra_minutos) AS extra "
           "FROM rh_analytics.agregados_mensais GROUP BY equipe")
    assert validar_sql(sql) is None


def test_rejeita_nao_select():
    erro = validar_sql("DELETE FROM rh_analytics.agregados_mensais WHERE 1=1")
    assert erro is not None and "SELECT" in erro


def test_rejeita_tabela_errada():
    erro = validar_sql("SELECT * FROM outro_dataset.salarios")
    assert erro is not None and "agregados_mensais" in erro


def test_rejeita_multiplos_statements():
    erro = validar_sql(
        "SELECT 1 FROM rh_analytics.agregados_mensais; DROP TABLE x")
    assert erro is not None


def test_rejeita_dml_embutida():
    erro = validar_sql(
        "SELECT * FROM rh_analytics.agregados_mensais WHERE 1=1 UNION ALL "
        "SELECT * FROM rh_analytics.agregados_mensais -- DROP")
    assert erro is not None  # comentario proibido


def test_degrada_sem_credencial(monkeypatch):
    monkeypatch.delenv("GCP_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    resultado = analytics_rh(
        "SELECT equipe FROM rh_analytics.agregados_mensais")
    assert "indisponível" in resultado.lower() or "indisponivel" in resultado.lower()


def test_rejeita_lista_de_tabelas_no_from():
    erro = validar_sql(
        "SELECT * FROM rh_analytics.agregados_mensais, outro_dataset.tabela")
    assert erro is not None


def test_rejeita_dataset_parecido():
    erro = validar_sql("SELECT * FROM notrh_analytics.my_agregados_mensais")
    assert erro is not None


def test_aceita_tabela_qualificada_com_projeto():
    sql = ("SELECT equipe FROM `meu-projeto.rh_analytics.agregados_mensais` "
           "GROUP BY equipe")
    assert validar_sql(sql) is None
