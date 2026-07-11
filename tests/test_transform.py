import pandas as pd

from etl.transform import agregados_mensais, enriquecer_batidas


def _batidas_exemplo() -> pd.DataFrame:
    return pd.DataFrame([
        {"id": 1, "colaborador_id": 2, "data": "2026-06-01", "entrada": "09:05",
         "saida_almoco": "12:00", "volta_almoco": "13:00", "saida": "18:00"},
        {"id": 2, "colaborador_id": 2, "data": "2026-06-02", "entrada": "09:25",
         "saida_almoco": "12:00", "volta_almoco": "13:00", "saida": "19:30"},
        {"id": 3, "colaborador_id": 3, "data": "2026-06-02", "entrada": None,
         "saida_almoco": "12:00", "volta_almoco": "13:00", "saida": "18:00"},
    ])


def test_enriquecer_batidas():
    enr = enriquecer_batidas(_batidas_exemplo())
    assert enr.loc[0, "atraso_minutos"] == 0        # dentro da tolerancia
    assert enr.loc[1, "atraso_minutos"] == 25       # acima de 09:10 conta desde 09:00
    assert enr.loc[1, "hora_extra_minutos"] == 90
    assert not bool(enr.loc[0, "batida_incompleta"])
    assert bool(enr.loc[2, "batida_incompleta"])
    assert enr.loc[2, "atraso_minutos"] == 0        # sem entrada, sem atraso


def test_agregados_mensais():
    colaboradores = pd.DataFrame([
        {"id": 2, "nome": "B", "cargo": "Analista", "equipe": "Produto", "gestor_id": 1},
        {"id": 3, "nome": "C", "cargo": "Analista", "equipe": "Produto", "gestor_id": 1},
    ])
    agg = agregados_mensais(enriquecer_batidas(_batidas_exemplo()), colaboradores)
    linha = agg[(agg["equipe"] == "Produto") & (agg["mes"] == "2026-06")].iloc[0]
    assert linha["total_atraso_minutos"] == 25
    assert linha["total_hora_extra_minutos"] == 90
    assert linha["batidas_incompletas"] == 1
    assert linha["colaboradores"] == 2
