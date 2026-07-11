"""Runner da suíte de avaliação: roda cada caso ponta a ponta contra o agente.

Isolamento: casos que escrevem (`muta_dados`) rodam contra uma cópia temporária
do banco (via `HR_DB_PATH`), então as avaliações nunca corrompem o estado da
demo. Casos somente-leitura compartilham um único agente (o índice RAG é
construído uma vez) para reduzir custo e latência.
"""

import os
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass, field

from langgraph.types import Command

from agent.graph import build_agent, executar
from evals.dataset import CASOS, Caso
from evals.scorers import Check, checar_deterministico, julgar

DB_REAL = "data/hr.db"


@dataclass
class Resultado:
    caso: Caso
    checks: list[Check]
    resposta: str
    chamadas: list[dict]
    latencia_s: float
    passou: bool = field(init=False)

    def __post_init__(self):
        self.passou = all(c.passou for c in self.checks)


async def _rodar_caso(agente, caso: Caso, usar_juiz: bool) -> Resultado:
    thread = f"eval-{caso.id}-{uuid.uuid4().hex[:8]}"
    turnos = [("pergunta", caso.pergunta), *caso.turnos_extra]
    todas_chamadas: list[dict] = []
    interrupt_visto: dict | None = None
    resposta_final = ""

    t0 = time.time()
    for tipo, valor in turnos:
        entrada = valor if tipo == "pergunta" else Command(resume=valor)
        r = await executar(agente, entrada, thread)
        todas_chamadas.extend(r["chamadas_mcp"])
        if r["interrupt"]:
            interrupt_visto = r["interrupt"]
        if r["resposta"]:
            resposta_final = r["resposta"]
    latencia = time.time() - t0

    checks = checar_deterministico(caso, resposta_final, todas_chamadas, interrupt_visto)
    if usar_juiz and caso.rubrica:
        checks.append(julgar(caso, caso.pergunta, resposta_final))

    return Resultado(caso, checks, resposta_final, todas_chamadas, latencia)


def _copia_temp_db() -> str:
    fd, caminho = tempfile.mkstemp(suffix=".db", prefix="eval-hr-")
    os.close(fd)
    shutil.copy(DB_REAL, caminho)
    return caminho


async def rodar_suite(casos: list[Caso] | None = None, usar_juiz: bool = True,
                      progresso=None) -> list[Resultado]:
    casos = casos if casos is not None else CASOS
    somente_leitura = [c for c in casos if not c.muta_dados]
    mutantes = [c for c in casos if c.muta_dados]
    resultados: list[Resultado] = []

    os.environ["HR_DB_PATH"] = DB_REAL
    agente = await build_agent()
    for caso in somente_leitura:
        if progresso:
            progresso(caso)
        resultados.append(await _rodar_caso(agente, caso, usar_juiz))

    for caso in mutantes:
        if progresso:
            progresso(caso)
        temp = _copia_temp_db()
        os.environ["HR_DB_PATH"] = temp
        try:
            agente_m = await build_agent()
            resultados.append(await _rodar_caso(agente_m, caso, usar_juiz))
        finally:
            os.environ["HR_DB_PATH"] = DB_REAL
            os.remove(temp)

    ordem = {c.id: i for i, c in enumerate(casos)}
    resultados.sort(key=lambda r: ordem[r.caso.id])
    return resultados
