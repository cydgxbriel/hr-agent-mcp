# hr-agent-mcp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** POC pública de agente conversacional de RH (ponto) com servidor MCP real, LangGraph com human-in-the-loop, RAG, ETL para BigQuery e chat Streamlit com demo online.

**Architecture:** Streamlit → agente LangGraph (ReAct, checkpointer, interrupt antes de escrita) → servidor MCP (FastMCP, stdio) com 5 tools → SQLite (operacional), FAISS (políticas) e BigQuery (analítico, alimentado por ETL Python). Lógica de negócio vive em funções puras testáveis; o servidor MCP e o agente são camadas finas por cima.

**Tech Stack:** Python ≥3.11, uv, FastMCP (`mcp`), LangGraph, langchain-openai, langchain-mcp-adapters, FAISS (faiss-cpu), pandas, Faker, google-cloud-bigquery, Streamlit, pytest, ruff.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-10-hr-agent-mcp-design.md`.
- LLM: OpenAI `gpt-4o-mini`. Embeddings: `text-embedding-3-small`.
- Dados sintéticos com **seed fixa 42** (reproduzível): 1 gestora + 8 colaboradores, 60 dias de batidas com anomalias plantadas (atrasos, batidas faltantes, 3–4 ajustes pendentes).
- SQLite = operacional (leitura E escrita); BigQuery = analítico **read-only** (sandbox não suporta DML); dataset `rh_analytics`, tabela `agregados_mensais`.
- Toda escrita passa por confirmação humana (interrupt do LangGraph) e registra em `audit_log`.
- Tools MCP nunca vazam traceback cru: erros viram mensagens claras em pt-BR.
- BigQuery/OpenAI indisponíveis → degradação graciosa, nunca crash.
- Idioma de código: identificadores em pt-BR (domínio) — consistente em todo o repo. Docstrings das tools MCP em pt-BR e ricas (o LLM roteia por elas).
- Env vars: `OPENAI_API_KEY`, `APP_PASSWORD`, `GCP_PROJECT_ID`, `GCP_SERVICE_ACCOUNT_JSON` (JSON inline) *ou* `GOOGLE_APPLICATION_CREDENTIALS` (path), `HR_DB_PATH` (default `data/hr.db`), `LANGSMITH_TRACING`/`LANGSMITH_API_KEY` opcionais.
- Commits atômicos por task; mensagens `feat:`/`test:`/`docs:`/`ci:`.
- CI roda apenas ruff + pytest (sem segredos; nada de OpenAI/BigQuery reais em teste).

## File Structure

```
hr-agent-mcp/
├── pyproject.toml            # uv, deps, ruff, pytest
├── .gitignore                # .env, data/hr.db, data/raw/, .venv, __pycache__
├── .env.example
├── README.md                 # Task 11
├── DEMO.md                   # Task 11
├── .github/workflows/ci.yml  # Task 10
├── core/
│   └── bq.py                 # get_bq_client() compartilhado (ETL + analytics)
├── etl/
│   ├── extract.py            # dados sintéticos (Faker, seed 42) → data/raw/*.csv
│   ├── transform.py          # atrasos, horas extras, agregados mensais
│   ├── load.py               # SQLite + load job BigQuery
│   └── pipeline.py           # python -m etl.pipeline
├── mcp_server/
│   ├── db.py                 # lógica de negócio pura sobre SQLite (testável)
│   ├── analytics.py          # validação SQL + consulta BigQuery
│   └── server.py             # FastMCP: 5 tools (camada fina)
├── rag/
│   └── index.py              # build_index(), buscar_politica()
├── agent/
│   └── graph.py              # build_agent(): ReAct + interrupt em aprovar_ajuste
├── app/
│   └── main.py               # Streamlit: gate de senha, chat, painel MCP
├── data/
│   └── politicas/            # 3 .md fictícios (committed)
└── tests/
    ├── test_extract.py
    ├── test_transform.py
    ├── test_load.py
    ├── test_mcp_db.py
    ├── test_analytics.py
    └── test_rag.py
```

---

### Task 1: Scaffold do projeto

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `core/__init__.py`, `etl/__init__.py`, `mcp_server/__init__.py`, `rag/__init__.py`, `agent/__init__.py`, `app/__init__.py`, `tests/__init__.py`

**Interfaces:**
- Consumes: nada.
- Produces: ambiente `uv` instalável; pacotes vazios importáveis; `uv run pytest` e `uv run ruff check .` funcionam.

- [ ] **Step 1: Criar `pyproject.toml`**

```toml
[project]
name = "hr-agent-mcp"
version = "0.1.0"
description = "Agente conversacional de RH com MCP, LangGraph, RAG e BigQuery"
requires-python = ">=3.11"
dependencies = [
    "streamlit>=1.40",
    "langgraph>=0.2.60",
    "langchain-openai>=0.2.10",
    "langchain-mcp-adapters>=0.1.0",
    "langchain-community>=0.3.10",
    "mcp>=1.2.0",
    "faiss-cpu>=1.8.0",
    "pandas>=2.2",
    "pyarrow>=17.0",
    "faker>=30.0",
    "google-cloud-bigquery>=3.25",
    "python-dotenv>=1.0",
]

[dependency-groups]
dev = ["pytest>=8.0", "pytest-asyncio>=0.24", "ruff>=0.6"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "W"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.setuptools]
packages = ["core", "etl", "mcp_server", "rag", "agent", "app"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

- [ ] **Step 2: Criar `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.env
data/hr.db
data/raw/
.pytest_cache/
.ruff_cache/
*.egg-info/
.streamlit/secrets.toml
```

- [ ] **Step 3: Criar `.env.example`**

```
OPENAI_API_KEY=sk-...
APP_PASSWORD=troque-me
HR_DB_PATH=data/hr.db
# BigQuery (opcional — sem isso, analytics degrada graciosamente)
GCP_PROJECT_ID=
GOOGLE_APPLICATION_CREDENTIALS=
# ou, para Streamlit Cloud, o JSON inline:
GCP_SERVICE_ACCOUNT_JSON=
# Observabilidade (opcional)
LANGSMITH_TRACING=false
LANGSMITH_API_KEY=
```

- [ ] **Step 4: Criar pacotes vazios**

Criar `core/__init__.py`, `etl/__init__.py`, `mcp_server/__init__.py`, `rag/__init__.py`, `agent/__init__.py`, `app/__init__.py`, `tests/__init__.py` — todos vazios.

- [ ] **Step 5: Instalar e verificar**

Run: `uv sync && uv run ruff check . && uv run pytest`
Expected: sync ok; ruff sem erros; pytest `no tests ran` (exit code 5 é aceitável aqui).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore .env.example core etl mcp_server rag agent app tests uv.lock
git commit -m "feat: scaffold do projeto (uv, ruff, pytest, pacotes)"
```

---

### Task 2: ETL — extract (dados sintéticos)

**Files:**
- Create: `etl/extract.py`
- Test: `tests/test_extract.py`

**Interfaces:**
- Consumes: nada.
- Produces: `gerar_dados(seed: int = 42) -> dict[str, pd.DataFrame]` com chaves `"colaboradores"`, `"batidas"`, `"ajustes"`; `salvar_csvs(dados: dict, pasta: str | Path) -> None`.
  - `colaboradores`: colunas `id:int, nome:str, cargo:str, equipe:str, gestor_id:int|NA` (id 1 = gestora Ana Souza, gestor_id NA).
  - `batidas`: colunas `id:int, colaborador_id:int, data:str YYYY-MM-DD, entrada:str|None, saida_almoco:str|None, volta_almoco:str|None, saida:str|None` (horários `HH:MM`; None = batida faltante).
  - `ajustes`: colunas `id:int, colaborador_id:int, data:str, campo:str, valor_proposto:str, motivo:str, status:str` (status inicial `"pendente"`).

- [ ] **Step 1: Escrever teste que falha**

`tests/test_extract.py`:

```python
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
```

- [ ] **Step 2: Rodar teste para ver falhar**

Run: `uv run pytest tests/test_extract.py -v`
Expected: FAIL — `ModuleNotFoundError` ou `ImportError: cannot import name 'gerar_dados'`.

- [ ] **Step 3: Implementar `etl/extract.py`**

```python
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
```

Nota: o teste exige 3–4 pendentes e ≥5 atrasos; se com seed 42 `faltantes` tiver menos de 4 registros ou os atrasos não baterem, ajuste as probabilidades (0.04→0.06; pesos de `atraso`) até o teste passar — os dados são sintéticos, a distribuição é nossa.

- [ ] **Step 4: Rodar testes até passar**

Run: `uv run pytest tests/test_extract.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add etl/extract.py tests/test_extract.py
git commit -m "feat: extract de dados sinteticos de ponto com anomalias plantadas"
```

---

### Task 3: ETL — transform (atrasos, horas extras, agregados)

**Files:**
- Create: `etl/transform.py`
- Test: `tests/test_transform.py`

**Interfaces:**
- Consumes: DataFrames de `gerar_dados()` (Task 2).
- Produces:
  - `enriquecer_batidas(batidas: pd.DataFrame) -> pd.DataFrame` — adiciona `atraso_minutos:int`, `hora_extra_minutos:int`, `batida_incompleta:bool`.
  - `agregados_mensais(batidas_enriquecidas: pd.DataFrame, colaboradores: pd.DataFrame) -> pd.DataFrame` — colunas `equipe:str, mes:str YYYY-MM, total_atraso_minutos:int, total_hora_extra_minutos:int, batidas_incompletas:int, colaboradores:int`.
- Regras: expediente 09:00–18:00; tolerância de 10 min (atraso só conta acima de 09:10, e conta desde 09:00); hora extra = minutos após 18:00; batida incompleta = qualquer campo de horário nulo.

- [ ] **Step 1: Escrever teste que falha**

`tests/test_transform.py`:

```python
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
```

- [ ] **Step 2: Rodar teste para ver falhar**

Run: `uv run pytest tests/test_transform.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implementar `etl/transform.py`**

```python
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
```

- [ ] **Step 4: Rodar testes até passar**

Run: `uv run pytest tests/test_transform.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add etl/transform.py tests/test_transform.py
git commit -m "feat: transform com atraso, hora extra e agregados mensais"
```

---

### Task 4: ETL — load (SQLite + BigQuery) e pipeline

**Files:**
- Create: `core/bq.py`, `etl/load.py`, `etl/pipeline.py`
- Test: `tests/test_load.py`

**Interfaces:**
- Consumes: `gerar_dados`, `salvar_csvs` (Task 2); `enriquecer_batidas`, `agregados_mensais` (Task 3).
- Produces:
  - `core.bq.get_bq_client() -> "bigquery.Client | None"` — None se não houver credencial (`GCP_SERVICE_ACCOUNT_JSON` ou `GOOGLE_APPLICATION_CREDENTIALS` + `GCP_PROJECT_ID`).
  - `etl.load.carregar_sqlite(dados: dict, batidas_enriquecidas: pd.DataFrame, db_path: str | Path) -> None` — cria tabelas `colaboradores`, `batidas` (já enriquecidas), `ajustes`, `audit_log` (vazia).
  - `etl.load.carregar_bigquery(agregados: pd.DataFrame) -> bool` — True se carregou; False se sem credencial (mensagem no stdout, sem exceção).
  - CLI: `uv run python -m etl.pipeline` roda extract → transform → load completo.
- Schema `audit_log`: `id INTEGER PRIMARY KEY AUTOINCREMENT, ajuste_id INTEGER, acao TEXT, justificativa TEXT, autor TEXT, criado_em TEXT`.

- [ ] **Step 1: Escrever teste que falha**

`tests/test_load.py`:

```python
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
```

- [ ] **Step 2: Rodar teste para ver falhar**

Run: `uv run pytest tests/test_load.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implementar `core/bq.py`**

```python
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
```

- [ ] **Step 4: Implementar `etl/load.py`**

```python
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
```

- [ ] **Step 5: Implementar `etl/pipeline.py`**

```python
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
    carregar_bigquery(agregados)
    print(f"Pipeline concluido. SQLite em {db_path}.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Rodar testes e o pipeline**

Run: `uv run pytest tests/test_load.py -v && uv run python -m etl.pipeline`
Expected: 3 PASS; pipeline imprime as 3 etapas, cria `data/hr.db` e pula BigQuery se sem credencial.

- [ ] **Step 7: Commit**

```bash
git add core/bq.py etl/load.py etl/pipeline.py tests/test_load.py
git commit -m "feat: load SQLite/BigQuery e pipeline ETL executavel"
```

---

### Task 5: Lógica operacional das tools (mcp_server/db.py)

**Files:**
- Create: `mcp_server/db.py`
- Test: `tests/test_mcp_db.py`

**Interfaces:**
- Consumes: SQLite criado por `carregar_sqlite` (Task 4). Path via env `HR_DB_PATH` (default `data/hr.db`), sobrescritível por parâmetro.
- Produces (todas retornam `str` em pt-BR pronto pro LLM; nunca levantam exceção pro chamador):
  - `consultar_batidas(nome_colaborador: str, data_inicio: str, data_fim: str, db_path: str | None = None) -> str`
  - `listar_ajustes_pendentes(db_path: str | None = None) -> str`
  - `aprovar_ajuste(ajuste_id: int, justificativa: str, db_path: str | None = None) -> str` — atualiza `ajustes.status='aprovado'`, aplica `valor_proposto` na batida correspondente e insere em `audit_log` (autor fixo `"Ana Souza (gestora)"`).

- [ ] **Step 1: Escrever teste que falha**

`tests/test_mcp_db.py`:

```python
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
```

- [ ] **Step 2: Rodar teste para ver falhar**

Run: `uv run pytest tests/test_mcp_db.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implementar `mcp_server/db.py`**

```python
"""Logica de negocio das tools operacionais, pura e testavel (SQLite)."""

import os
import sqlite3
from datetime import datetime, timezone


def _conectar(db_path: str | None) -> sqlite3.Connection:
    caminho = db_path or os.environ.get("HR_DB_PATH", "data/hr.db")
    conn = sqlite3.connect(caminho)
    conn.row_factory = sqlite3.Row
    return conn


def consultar_batidas(
    nome_colaborador: str, data_inicio: str, data_fim: str, db_path: str | None = None
) -> str:
    try:
        conn = _conectar(db_path)
        colab = conn.execute(
            "SELECT id, nome FROM colaboradores WHERE nome LIKE ? AND id != 1",
            (f"%{nome_colaborador}%",),
        ).fetchone()
        if colab is None:
            conn.close()
            return (f"Não encontrei colaborador com nome parecido com "
                    f"'{nome_colaborador}' na equipe.")
        linhas = conn.execute(
            """SELECT data, entrada, saida_almoco, volta_almoco, saida,
                      atraso_minutos, hora_extra_minutos, batida_incompleta
               FROM batidas
               WHERE colaborador_id = ? AND data BETWEEN ? AND ?
               ORDER BY data""",
            (colab["id"], data_inicio, data_fim),
        ).fetchall()
        conn.close()
        if not linhas:
            return (f"{colab['nome']} não tem batidas registradas entre "
                    f"{data_inicio} e {data_fim}.")
        saida = [f"Batidas de {colab['nome']} ({data_inicio} a {data_fim}):",
                 "data | entrada | almoço | volta | saída | atraso(min) | extra(min)"]
        for r in linhas:
            alerta = " ⚠️ INCOMPLETA" if r["batida_incompleta"] else ""
            saida.append(
                f"{r['data']} | {r['entrada'] or '—'} | {r['saida_almoco'] or '—'} | "
                f"{r['volta_almoco'] or '—'} | {r['saida'] or '—'} | "
                f"{r['atraso_minutos']} | {r['hora_extra_minutos']}{alerta}")
        return "\n".join(saida)
    except Exception as exc:  # noqa: BLE001 — tool nunca vaza traceback
        return f"Erro ao consultar batidas: {type(exc).__name__}. Tente novamente."


def listar_ajustes_pendentes(db_path: str | None = None) -> str:
    try:
        conn = _conectar(db_path)
        linhas = conn.execute(
            """SELECT a.id, c.nome, a.data, a.campo, a.valor_proposto, a.motivo
               FROM ajustes a JOIN colaboradores c ON c.id = a.colaborador_id
               WHERE a.status = 'pendente' ORDER BY a.data""",
        ).fetchall()
        conn.close()
        if not linhas:
            return "Não há ajustes de ponto pendentes de aprovação. 🎉"
        saida = [f"Há {len(linhas)} ajuste(s) pendente(s):"]
        for r in linhas:
            saida.append(
                f"#{r['id']} — {r['nome']} | {r['data']} | corrigir '{r['campo']}' "
                f"para {r['valor_proposto']} | motivo: {r['motivo']}")
        return "\n".join(saida)
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao listar ajustes: {type(exc).__name__}. Tente novamente."


def aprovar_ajuste(
    ajuste_id: int, justificativa: str, db_path: str | None = None
) -> str:
    try:
        conn = _conectar(db_path)
        ajuste = conn.execute(
            "SELECT * FROM ajustes WHERE id = ?", (ajuste_id,)).fetchone()
        if ajuste is None:
            conn.close()
            return f"Não encontrei ajuste com id {ajuste_id}."
        if ajuste["status"] != "pendente":
            conn.close()
            return f"O ajuste #{ajuste_id} já foi processado (status: {ajuste['status']})."

        campo = ajuste["campo"]
        if campo not in ("entrada", "saida_almoco", "volta_almoco", "saida"):
            conn.close()
            return f"Campo de ajuste inválido: {campo}."
        conn.execute(
            f"UPDATE batidas SET {campo} = ? WHERE colaborador_id = ? AND data = ?",
            (ajuste["valor_proposto"], ajuste["colaborador_id"], ajuste["data"]))
        conn.execute("UPDATE ajustes SET status = 'aprovado' WHERE id = ?", (ajuste_id,))
        conn.execute(
            """INSERT INTO audit_log (ajuste_id, acao, justificativa, autor, criado_em)
               VALUES (?, 'aprovado', ?, 'Ana Souza (gestora)', ?)""",
            (ajuste_id, justificativa, datetime.now(timezone.utc).isoformat()))
        conn.commit()
        conn.close()
        return (f"Ajuste #{ajuste_id} aprovado: '{campo}' corrigido para "
                f"{ajuste['valor_proposto']} em {ajuste['data']}. "
                f"Registrado na trilha de auditoria.")
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao aprovar ajuste: {type(exc).__name__}. Nada foi gravado."
```

- [ ] **Step 4: Rodar testes até passar**

Run: `uv run pytest tests/test_mcp_db.py -v`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add mcp_server/db.py tests/test_mcp_db.py
git commit -m "feat: logica operacional de batidas, ajustes e auditoria"
```

---

### Task 6: RAG — políticas fictícias + índice FAISS

**Files:**
- Create: `data/politicas/politica-de-ponto.md`, `data/politicas/banco-de-horas.md`, `data/politicas/home-office.md`, `rag/index.py`
- Test: `tests/test_rag.py`

**Interfaces:**
- Consumes: nada dos módulos anteriores.
- Produces:
  - `rag.index.build_index(pasta: str | Path = "data/politicas", embeddings=None) -> FAISS` — `embeddings=None` usa `OpenAIEmbeddings(model="text-embedding-3-small")`; injetável para teste.
  - `rag.index.buscar_politica(pergunta: str, indice: FAISS, k: int = 3) -> str` — trechos concatenados com a fonte (`[fonte: politica-de-ponto.md]`).

- [ ] **Step 1: Criar os 3 documentos de política**

`data/politicas/politica-de-ponto.md`:

```markdown
# Política de Registro de Ponto — Empresa Fictícia Demo

> Documento fictício criado para fins de demonstração. Não representa nenhuma empresa real.

## Jornada padrão
A jornada padrão é de 8 horas diárias, das 09:00 às 18:00, com 1 hora de almoço
(12:00–13:00), de segunda a sexta-feira.

## Tolerância de atraso
Há tolerância de 10 minutos na entrada. Entradas após 09:10 são contabilizadas
como atraso desde as 09:00 e entram no relatório mensal do gestor.

## Batidas obrigatórias
São obrigatórias 4 batidas diárias: entrada, saída para almoço, retorno do almoço
e saída. Batida faltante gera pendência que deve ser regularizada via ajuste.

## Ajuste de batida
O colaborador pode solicitar ajuste de batida em até 5 dias úteis após a ocorrência,
informando o motivo. Todo ajuste exige aprovação do gestor imediato e fica
registrado em trilha de auditoria, com data, autor e justificativa.
O gestor deve analisar ajustes pendentes em até 3 dias úteis.

## Reincidência
Três ou mais atrasos não justificados no mesmo mês geram advertência formal
conforme o regimento interno.
```

`data/politicas/banco-de-horas.md`:

```markdown
# Política de Banco de Horas — Empresa Fictícia Demo

> Documento fictício criado para fins de demonstração.

## Acúmulo
Horas extras autorizadas são creditadas no banco de horas com fator 1,2
(cada hora extra vale 1h12 de folga). Horas extras precisam de autorização
prévia do gestor, exceto em incidentes críticos.

## Limite
O saldo máximo do banco de horas é de 40 horas. Acima disso, as horas
excedentes são pagas na folha do mês seguinte com adicional de 50%.

## Compensação
O saldo deve ser compensado em até 6 meses. Folgas de compensação devem ser
combinadas com o gestor com pelo menos 2 dias úteis de antecedência.

## Saída antecipada
Saídas antes das 18:00 debitam o banco de horas, exceto quando previamente
acordadas como compensação.
```

`data/politicas/home-office.md`:

```markdown
# Política de Trabalho Remoto — Empresa Fictícia Demo

> Documento fictício criado para fins de demonstração.

## Modelo híbrido
O modelo padrão é híbrido: 3 dias presenciais (terça a quinta) e 2 dias remotos
(segunda e sexta), salvo acordo diferente com o gestor.

## Registro de ponto no remoto
O registro de ponto é obrigatório também nos dias remotos, pelo aplicativo,
nos mesmos horários da jornada padrão.

## Falha de sistema
Se o aplicativo de ponto estiver indisponível, o colaborador deve comunicar o
gestor no mesmo dia e solicitar ajuste de batida com o motivo
"sistema fora do ar". Esses ajustes têm aprovação simplificada.

## Elegibilidade
Colaboradores em período de experiência trabalham presencialmente durante os
primeiros 90 dias.
```

- [ ] **Step 2: Escrever teste que falha**

`tests/test_rag.py`:

```python
from langchain_core.embeddings import DeterministicFakeEmbedding

from rag.index import build_index, buscar_politica


def test_index_e_busca_com_fake_embeddings():
    indice = build_index("data/politicas",
                         embeddings=DeterministicFakeEmbedding(size=64))
    resultado = buscar_politica("qual a tolerância de atraso?", indice, k=3)
    assert "[fonte:" in resultado
    assert len(resultado) > 100


def test_chunks_carregam_os_tres_documentos():
    indice = build_index("data/politicas",
                         embeddings=DeterministicFakeEmbedding(size=64))
    fontes = {d.metadata["fonte"] for d in indice.docstore._dict.values()}
    assert fontes == {"politica-de-ponto.md", "banco-de-horas.md", "home-office.md"}
```

- [ ] **Step 3: Rodar teste para ver falhar**

Run: `uv run pytest tests/test_rag.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 4: Implementar `rag/index.py`**

```python
"""RAG sobre as politicas de RH: chunking + indice FAISS em memoria."""

from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def build_index(pasta: str | Path = "data/politicas", embeddings=None) -> FAISS:
    if embeddings is None:
        from langchain_openai import OpenAIEmbeddings

        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    documentos: list[Document] = []
    for arquivo in sorted(Path(pasta).glob("*.md")):
        for trecho in splitter.split_text(arquivo.read_text(encoding="utf-8")):
            documentos.append(
                Document(page_content=trecho, metadata={"fonte": arquivo.name}))
    return FAISS.from_documents(documentos, embeddings)


def buscar_politica(pergunta: str, indice: FAISS, k: int = 3) -> str:
    resultados = indice.similarity_search(pergunta, k=k)
    if not resultados:
        return "Não encontrei nada relevante nas políticas internas."
    blocos = [f"{doc.page_content}\n[fonte: {doc.metadata['fonte']}]"
              for doc in resultados]
    return "\n\n---\n\n".join(blocos)
```

Nota: `langchain-text-splitters` vem como dependência transitiva de `langchain-community`; se o import falhar, adicione `"langchain-text-splitters>=0.3"` ao `pyproject.toml`.

- [ ] **Step 5: Rodar testes até passar**

Run: `uv run pytest tests/test_rag.py -v`
Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add data/politicas rag/index.py tests/test_rag.py
git commit -m "feat: RAG de politicas de RH com FAISS e embeddings injetaveis"
```

---

### Task 7: Analytics BigQuery com validação de SQL

**Files:**
- Create: `mcp_server/analytics.py`
- Test: `tests/test_analytics.py`

**Interfaces:**
- Consumes: `core.bq.get_bq_client()` (Task 4).
- Produces:
  - `validar_sql(sql: str) -> str | None` — retorna mensagem de erro ou None se válida. Regras: statement único, começa com SELECT, referencia apenas `rh_analytics.agregados_mensais`, proíbe `;`, DML/DDL (INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/MERGE/TRUNCATE) e comentários (`--`, `/*`).
  - `analytics_rh(consulta_sql: str) -> str` — valida, executa no BigQuery, retorna resultado formatado (máx. 50 linhas) ou mensagem de degradação se sem credencial.
  - `SCHEMA_AGREGADOS: str` — descrição textual do schema para compor a docstring da tool (Task 8).

- [ ] **Step 1: Escrever teste que falha**

`tests/test_analytics.py`:

```python
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
```

- [ ] **Step 2: Rodar teste para ver falhar**

Run: `uv run pytest tests/test_analytics.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implementar `mcp_server/analytics.py`**

```python
"""Camada analitica: validacao de SQL gerada pelo LLM + consulta ao BigQuery."""

import re

from core.bq import get_bq_client

TABELA_PERMITIDA = "rh_analytics.agregados_mensais"

SCHEMA_AGREGADOS = (
    "Tabela rh_analytics.agregados_mensais (BigQuery, somente leitura): "
    "equipe STRING (Produto, Engenharia, Comercial), mes STRING 'YYYY-MM', "
    "total_atraso_minutos INT64, total_hora_extra_minutos INT64, "
    "batidas_incompletas INT64, colaboradores INT64."
)

_PROIBIDOS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|MERGE|TRUNCATE|GRANT)\b", re.IGNORECASE)
_REF_TABELA = re.compile(r"\b(?:FROM|JOIN)\s+([`\w.\-]+)", re.IGNORECASE)


def validar_sql(sql: str) -> str | None:
    limpa = sql.strip()
    if ";" in limpa:
        return "Apenas um statement é permitido (sem ';')."
    if "--" in limpa or "/*" in limpa:
        return "Comentários não são permitidos na consulta."
    if not limpa.upper().startswith("SELECT"):
        return "Apenas consultas SELECT são permitidas."
    if _PROIBIDOS.search(limpa):
        return "A consulta contém comandos proibidos — apenas SELECT é permitido."
    tabelas = {t.strip("`") for t in _REF_TABELA.findall(limpa)}
    if not tabelas:
        return f"A consulta precisa referenciar a tabela {TABELA_PERMITIDA}."
    for tabela in tabelas:
        if not tabela.endswith("agregados_mensais") or "rh_analytics" not in tabela:
            return (f"Tabela '{tabela}' não permitida. "
                    f"Use apenas {TABELA_PERMITIDA}.")
    return None


def analytics_rh(consulta_sql: str) -> str:
    erro = validar_sql(consulta_sql)
    if erro:
        return f"Consulta rejeitada pela camada de governança: {erro}"

    cliente = get_bq_client()
    if cliente is None:
        return ("A camada analítica (BigQuery) está indisponível no momento — "
                "credenciais não configuradas. As consultas operacionais de "
                "batidas e ajustes seguem funcionando.")
    try:
        linhas = list(cliente.query(consulta_sql).result(max_results=50))
        if not linhas:
            return "A consulta executou, mas não retornou linhas."
        colunas = list(linhas[0].keys())
        saida = [" | ".join(colunas)]
        for linha in linhas:
            saida.append(" | ".join(str(linha[c]) for c in colunas))
        return "\n".join(saida)
    except Exception as exc:  # noqa: BLE001 — tool nunca vaza traceback
        return f"Erro ao consultar o BigQuery: {type(exc).__name__}: {exc}"
```

- [ ] **Step 4: Rodar testes até passar**

Run: `uv run pytest tests/test_analytics.py -v`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add mcp_server/analytics.py tests/test_analytics.py
git commit -m "feat: analytics BigQuery com validacao de SQL (governanca)"
```

---

### Task 8: Servidor MCP (FastMCP, 5 tools)

**Files:**
- Create: `mcp_server/server.py`
- Test: manual (smoke test via CLI abaixo; a lógica já está testada nas Tasks 5–7)

**Interfaces:**
- Consumes: `mcp_server.db` (Task 5), `rag.index` (Task 6), `mcp_server.analytics` (Task 7).
- Produces: servidor MCP executável com `uv run python -m mcp_server.server` (transporte stdio), expondo as tools `consultar_batidas`, `listar_ajustes_pendentes`, `aprovar_ajuste`, `consultar_politica`, `analytics_rh`. É este comando que o agente (Task 9) usa como subprocess.

- [ ] **Step 1: Implementar `mcp_server/server.py`**

```python
"""Servidor MCP (FastMCP, stdio) expondo as ferramentas de RH.

As docstrings sao a interface com o LLM: descrevem quando usar cada tool.
"""

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from mcp_server import analytics, db

load_dotenv()

mcp = FastMCP("hr-agent")

_indice_politicas = None


def _indice():
    global _indice_politicas
    if _indice_politicas is None:
        from rag.index import build_index

        _indice_politicas = build_index()
    return _indice_politicas


@mcp.tool()
def consultar_batidas(nome_colaborador: str, data_inicio: str, data_fim: str) -> str:
    """Consulta as batidas de ponto de um colaborador da equipe num período.

    Use para perguntas sobre horários, atrasos, horas extras ou batidas
    faltantes de uma pessoa específica. Aceita nome parcial (ex.: 'Bruno').
    Datas no formato YYYY-MM-DD. O período dos dados vai de maio a julho de 2026.
    """
    return db.consultar_batidas(nome_colaborador, data_inicio, data_fim)


@mcp.tool()
def listar_ajustes_pendentes() -> str:
    """Lista os ajustes de ponto aguardando aprovação da gestora.

    Use quando a gestora perguntar o que está pendente, o que precisa
    aprovar, ou pedir a fila de ajustes. Retorna id, colaborador, data,
    campo a corrigir, valor proposto e motivo.
    """
    return db.listar_ajustes_pendentes()


@mcp.tool()
def aprovar_ajuste(ajuste_id: int, justificativa: str) -> str:
    """Aprova um ajuste de ponto pendente. AÇÃO DE ESCRITA com auditoria.

    Use somente quando a gestora pedir explicitamente para aprovar um ajuste.
    Exige o id do ajuste (veja listar_ajustes_pendentes) e uma justificativa.
    A aprovação corrige a batida e registra na trilha de auditoria.
    """
    return db.aprovar_ajuste(ajuste_id, justificativa)


@mcp.tool()
def consultar_politica(pergunta: str) -> str:
    """Busca trechos relevantes das políticas internas de RH (RAG).

    Use para dúvidas sobre regras: tolerância de atraso, banco de horas,
    ajuste de batida, home office, advertências. Retorna trechos literais
    com a fonte; responda com base neles, citando a política.
    """
    from rag.index import buscar_politica

    try:
        return buscar_politica(pergunta, _indice())
    except Exception as exc:  # noqa: BLE001
        return (f"A busca nas políticas está indisponível ({type(exc).__name__}). "
                "Verifique a chave OpenAI.")


@mcp.tool()
def analytics_rh(consulta_sql: str) -> str:
    """Executa uma consulta analítica SELECT no data warehouse (BigQuery).

    Use para perguntas agregadas sobre a equipe: total de horas extras por
    mês, evolução de atrasos, batidas incompletas por equipe.
    Escreva SQL padrão BigQuery usando exclusivamente esta tabela:
    rh_analytics.agregados_mensais — colunas: equipe STRING (Produto,
    Engenharia, Comercial), mes STRING 'YYYY-MM', total_atraso_minutos INT64,
    total_hora_extra_minutos INT64, batidas_incompletas INT64,
    colaboradores INT64.
    Somente SELECT é aceito; a consulta passa por validação de governança.
    """
    return analytics.analytics_rh(consulta_sql)


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

Nota: o schema na docstring precisa bater com `analytics.SCHEMA_AGREGADOS` (Task 7) — se o schema mudar, atualize os dois pontos.

- [ ] **Step 2: Smoke test do servidor**

Com `data/hr.db` existente (rode `uv run python -m etl.pipeline` se preciso):

Run: `uv run python -c "
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(command='uv', args=['run', 'python', '-m', 'mcp_server.server'])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as sessao:
            await sessao.initialize()
            tools = await sessao.list_tools()
            print([t.name for t in tools.tools])
            r = await sessao.call_tool('listar_ajustes_pendentes', {})
            print(r.content[0].text[:200])

asyncio.run(main())
"`
Expected: lista com os 5 nomes de tools e o texto dos ajustes pendentes.

- [ ] **Step 3: Rodar suite completa e lint**

Run: `uv run ruff check . && uv run pytest`
Expected: tudo verde.

- [ ] **Step 4: Commit**

```bash
git add mcp_server/server.py
git commit -m "feat: servidor MCP com as 5 tools de RH"
```

---

### Task 9: Agente LangGraph com human-in-the-loop

**Files:**
- Create: `agent/graph.py`
- Test: `tests/test_agent_helpers.py`

**Interfaces:**
- Consumes: servidor MCP via `python -m mcp_server.server` (Task 8).
- Produces:
  - `build_agent() -> agente` (async) — ReAct com `create_react_agent`, checkpointer `MemorySaver`, tools MCP com `aprovar_ajuste` embrulhada em interrupt.
  - `executar(agente, entrada: str | Command, thread_id: str) -> dict` (async) — retorna `{"resposta": str, "chamadas_mcp": list[dict], "interrupt": dict | None}`. `interrupt` traz `{"acao", "ajuste_id", "justificativa"}` quando o grafo pausou aguardando confirmação; retomar chamando `executar(agente, Command(resume="confirmar"|"cancelar"), thread_id)`.
  - `chamadas_apos_ultima_pergunta(mensagens) -> list[dict]` — helper puro `[{"tool": str, "args": dict}]` (testável).

- [ ] **Step 1: Escrever teste que falha (helper puro)**

`tests/test_agent_helpers.py`:

```python
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.graph import chamadas_apos_ultima_pergunta


def test_extrai_somente_chamadas_do_turno_atual():
    mensagens = [
        HumanMessage("pergunta antiga"),
        AIMessage("", tool_calls=[
            {"name": "consultar_batidas", "args": {"nome_colaborador": "X"},
             "id": "c1"}]),
        ToolMessage("resultado", tool_call_id="c1"),
        AIMessage("resposta antiga"),
        HumanMessage("pergunta nova"),
        AIMessage("", tool_calls=[
            {"name": "listar_ajustes_pendentes", "args": {}, "id": "c2"}]),
        ToolMessage("resultado", tool_call_id="c2"),
        AIMessage("resposta nova"),
    ]
    chamadas = chamadas_apos_ultima_pergunta(mensagens)
    assert chamadas == [{"tool": "listar_ajustes_pendentes", "args": {}}]


def test_sem_chamadas_retorna_lista_vazia():
    mensagens = [HumanMessage("oi"), AIMessage("olá!")]
    assert chamadas_apos_ultima_pergunta(mensagens) == []
```

- [ ] **Step 2: Rodar teste para ver falhar**

Run: `uv run pytest tests/test_agent_helpers.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implementar `agent/graph.py`**

```python
"""Agente LangGraph (ReAct) sobre as tools MCP, com confirmacao humana na escrita."""

import sys

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command, interrupt

SYSTEM_PROMPT = """Você é o assistente de RH da gestora Ana Souza.
Você substitui as telas do sistema de ponto: consulta batidas, explica políticas
internas, lista e aprova ajustes de ponto e responde perguntas analíticas.

Regras:
- Responda sempre em português do Brasil, de forma direta e cordial.
- Hoje é 2026-07-10; os dados de ponto cobrem maio a julho de 2026.
- Para dúvidas de política, use consultar_politica e cite a fonte.
- Para perguntas agregadas (totais, evolução, comparação entre equipes),
  use analytics_rh escrevendo SQL conforme o schema da tool.
- NUNCA aprove um ajuste sem que a gestora tenha pedido explicitamente.
- Se uma tool retornar erro ou indisponibilidade, explique com transparência.
"""


def _com_confirmacao(tool_mcp):
    """Embrulha a tool de escrita: pausa o grafo (interrupt) antes de executar."""

    @tool
    async def aprovar_ajuste(ajuste_id: int, justificativa: str) -> str:
        """Aprova um ajuste de ponto pendente (exige confirmação da gestora)."""
        decisao = interrupt({
            "acao": "aprovar_ajuste",
            "ajuste_id": ajuste_id,
            "justificativa": justificativa,
        })
        if decisao != "confirmar":
            return ("A gestora cancelou a aprovação. Nada foi gravado. "
                    "Pergunte se ela deseja outra coisa.")
        return await tool_mcp.ainvoke(
            {"ajuste_id": ajuste_id, "justificativa": justificativa})

    aprovar_ajuste.description = tool_mcp.description
    return aprovar_ajuste


async def build_agent():
    cliente = MultiServerMCPClient({
        "hr": {
            "command": sys.executable,
            "args": ["-m", "mcp_server.server"],
            "transport": "stdio",
        }
    })
    tools_mcp = await cliente.get_tools()
    tools = [
        _com_confirmacao(t) if t.name == "aprovar_ajuste" else t
        for t in tools_mcp
    ]
    modelo = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    return create_react_agent(
        modelo, tools, prompt=SYSTEM_PROMPT, checkpointer=MemorySaver())


def chamadas_apos_ultima_pergunta(mensagens) -> list[dict]:
    """Extrai as chamadas de tool feitas depois da ultima mensagem humana."""
    ultima_humana = -1
    for i, msg in enumerate(mensagens):
        if isinstance(msg, HumanMessage):
            ultima_humana = i
    chamadas = []
    for msg in mensagens[ultima_humana + 1:]:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                chamadas.append({"tool": tc["name"], "args": tc["args"]})
    return chamadas


async def executar(agente, entrada: str | Command, thread_id: str) -> dict:
    config = {"configurable": {"thread_id": thread_id}}
    if isinstance(entrada, str):
        payload = {"messages": [{"role": "user", "content": entrada}]}
    else:
        payload = entrada  # Command(resume=...)

    resultado = await agente.ainvoke(payload, config)

    interrupcoes = resultado.get("__interrupt__") or []
    pendente = interrupcoes[0].value if interrupcoes else None

    mensagens = resultado["messages"]
    resposta = ""
    if not pendente and mensagens and isinstance(mensagens[-1], AIMessage):
        resposta = mensagens[-1].content

    return {
        "resposta": resposta,
        "chamadas_mcp": chamadas_apos_ultima_pergunta(mensagens),
        "interrupt": pendente,
    }
```

Nota de compatibilidade: dependendo da versão do LangGraph, o payload de retomada é `Command(resume="confirmar")` e o interrupt aparece em `resultado["__interrupt__"]` como lista de objetos com `.value`. Se a versão instalada divergir, ajuste em `executar` (é o único ponto que toca essa API).

- [ ] **Step 4: Rodar testes até passar**

Run: `uv run pytest tests/test_agent_helpers.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Teste de integração manual (requer OPENAI_API_KEY no .env e data/hr.db)**

Run: `uv run python -c "
import asyncio
from langgraph.types import Command
from agent.graph import build_agent, executar

async def main():
    agente = await build_agent()
    r1 = await executar(agente, 'Quais ajustes estão pendentes?', 't1')
    print('RESPOSTA 1:', r1['resposta'][:300])
    print('CHAMADAS:', r1['chamadas_mcp'])
    r2 = await executar(agente, 'Aprove o ajuste 1 porque o sistema estava fora do ar', 't1')
    print('INTERRUPT:', r2['interrupt'])
    r3 = await executar(agente, Command(resume='confirmar'), 't1')
    print('RESPOSTA 3:', r3['resposta'][:300])

asyncio.run(main())
"`
Expected: resposta 1 lista pendências com chamada a `listar_ajustes_pendentes`; r2 traz `interrupt` com `acao=aprovar_ajuste`; r3 confirma aprovação com trilha de auditoria.

- [ ] **Step 6: Commit**

```bash
git add agent/graph.py tests/test_agent_helpers.py
git commit -m "feat: agente ReAct com tools MCP e confirmacao humana na escrita"
```

---

### Task 10: App Streamlit (gate de senha, chat, painel MCP)

**Files:**
- Create: `app/main.py`
- Test: manual (roteiro no Step 3)

**Interfaces:**
- Consumes: `build_agent`, `executar` (Task 9); `etl.pipeline.main` (Task 4) para bootstrap do banco.
- Produces: `uv run streamlit run app/main.py` sobe o chat completo.

- [ ] **Step 1: Implementar `app/main.py`**

```python
"""Chat Streamlit: gate de senha, conversa com o agente e painel de chamadas MCP."""

import asyncio
import os
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="HR Agent MCP", page_icon="🕐", layout="wide")

SEGREDOS_EXPORTAVEIS = (
    "OPENAI_API_KEY", "APP_PASSWORD", "GCP_PROJECT_ID",
    "GCP_SERVICE_ACCOUNT_JSON", "HR_DB_PATH",
    "LANGSMITH_TRACING", "LANGSMITH_API_KEY",
)


def _exportar_segredos() -> None:
    """Copia st.secrets -> os.environ (o subprocess MCP herda os.environ)."""
    try:
        for chave in SEGREDOS_EXPORTAVEIS:
            if chave in st.secrets and not os.environ.get(chave):
                os.environ[chave] = str(st.secrets[chave])
    except FileNotFoundError:
        pass  # sem secrets.toml em dev local — .env cobre


_exportar_segredos()


def _gate_de_senha() -> None:
    senha_esperada = os.environ.get("APP_PASSWORD", "")
    if not senha_esperada:
        return  # sem senha configurada (dev local)
    if st.session_state.get("autenticado"):
        return
    st.title("🕐 HR Agent MCP")
    st.caption("Demo protegida — insira a senha de acesso.")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar") and senha:
        if senha == senha_esperada:
            st.session_state["autenticado"] = True
            st.rerun()
        st.error("Senha incorreta.")
    st.stop()


_gate_de_senha()


@st.cache_resource
def _bootstrap():
    """Garante o banco (disco efemero no Streamlit Cloud) e cria o agente."""
    if not Path(os.environ.get("HR_DB_PATH", "data/hr.db")).exists():
        from etl.pipeline import main as rodar_etl

        rodar_etl()
    from agent.graph import build_agent

    loop = asyncio.new_event_loop()
    agente = loop.run_until_complete(build_agent())
    return loop, agente


loop, agente = _bootstrap()

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.historico = []
    st.session_state.chamadas_mcp = []
    st.session_state.interrupt_pendente = None


def _processar(entrada) -> None:
    from agent.graph import executar

    with st.spinner("Consultando o agente..."):
        resultado = loop.run_until_complete(
            executar(agente, entrada, st.session_state.thread_id))
    if resultado["chamadas_mcp"]:
        st.session_state.chamadas_mcp.append(resultado["chamadas_mcp"])
    st.session_state.interrupt_pendente = resultado["interrupt"]
    if resultado["resposta"]:
        st.session_state.historico.append(
            {"role": "assistant", "content": resultado["resposta"]})


# ---------- Sidebar: painel de transparencia MCP ----------
with st.sidebar:
    st.header("🔌 Chamadas MCP")
    st.caption("Cada resposta mostra quais ferramentas o agente chamou "
               "no servidor MCP, com os argumentos usados.")
    if not st.session_state.chamadas_mcp:
        st.info("Nenhuma chamada ainda. Pergunte algo!")
    for i, turno in enumerate(st.session_state.chamadas_mcp, start=1):
        with st.expander(f"Turno {i} — {len(turno)} chamada(s)", expanded=True):
            for chamada in turno:
                st.markdown(f"**`{chamada['tool']}`**")
                st.json(chamada["args"])
    st.divider()
    st.caption("Persona: **Ana Souza — Gestora de RH** · dados sintéticos · "
               "[código no GitHub](https://github.com/)")

# ---------- Chat ----------
st.title("🕐 HR Agent MCP")
st.caption("Converse em vez de navegar: batidas, políticas, aprovações e analytics.")

with st.expander("💡 Sugestões de perguntas"):
    st.markdown("""
- *Como foram as batidas do time esta semana?* (cite um nome para detalhar)
- *Qual a tolerância de atraso pela política?*
- *O que está pendente de aprovação?*
- *Aprove o ajuste 1, o sistema estava fora do ar.*
- *Qual equipe fez mais horas extras por mês?*
""")

for msg in st.session_state.historico:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if st.session_state.interrupt_pendente:
    pend = st.session_state.interrupt_pendente
    with st.chat_message("assistant"):
        st.warning(
            f"⚠️ **Confirmação necessária** — aprovar o ajuste "
            f"**#{pend['ajuste_id']}**?\n\nJustificativa: *{pend['justificativa']}*")
        col1, col2 = st.columns(2)
        if col1.button("✅ Confirmar aprovação", type="primary"):
            from langgraph.types import Command

            st.session_state.interrupt_pendente = None
            _processar(Command(resume="confirmar"))
            st.rerun()
        if col2.button("❌ Cancelar"):
            from langgraph.types import Command

            st.session_state.interrupt_pendente = None
            _processar(Command(resume="cancelar"))
            st.rerun()

pergunta = st.chat_input("Pergunte sobre ponto, políticas, ajustes ou analytics...")
if pergunta:
    st.session_state.historico.append({"role": "user", "content": pergunta})
    _processar(pergunta)
    st.rerun()
```

- [ ] **Step 2: Lint**

Run: `uv run ruff check .`
Expected: sem erros.

- [ ] **Step 3: Teste manual completo (requer `.env` com OPENAI_API_KEY)**

Run: `uv run streamlit run app/main.py`

Roteiro de verificação (os 4 fluxos do spec):
1. Sem `APP_PASSWORD` no `.env` → entra direto; com → gate funciona (senha errada dá erro).
2. "Quais ajustes estão pendentes?" → resposta com lista; sidebar mostra `listar_ajustes_pendentes`.
3. "Qual a tolerância de atraso?" → resposta cita a política; sidebar mostra `consultar_politica`.
4. "Aprove o ajuste 1, o sistema estava fora do ar" → aparece o card de confirmação; **Confirmar** → resposta de aprovado; repetir a aprovação → "já foi processado" (prova da auditoria); **Cancelar** em outro ajuste → nada gravado.
5. "Qual equipe fez mais horas extras por mês?" → sem credencial BigQuery, resposta transparente de indisponibilidade; com credencial, tabela de resultados. Sidebar mostra `analytics_rh` com o SQL gerado.
6. Follow-up com pronome ("e na semana anterior?") → memória de conversa funciona.

- [ ] **Step 4: Commit**

```bash
git add app/main.py
git commit -m "feat: chat Streamlit com gate de senha e painel de chamadas MCP"
```

---

### Task 11: CI (GitHub Actions)

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: suite pytest + ruff das tasks anteriores.
- Produces: workflow `CI` verde a cada push (lint + testes, sem segredos).

- [ ] **Step 1: Criar `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync
      - run: uv run ruff check .
      - run: uv run pytest -v
```

- [ ] **Step 2: Verificar localmente o que a CI vai rodar**

Run: `uv run ruff check . && uv run pytest -v`
Expected: tudo verde (a CI só repete isso).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: lint e testes no GitHub Actions"
```

---

### Task 12: README e DEMO.md

**Files:**
- Create: `README.md`, `DEMO.md`

**Interfaces:**
- Consumes: tudo anterior (documenta o sistema pronto).
- Produces: README com diagrama mermaid, mapa de capacidades, quickstart, seção BigQuery e deploy; DEMO.md com roteiro de 3 minutos.

- [ ] **Step 1: Escrever `README.md`**

Estrutura obrigatória (escrever por extenso, em pt-BR — o conteúdo abaixo é o esqueleto com os pontos que cada seção precisa cobrir; placeholders `<...>` são preenchidos no deploy, Task 13):

```markdown
# 🕐 HR Agent MCP

Agente conversacional de RH que substitui telas estáticas de sistema de ponto
por uma interface de conversa — com **MCP**, **LangGraph**, **RAG** e **BigQuery**.

**🔗 Demo online:** <link Streamlit Cloud> (senha: solicitar) · **CI:** <badge>

## O que ele faz
[4 fluxos: consulta de batidas · dúvidas de política (RAG com fonte) ·
aprovação de ajuste com confirmação humana + trilha de auditoria ·
analytics no BigQuery via SQL validado por camada de governança.
GIF da demo aqui.]

## Arquitetura
[diagrama mermaid:]
​```mermaid
flowchart TD
    UI[Streamlit — chat + painel MCP] --> AG[LangGraph — agente ReAct\nmemória + human-in-the-loop]
    AG -->|MCP stdio| SRV[Servidor MCP — FastMCP]
    SRV --> T1[consultar_batidas] --> DB[(SQLite\noperacional)]
    SRV --> T2[listar/aprovar ajustes] --> DB
    T2 --> AUD[(audit_log)]
    SRV --> T3[consultar_politica] --> RAG[FAISS — políticas de RH]
    SRV --> T4[analytics_rh] --> BQ[(BigQuery\nrh_analytics)]
    ETL[ETL Python\nextract→transform→load] --> DB
    ETL --> BQ
​```
[parágrafo: por que operacional (SQLite, leitura/escrita) separado do
analítico (BigQuery, read-only) — e por que toda escrita passa por
interrupt + auditoria.]

## Capacidades demonstradas
| Capacidade | Onde está no código |
|---|---|
| MCP (servidor + client) | `mcp_server/server.py`, `agent/graph.py` |
| Orquestração de agente (LangGraph) | `agent/graph.py` |
| Human-in-the-loop (interrupt) | `agent/graph.py` (`_com_confirmacao`) |
| RAG (FAISS + embeddings) | `rag/index.py`, `data/politicas/` |
| ETL (extract→transform→load) | `etl/` |
| BigQuery + governança de SQL | `mcp_server/analytics.py`, `core/bq.py` |
| APIs Python / testes / CI | `mcp_server/db.py`, `tests/`, `.github/workflows/` |

## Rodando localmente
[passos: clonar; `cp .env.example .env` e preencher OPENAI_API_KEY;
`uv sync`; `uv run python -m etl.pipeline`; `uv run streamlit run app/main.py`.
BigQuery é opcional — sem credencial o agente degrada graciosamente.]

## BigQuery (opcional)
[passos: criar projeto no GCP Sandbox (grátis, sem cartão); service account
com papel BigQuery Admin no projeto; baixar JSON; apontar
GOOGLE_APPLICATION_CREDENTIALS ou colar em GCP_SERVICE_ACCOUNT_JSON;
rodar `uv run python -m etl.pipeline` para carregar `rh_analytics`.]

## Dados
[100% sintéticos (Faker, seed 42), personas fictícias, políticas fictícias.
Nenhum dado real de nenhuma empresa.]

## Stack
[lista com versões: Python 3.11+, uv, mcp/FastMCP, LangGraph,
langchain-openai (gpt-4o-mini), FAISS, pandas, google-cloud-bigquery,
Streamlit, pytest, ruff.]
```

- [ ] **Step 2: Escrever `DEMO.md`**

```markdown
# 🎬 Roteiro de demo — 3 minutos

**Persona:** Ana Souza, gestora de RH. **Cenário:** segunda de manhã, revisão da equipe.

## 0:00 — Abertura (painel lateral à vista)
Mostrar o chat e o painel "Chamadas MCP" vazio. Uma frase: "cada resposta
mostra as ferramentas MCP chamadas — transparência de integração".

## 0:20 — Consulta operacional
> "Como foram as batidas do [colaborador] nas últimas duas semanas?"

Apontar no painel: `consultar_batidas` + argumentos. Destacar atrasos e a
batida incompleta na resposta.

## 1:00 — Grounding em política (RAG)
> "E qual a tolerância de atraso pela nossa política?"

Apontar: `consultar_politica`, resposta cita a fonte (politica-de-ponto.md).

## 1:30 — Ação com governança (o clímax)
> "O que está pendente de aprovação?" → "Aprove o ajuste 1, o sistema estava fora do ar."

Mostrar o **card de confirmação** (human-in-the-loop): o agente NÃO escreve
sem confirmação. Confirmar → aprovado + trilha de auditoria.
Pedir para aprovar de novo → "já foi processado" (auditoria funcionando).

## 2:20 — Analytics (BigQuery)
> "Qual equipe acumulou mais horas extras por mês?"

Apontar: `analytics_rh` com o SQL gerado pelo LLM e validado pela camada de
governança antes de tocar o BigQuery.

## 2:50 — Fechamento
Arquitetura em uma frase: "Streamlit → LangGraph → MCP → SQLite/FAISS/BigQuery;
ETL alimenta o warehouse; toda escrita tem confirmação humana e auditoria."
```

- [ ] **Step 3: Commit**

```bash
git add README.md DEMO.md
git commit -m "docs: README com arquitetura e mapa de capacidades + roteiro de demo"
```

---

### Task 13: Publicação e deploy (GitHub + BigQuery + Streamlit Cloud)

**Files:**
- Modify: `README.md` (preencher link da demo e badge de CI)

**Interfaces:**
- Consumes: repo completo e verde.
- Produces: repo público no GitHub com CI verde; dataset `rh_analytics` carregado no BigQuery; demo online no Streamlit Community Cloud; README final.

Passos manuais/guiados — envolvem contas do usuário (GitHub, GCP, Streamlit Cloud). Executar com o usuário presente ou com `gh` autenticado.

- [ ] **Step 1: Publicar no GitHub**

```bash
gh repo create hr-agent-mcp --public --source . --push \
  --description "Agente conversacional de RH com MCP, LangGraph, RAG e BigQuery"
```

Verificar: Actions do repo → workflow CI verde.

- [ ] **Step 2: BigQuery Sandbox (manual, ~10 min)**

1. https://console.cloud.google.com → criar projeto (ex.: `hr-agent-poc`) — sandbox, sem billing.
2. IAM → Service Accounts → criar `hr-agent` com papel **BigQuery Admin** → criar chave JSON e baixar.
3. Local: preencher `GCP_PROJECT_ID` e `GOOGLE_APPLICATION_CREDENTIALS` no `.env`.
4. Rodar: `uv run python -m etl.pipeline` → esperado: "BigQuery: N linhas carregadas em ...".
5. Conferir no console: dataset `rh_analytics`, tabela `agregados_mensais`.
6. Testar no app local: pergunta analítica → tabela de resultados via `analytics_rh`.

- [ ] **Step 3: Deploy no Streamlit Community Cloud (manual, ~15 min)**

1. https://share.streamlit.io → New app → repo `hr-agent-mcp`, branch `main`, arquivo `app/main.py`.
2. Advanced settings → Secrets (TOML):

```toml
OPENAI_API_KEY = "sk-..."
APP_PASSWORD = "senha-da-demo"
GCP_PROJECT_ID = "hr-agent-poc"
GCP_SERVICE_ACCOUNT_JSON = '''{ ...conteudo do json da service account... }'''
```

3. Deploy e smoke test dos 4 fluxos do roteiro da Task 10 Step 3, agora online.
4. Atenção: Community Cloud usa `uv` com `pyproject.toml` automaticamente; se o build falhar por resolução, gerar `requirements.txt` com `uv export --no-dev --format requirements-txt > requirements.txt` e commitar.

- [ ] **Step 4: Finalizar README**

Preencher no `README.md`: link da demo online, badge de CI
(`[![CI](https://github.com/<user>/hr-agent-mcp/actions/workflows/ci.yml/badge.svg)](...)`),
e o link do GitHub na sidebar do app (`app/main.py`). Gravar GIF da demo
(ex.: [ScreenToGif](https://www.screentogif.com/) no Windows), salvar em `docs/demo.gif`,
referenciar no README.

```bash
git add README.md app/main.py docs/demo.gif
git commit -m "docs: link da demo online, badge de CI e GIF"
git push
```

- [ ] **Step 5: Verificação final (critérios de aceite do spec)**

1. Clone limpo em outra pasta + `.env` → app local funciona.
2. Demo online responde os 4 fluxos.
3. Painel lateral mostra as chamadas MCP.
4. CI verde no GitHub.
5. README completo (diagrama, GIF, mapa, instruções) + DEMO.md.
