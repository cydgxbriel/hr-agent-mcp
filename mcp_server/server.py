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
