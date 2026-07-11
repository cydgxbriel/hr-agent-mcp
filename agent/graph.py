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
