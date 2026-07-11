"""Transform: enriquece batidas (atraso, hora extra) e gera agregados mensais."""

import pandas as pd

ENTRADA_PADRAO = 9 * 60      # 09:00 em minutos
TOLERANCIA_MIN = 10
SAIDA_PADRAO = 18 * 60       # 18:00 em minutos


def _minutos(horario: str | None) -> int | None:
    if horario is None or pd.isna(horario):
        return None
    h, m = str(horario).split(":")
    return int(h) * 60 + int(m)


def enriquecer_batidas(batidas: pd.DataFrame) -> pd.DataFrame:
    enr = batidas.copy()
    entrada = enr["entrada"].map(_minutos)
    saida = enr["saida"].map(_minutos)

    enr["atraso_minutos"] = [
        (e - ENTRADA_PADRAO) if e is not None and e > ENTRADA_PADRAO + TOLERANCIA_MIN else 0
        for e in entrada
    ]
    enr["hora_extra_minutos"] = [
        (s - SAIDA_PADRAO) if s is not None and s > SAIDA_PADRAO else 0
        for s in saida
    ]
    campos = ["entrada", "saida_almoco", "volta_almoco", "saida"]
    enr["batida_incompleta"] = enr[campos].isna().any(axis=1)
    return enr


def agregados_mensais(
    batidas_enriquecidas: pd.DataFrame, colaboradores: pd.DataFrame
) -> pd.DataFrame:
    df = batidas_enriquecidas.merge(
        colaboradores[["id", "equipe"]], left_on="colaborador_id", right_on="id",
        suffixes=("", "_colab"),
    )
    df["mes"] = df["data"].str.slice(0, 7)
    agg = (
        df.groupby(["equipe", "mes"])
        .agg(
            total_atraso_minutos=("atraso_minutos", "sum"),
            total_hora_extra_minutos=("hora_extra_minutos", "sum"),
            batidas_incompletas=("batida_incompleta", "sum"),
            colaboradores=("colaborador_id", "nunique"),
        )
        .reset_index()
    )
    for coluna in ("total_atraso_minutos", "total_hora_extra_minutos", "batidas_incompletas"):
        agg[coluna] = agg[coluna].astype(int)
    return agg
