import pandas as pd

from etl.extract import gerar_dados


def test_reproduzivel_com_seed():
    a = gerar_dados(seed=42)
    b = gerar_dados(seed=42)
    for chave in ("colaboradores", "batidas", "ajustes"):
        pd.testing.assert_frame_equal(a[chave], b[chave])


def test_estrutura_colaboradores():
    dados = gerar_dados(seed=42)
    colab = dados["colaboradores"]
    assert len(colab) == 9  # 1 gestora + 8
    gestora = colab[colab["id"] == 1].iloc[0]
    assert gestora["nome"] == "Ana Souza"
    assert pd.isna(gestora["gestor_id"])
    assert (colab[colab["id"] != 1]["gestor_id"] == 1).all()


def test_anomalias_plantadas():
    dados = gerar_dados(seed=42)
    batidas = dados["batidas"]
    ajustes = dados["ajustes"]
    # batidas faltantes existem
    assert batidas["entrada"].isna().sum() + batidas["saida"].isna().sum() > 0
    # atrasos existem (entrada depois de 09:10)
    entradas = batidas["entrada"].dropna()
    assert (entradas > "09:10").sum() >= 5
    # 3-4 ajustes pendentes
    pendentes = ajustes[ajustes["status"] == "pendente"]
    assert 3 <= len(pendentes) <= 4
