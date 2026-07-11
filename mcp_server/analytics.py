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
