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
