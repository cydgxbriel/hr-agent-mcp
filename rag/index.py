"""RAG sobre as politicas de RH: chunking + indice FAISS em memoria."""

from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def build_index(pasta: str | Path = "data/politicas", embeddings=None) -> FAISS:
    if embeddings is None:
        from langchain_openai import OpenAIEmbeddings

        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    documentos: list[Document] = []
    for arquivo in sorted(Path(pasta).glob("*.md")):
        for trecho in splitter.split_text(arquivo.read_text(encoding="utf-8")):
            documentos.append(
                Document(page_content=trecho, metadata={"fonte": arquivo.name}))
    return FAISS.from_documents(documentos, embeddings)


def buscar_politica(pergunta: str, indice: FAISS, k: int = 3) -> str:
    resultados = indice.similarity_search(pergunta, k=k)
    if not resultados:
        return "Não encontrei nada relevante nas políticas internas."
    blocos = [f"{doc.page_content}\n[fonte: {doc.metadata['fonte']}]"
              for doc in resultados]
    return "\n\n---\n\n".join(blocos)
