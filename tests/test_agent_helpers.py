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
