"""Valida a estrutura do dataset de avaliação (sem chamar API)."""

from evals.dataset import CASOS, por_categoria
from evals.scorers import checar_deterministico


def test_ids_unicos():
    ids = [c.id for c in CASOS]
    assert len(ids) == len(set(ids)), "ids de caso duplicados"


def test_todo_caso_tem_ao_menos_uma_checagem():
    for c in CASOS:
        tem_check = (c.tool_esperada or c.tools_proibidas or c.nenhuma_tool
                     or c.contem or c.nao_contem or c.regex or c.interrupt_esperado
                     or c.sem_interrupt or c.rubrica)
        assert tem_check, f"caso {c.id} não tem nenhuma asserção"


def test_casos_de_escrita_sao_isolados():
    # Todo caso que confirma uma aprovação deve rodar contra DB temporário.
    for c in CASOS:
        confirma = any(v == "confirmar" for _, v in c.turnos_extra)
        if confirma:
            assert c.muta_dados, f"caso {c.id} confirma escrita mas não isola o DB"


def test_ajuste_id_esperado_valido():
    # O dataset gerado com seed 42 tem 4 ajustes pendentes (ids 1..4).
    for c in CASOS:
        if c.ajuste_id_esperado is not None:
            assert 1 <= c.ajuste_id_esperado <= 4


def test_scorer_deterministico_puro():
    # checar_deterministico é função pura: mesma entrada, mesmo veredito.
    caso = next(c for c in CASOS if c.id == "A1")
    chamadas = [{"tool": "analytics_rh", "args": {}}]
    resposta = "A equipe Produto acumulou 4.995 minutos de horas extras."
    checks = checar_deterministico(caso, resposta, chamadas, None)
    assert all(c.passou for c in checks)


def test_scorer_detecta_tool_errada():
    caso = next(c for c in CASOS if c.id == "R2")
    checks = checar_deterministico(caso, "resposta qualquer", [], None)
    assert any(c.nome == "tool" and not c.passou for c in checks)


def test_todas_categorias_representadas():
    cats = por_categoria()
    esperadas = {"roteamento", "operacional", "desambiguacao", "politica",
                 "analytics", "escrita", "cruzamento", "governanca"}
    assert set(cats) == esperadas
