# 🧪 Avaliação do agente (evals)

Suíte de avaliação ponta a ponta do agente de RH: cada caso roda contra o
agente real (LangGraph → servidor MCP → SQLite/RAG/BigQuery → LLM), não mocks.
As asserções são ancoradas nos dados sintéticos gerados com seed 42.

## Como rodar

```bash
uv run python -m evals.run            # determinístico + LLM-as-judge
uv run python -m evals.run --sem-juiz # só a camada determinística
```

Precisa de `OPENAI_API_KEY` (agente + juiz) e, para a categoria *analytics*,
das credenciais de BigQuery no `.env`. Não roda na CI (consome API + segredos);
é um harness manual e estes resultados são versionados.

## Camadas de avaliação

- **Determinística** — qual tool MCP foi chamada, substrings/regex na resposta,
  e o estado do gate de confirmação (interrupt). Barata e reprodutível.
- **LLM-as-judge** — um `gpt-4o-mini` juiz avalia a resposta contra uma rubrica
  em linguagem natural, só onde o match de string seria frágil demais.

Um caso passa quando **todas** as suas checagens passam. Casos marcados como
*esforço* exercitam limites conhecidos (ex.: desambiguação de nomes, raciocínio
cruzando política + dados) e podem falhar de propósito — são sinal, não ruído.


## Resultados

**Acurácia geral:** 26/28 (93%) · **juiz:** sim · **latência total:** 374s · **rodado em:** 2026-07-11


### Por categoria

| Categoria | Passou / Total |
|---|---|
| analytics | 4/4 |
| cruzamento | 1/2 |
| desambiguacao | 2/3 |
| escrita | 4/4 |
| governanca | 3/3 |
| operacional | 4/4 |
| politica | 4/4 |
| roteamento | 4/4 |

### Por caso

| Caso | Categoria | Resultado | Checagens que falharam |
|---|---|---|---|
| R1 | roteamento | ✅ | — |
| R2 | roteamento | ✅ | — |
| R3 | roteamento | ✅ | — |
| R4 | roteamento | ✅ | — |
| O1 | operacional | ✅ | — |
| O2 | operacional | ✅ | — |
| O3 | operacional | ✅ | — |
| O4 | operacional | ✅ | — |
| D1 *(esforço)* | desambiguacao | ❌ | juiz |
| D2 | desambiguacao | ✅ | — |
| D3 | desambiguacao | ✅ | — |
| P1 | politica | ✅ | — |
| P2 | politica | ✅ | — |
| P3 | politica | ✅ | — |
| P4 | politica | ✅ | — |
| A1 | analytics | ✅ | — |
| A2 | analytics | ✅ | — |
| A3 | analytics | ✅ | — |
| A4 | analytics | ✅ | — |
| W1 | escrita | ✅ | — |
| W2 | escrita | ✅ | — |
| W3 | escrita | ✅ | — |
| W4 | escrita | ✅ | — |
| C1 *(esforço)* | cruzamento | ✅ | — |
| C2 *(esforço)* | cruzamento | ❌ | juiz |
| G1 | governanca | ✅ | — |
| G2 | governanca | ✅ | — |
| G3 | governanca | ✅ | — |
