"""CLI da suíte de avaliação.

Uso:
    uv run python -m evals.run                 # roda tudo (determinístico + juiz)
    uv run python -m evals.run --sem-juiz      # só camada determinística (custo zero de juiz)
    uv run python -m evals.run --categoria politica
    uv run python -m evals.run --quieto        # sem log por caso

Gera:
    evals/resultados.json   — detalhe por caso
    EVALS.md                — metodologia + tabela de resultados (versionado)
"""

import argparse
import asyncio
import json
import sys
from datetime import date

from dotenv import load_dotenv

load_dotenv()

from evals.dataset import CASOS  # noqa: E402
from evals.harness import Resultado, rodar_suite  # noqa: E402

METODOLOGIA = """\
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
"""


def _tabela_por_categoria(resultados: list[Resultado]) -> str:
    cats: dict[str, list[Resultado]] = {}
    for r in resultados:
        cats.setdefault(r.caso.categoria, []).append(r)
    linhas = ["| Categoria | Passou / Total |", "|---|---|"]
    for cat in sorted(cats):
        grupo = cats[cat]
        ok = sum(1 for r in grupo if r.passou)
        linhas.append(f"| {cat} | {ok}/{len(grupo)} |")
    return "\n".join(linhas)


def _tabela_casos(resultados: list[Resultado]) -> str:
    linhas = ["| Caso | Categoria | Resultado | Checagens que falharam |",
              "|---|---|---|---|"]
    for r in resultados:
        icone = "✅" if r.passou else "❌"
        falhas = ", ".join(c.nome for c in r.checks if not c.passou) or "—"
        esforco = " *(esforço)*" if r.caso.nota and "esforço" in r.caso.nota.lower() else ""
        linhas.append(f"| {r.caso.id}{esforco} | {r.caso.categoria} | {icone} | {falhas} |")
    return "\n".join(linhas)


def _gerar_markdown(resultados: list[Resultado], usou_juiz: bool) -> str:
    total = len(resultados)
    ok = sum(1 for r in resultados if r.passou)
    lat = sum(r.latencia_s for r in resultados)
    pct = (100 * ok / total) if total else 0
    cabecalho = (
        f"**Acurácia geral:** {ok}/{total} ({pct:.0f}%) · "
        f"**juiz:** {'sim' if usou_juiz else 'não'} · "
        f"**latência total:** {lat:.0f}s · "
        f"**rodado em:** {date.today().isoformat()}\n")
    return "\n\n".join([
        METODOLOGIA,
        "## Resultados",
        cabecalho,
        "### Por categoria",
        _tabela_por_categoria(resultados),
        "### Por caso",
        _tabela_casos(resultados),
    ]) + "\n"


def _gerar_json(resultados: list[Resultado]) -> str:
    payload = []
    for r in resultados:
        payload.append({
            "id": r.caso.id,
            "categoria": r.caso.categoria,
            "pergunta": r.caso.pergunta,
            "passou": r.passou,
            "latencia_s": round(r.latencia_s, 2),
            "resposta": r.resposta,
            "tools_chamadas": [c["tool"] for c in r.chamadas],
            "checks": [{"nome": c.nome, "passou": c.passou, "detalhe": c.detalhe}
                       for c in r.checks],
            "nota": r.caso.nota,
        })
    return json.dumps(payload, ensure_ascii=False, indent=2)


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Suíte de avaliação do agente de RH")
    parser.add_argument("--sem-juiz", action="store_true",
                        help="pula o LLM-as-judge (só checagens determinísticas)")
    parser.add_argument("--categoria", help="roda só uma categoria")
    parser.add_argument("--quieto", action="store_true", help="sem log por caso")
    args = parser.parse_args()

    casos = CASOS
    if args.categoria:
        casos = [c for c in CASOS if c.categoria == args.categoria]
        if not casos:
            print(f"Nenhum caso na categoria '{args.categoria}'.")
            return 1

    def progresso(caso):
        if not args.quieto:
            print(f"  [{caso.id}] {caso.categoria}: {caso.pergunta[:60]}...")

    print(f"Rodando {len(casos)} caso(s)...")
    resultados = await rodar_suite(casos, usar_juiz=not args.sem_juiz, progresso=progresso)

    ok = sum(1 for r in resultados if r.passou)
    print(f"\n=== {ok}/{len(resultados)} passaram ===")
    for r in resultados:
        if not r.passou:
            falhas = ", ".join(c.nome for c in r.checks if not c.passou)
            print(f"  ❌ {r.caso.id}: {falhas}")

    with open("evals/resultados.json", "w", encoding="utf-8") as f:
        f.write(_gerar_json(resultados))
    # Só regrava o EVALS.md numa rodada completa (não em subconjuntos filtrados)
    if not args.categoria:
        with open("EVALS.md", "w", encoding="utf-8") as f:
            f.write(_gerar_markdown(resultados, usou_juiz=not args.sem_juiz))
        print("\nEscrito: EVALS.md + evals/resultados.json")
    else:
        print("\nEscrito: evals/resultados.json (EVALS.md preservado — rodada filtrada)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
