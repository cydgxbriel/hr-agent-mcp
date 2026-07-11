# hr-agent-mcp — Design da POC

**Data:** 2026-07-10 · **Status:** aprovado

## Objetivo

POC funcional e pública de um **agente conversacional de RH** que substitui a navegação em telas estáticas de um sistema de ponto: o gestor conversa com o agente para consultar batidas da equipe, tirar dúvidas de política interna (RAG), aprovar ajustes de ponto com confirmação explícita e trilha de auditoria, e fazer perguntas analíticas respondidas por um data warehouse (BigQuery).

O projeto demonstra, num único repositório executável: **MCP** como camada de integração de ferramentas, **LangGraph** como orquestração de agente com human-in-the-loop, **RAG** para grounding em políticas, **pipeline ETL** alimentando o **BigQuery**, APIs em **Python**, e deploy em nuvem com demo online.

## Escopo

**Dentro:**
- Servidor MCP real (FastMCP, stdio) com 5 tools de RH.
- Agente LangGraph (ReAct) consumindo as tools via `langchain-mcp-adapters`, com interrupt de confirmação antes de qualquer escrita.
- Pipeline ETL (extract → transform → load) com dados sintéticos.
- RAG sobre 3 documentos fictícios de política de RH (pt-BR).
- Chat em Streamlit com painel lateral exibindo as chamadas MCP em tempo real.
- Deploy no Streamlit Community Cloud com senha de acesso.
- Testes (pytest) das tools MCP e do transform do ETL; CI mínima (lint + testes) no GitHub Actions.
- README em pt-BR com diagrama, GIF e mapa "capacidade → onde está no código". Roteiro de demo em `DEMO.md`.

**Fora (YAGNI):**
- Autenticação/multiusuário real (persona de gestora fixa, senha única de acesso à demo).
- Escrita no BigQuery (sandbox não suporta DML; escrita operacional fica no SQLite — separação operacional × analítico é a arquitetura desejada).
- Múltiplos agentes especializados sob supervisor (um agente ReAct basta para o caso de uso; a arquitetura permite evoluir).
- Vector store gerenciado (FAISS local; documentos pequenos, índice construído no startup).

## Arquitetura

```
Streamlit (chat + painel de chamadas MCP)
   │
LangGraph — agente ReAct
   │  · memória de conversa (checkpointer)
   │  · interrupt (human-in-the-loop) antes de escrita
   │  · LangSmith opcional via env
   ▼
MCP Server — FastMCP, transporte stdio (subprocess)
 ├─ consultar_batidas(colaborador, período) ──► SQLite (operacional)
 ├─ listar_ajustes_pendentes() ──────────────► SQLite
 ├─ aprovar_ajuste(id, justificativa) ───────► SQLite + audit_log
 ├─ consultar_politica(pergunta) ────────────► RAG · FAISS + embeddings OpenAI
 └─ analytics_rh(pergunta) ──────────────────► BigQuery (dataset rh_analytics)
                       ▲
        ETL: extract (Faker → CSV bruto)
             transform (pandas: atrasos, horas extras)
             load (SQLite + load job BigQuery)
```

- **LLM:** OpenAI `gpt-4o-mini` (tool-calling suficiente, custo de centavos na demo).
- O servidor MCP roda como subprocess stdio dentro do mesmo container do Streamlit — sem hospedagem extra.

## Componentes e interfaces

| Módulo | Responsabilidade | Interface |
|---|---|---|
| `mcp_server/` | Expor as 5 tools de RH via MCP; docstrings ricas guiam o roteamento do LLM | Protocolo MCP (stdio) |
| `agent/` | Grafo LangGraph: ReAct + interrupt de confirmação + memória | `run_agent(mensagem, thread_id) → resposta / pedido de confirmação` |
| `etl/` | Gerar dados sintéticos, transformar e carregar SQLite + BigQuery | CLI: `python -m etl.pipeline` |
| `rag/` | Ingestão dos documentos de política, chunking, índice FAISS | `buscar_politica(pergunta) → trechos` |
| `app/` | Chat Streamlit, painel de chamadas MCP, gate de senha | Web UI |
| `data/` | CSVs brutos, SQLite, documentos de política | Arquivos |

Cada módulo é testável isoladamente: as tools MCP funcionam sem o agente; o ETL roda sem o app; o RAG responde sem LLM de geração.

## Dados

- **Personas:** 1 gestora logada (persona fixa da demo) + 8 colaboradores gerados com Faker (seed fixa → dados reproduzíveis).
- **Batidas:** 60 dias, com anomalias plantadas — atrasos, batidas faltantes e 3–4 ajustes pendentes de aprovação — para a demo sempre ter material.
- **SQLite (operacional):** `colaboradores`, `batidas`, `ajustes`, `audit_log`.
- **BigQuery (analítico):** GCP Sandbox (grátis, sem cartão), dataset `rh_analytics` com agregados mensais de horas extras, atrasos e absenteísmo por equipe, carregados via load job pelo ETL.
- **Políticas (RAG):** 3 markdowns fictícios em pt-BR — política de ponto, banco de horas, home office.

## Tratamento de erros

- Tools MCP retornam erros estruturados (mensagem clara, nunca traceback cru) — o agente comunica a falha em linguagem natural.
- BigQuery indisponível/credencial ausente → `analytics_rh` responde que a camada analítica está fora do ar; o restante da demo segue funcionando.
- Toda escrita (`aprovar_ajuste`) exige confirmação prévia via interrupt do LangGraph; sem confirmação, nada é gravado.
- Gate de senha errado → app não inicializa o agente (protege a chave OpenAI).

## Testes e CI

- **pytest:** tools MCP contra SQLite in-memory (consulta, aprovação, auditoria, erro de id inexistente); transform do ETL (cálculo de atraso/hora extra); recuperação do RAG (pergunta conhecida retorna o trecho certo).
- **CI (GitHub Actions):** ruff + pytest a cada push. Sem testes de integração com BigQuery/OpenAI na CI (dependem de segredo; verificados manualmente e via demo online).

## Deploy

- **Streamlit Community Cloud**, repo público no GitHub.
- Secrets: `OPENAI_API_KEY`, service account GCP (JSON), `APP_PASSWORD`.
- Gerenciador: `uv` (`pyproject.toml`); instruções clone-e-rode no README.

## Critérios de aceite

1. `uv run streamlit run app/main.py` local funciona com `.env` preenchido.
2. Demo online (link no README) responde os 4 fluxos: consulta de batidas, dúvida de política (RAG), aprovação de ajuste com confirmação + auditoria, pergunta analítica (BigQuery).
3. Painel lateral exibe as chamadas MCP (tool + argumentos) de cada resposta.
4. CI verde; testes passam localmente.
5. README com diagrama, GIF, mapa de capacidades e instruções; `DEMO.md` com roteiro de 3 minutos.

## Cronograma (2–3 dias)

| Dia | Entrega |
|---|---|
| 1 | Repo, ETL + dados sintéticos, SQLite, BigQuery, servidor MCP, testes |
| 2 | Agente LangGraph, RAG, Streamlit, integração ponta a ponta |
| 3 | Deploy, README, GIF, polimento |
