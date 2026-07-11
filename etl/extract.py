"""Extract: gera dados sinteticos de ponto (Faker, seed fixa) e salva CSVs brutos."""

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from faker import Faker

EQUIPES = ["Produto", "Engenharia", "Comercial"]
CARGOS = ["Analista", "Especialista", "Coordenador"]
DIAS_DE_HISTORICO = 60


def _hora(h: int, m: int) -> str:
    return f"{h:02d}:{m:02d}"


def gerar_dados(seed: int = 42) -> dict[str, pd.DataFrame]:
    rng = random.Random(seed)
    fake = Faker("pt_BR")
    Faker.seed(seed)

    colaboradores = [
        {"id": 1, "nome": "Ana Souza", "cargo": "Gerente de RH", "equipe": "Gestão",
         "gestor_id": pd.NA}
    ]
    for i in range(2, 10):
        colaboradores.append({
            "id": i, "nome": fake.name(), "cargo": rng.choice(CARGOS),
            "equipe": rng.choice(EQUIPES), "gestor_id": 1,
        })

    batidas: list[dict] = []
    ajustes: list[dict] = []
    fim = date(2026, 7, 10)
    dias = [fim - timedelta(days=d) for d in range(DIAS_DE_HISTORICO)]
    dias_uteis = sorted(d for d in dias if d.weekday() < 5)

    batida_id = 1
    for colab in colaboradores[1:]:
        for dia in dias_uteis:
            if rng.random() < 0.03:  # ausencia completa
                continue
            atraso = rng.choice([0, 0, 0, 0, 0, 5, 12, 25, 40])
            entrada = _hora(9 + (atraso + rng.randint(0, 3)) // 60,
                            (atraso + rng.randint(0, 3)) % 60)
            extra = rng.choice([0, 0, 0, 15, 45, 90])
            saida = _hora(18 + extra // 60, extra % 60)
            registro = {
                "id": batida_id, "colaborador_id": colab["id"],
                "data": dia.isoformat(), "entrada": entrada,
                "saida_almoco": _hora(12, rng.randint(0, 15)),
                "volta_almoco": _hora(13, rng.randint(0, 15)),
                "saida": saida,
            }
            if rng.random() < 0.04:  # batida faltante
                registro[rng.choice(["entrada", "saida"])] = None
            batidas.append(registro)
            batida_id += 1

    faltantes = [b for b in batidas if b["entrada"] is None or b["saida"] is None]
    for i, registro in enumerate(rng.sample(faltantes, k=4), start=1):
        campo = "entrada" if registro["entrada"] is None else "saida"
        ajustes.append({
            "id": i, "colaborador_id": registro["colaborador_id"],
            "data": registro["data"], "campo": campo,
            "valor_proposto": "09:00" if campo == "entrada" else "18:00",
            "motivo": rng.choice([
                "Esqueci de bater o ponto na entrada.",
                "Sistema de ponto estava fora do ar.",
                "Estava em reunião externa com cliente.",
                "Trabalhei de home office e registrei mais tarde.",
            ]),
            "status": "pendente",
        })

    return {
        "colaboradores": pd.DataFrame(colaboradores),
        "batidas": pd.DataFrame(batidas),
        "ajustes": pd.DataFrame(ajustes),
    }


def salvar_csvs(dados: dict[str, pd.DataFrame], pasta: str | Path) -> None:
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    for nome, df in dados.items():
        df.to_csv(pasta / f"{nome}.csv", index=False)
