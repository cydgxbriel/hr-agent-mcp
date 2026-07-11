"""Camadas de avaliação: checagens determinísticas + LLM-as-judge."""

import json
import re
from dataclasses import dataclass

from evals.dataset import Caso


@dataclass
class Check:
    nome: str
    passou: bool
    detalhe: str


def checar_deterministico(
    caso: Caso, resposta: str, chamadas: list[dict], interrupt: dict | None
) -> list[Check]:
    """Aplica as asserções baratas e não-flaky do caso."""
    checks: list[Check] = []
    nomes_tools = [c["tool"] for c in chamadas]
    resp_lower = (resposta or "").lower()

    if caso.tool_esperada:
        ok = caso.tool_esperada in nomes_tools
        checks.append(Check("tool", ok,
                            f"esperava '{caso.tool_esperada}', chamou {nomes_tools}"))
    for proibida in caso.tools_proibidas:
        checks.append(Check(f"nao-tool:{proibida}", proibida not in nomes_tools,
                            f"chamadas: {nomes_tools}"))
    if caso.nenhuma_tool:
        checks.append(Check("nenhuma-tool", len(nomes_tools) == 0,
                            f"chamadas: {nomes_tools}"))
    for termo in caso.contem:
        checks.append(Check(f"contem:{termo}", termo.lower() in resp_lower,
                            f"resposta[:120]={resposta[:120]!r}"))
    for termo in caso.nao_contem:
        checks.append(Check(f"nao-contem:{termo}", termo.lower() not in resp_lower,
                            f"resposta[:120]={resposta[:120]!r}"))
    if caso.regex:
        achou = bool(re.search(caso.regex, resposta or "", re.IGNORECASE))
        checks.append(Check(f"regex:{caso.regex}", achou,
                            f"resposta[:120]={resposta[:120]!r}"))
    if caso.interrupt_esperado:
        ok = interrupt is not None and (
            caso.ajuste_id_esperado is None
            or interrupt.get("ajuste_id") == caso.ajuste_id_esperado)
        checks.append(Check("interrupt", ok, f"interrupt={interrupt}"))
    if caso.sem_interrupt:
        checks.append(Check("sem-interrupt", interrupt is None,
                            f"interrupt={interrupt}"))
    return checks


_JUDGE_PROMPT = """Você é um avaliador rigoroso de um assistente de RH.
Julgue se a RESPOSTA cumpre o CRITÉRIO. Seja objetivo: se a resposta atende o
essencial do critério, aprova; se falha no essencial (dado errado, inventa,
ignora o pedido), reprova.

Contexto do sistema (não penalize a resposta por isto): a data-base é
2026-07-10 e os dados de ponto vão de maio a julho de 2026. Portanto respostas
que citam "2026" estão corretas — não trate o ano como erro.

PERGUNTA DO USUÁRIO:
{pergunta}

RESPOSTA DO ASSISTENTE:
{resposta}

CRITÉRIO DE APROVAÇÃO:
{rubrica}

Responda SOMENTE com JSON válido, sem cercas de código:
{{"passou": true|false, "justificativa": "<uma frase>"}}"""


def julgar(caso: Caso, pergunta: str, resposta: str) -> Check:
    """Avalia a resposta contra a rubrica usando um LLM juiz (gpt-4o-mini)."""
    from langchain_openai import ChatOpenAI

    modelo = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    prompt = _JUDGE_PROMPT.format(
        pergunta=pergunta, resposta=resposta or "(resposta vazia)", rubrica=caso.rubrica)
    try:
        bruto = modelo.invoke(prompt).content
        limpo = bruto.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
        veredito = json.loads(limpo.strip())
        return Check("juiz", bool(veredito.get("passou")),
                     veredito.get("justificativa", ""))
    except Exception as exc:  # noqa: BLE001 — falha do juiz não derruba a suíte
        return Check("juiz", False, f"erro ao julgar: {type(exc).__name__}: {exc}")
