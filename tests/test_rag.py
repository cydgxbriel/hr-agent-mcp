from langchain_core.embeddings import DeterministicFakeEmbedding

from rag.index import build_index, buscar_politica


def test_index_e_busca_com_fake_embeddings():
    indice = build_index("data/politicas",
                         embeddings=DeterministicFakeEmbedding(size=64))
    resultado = buscar_politica("qual a tolerância de atraso?", indice, k=3)
    assert "[fonte:" in resultado
    assert len(resultado) > 100


def test_chunks_carregam_os_tres_documentos():
    indice = build_index("data/politicas",
                         embeddings=DeterministicFakeEmbedding(size=64))
    fontes = {d.metadata["fonte"] for d in indice.docstore._dict.values()}
    assert fontes == {"politica-de-ponto.md", "banco-de-horas.md", "home-office.md"}
