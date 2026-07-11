"""Chat Streamlit: gate de senha, conversa com o agente e painel de chamadas MCP."""

import asyncio
import hmac
import os
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="HR Agent MCP", page_icon="🕐", layout="wide")

SEGREDOS_EXPORTAVEIS = (
    "OPENAI_API_KEY", "APP_PASSWORD", "GCP_PROJECT_ID",
    "GCP_SERVICE_ACCOUNT_JSON", "HR_DB_PATH",
    "LANGSMITH_TRACING", "LANGSMITH_API_KEY",
)


def _exportar_segredos() -> None:
    """Copia st.secrets -> os.environ (o subprocess MCP herda os.environ)."""
    try:
        for chave in SEGREDOS_EXPORTAVEIS:
            if chave in st.secrets and not os.environ.get(chave):
                os.environ[chave] = str(st.secrets[chave])
    except FileNotFoundError:
        pass  # sem secrets.toml em dev local — .env cobre


_exportar_segredos()


def _gate_de_senha() -> None:
    senha_esperada = os.environ.get("APP_PASSWORD", "")
    if not senha_esperada:
        return  # sem senha configurada (dev local)
    if st.session_state.get("autenticado"):
        return
    st.title("🕐 HR Agent MCP")
    st.caption("Demo protegida — insira a senha de acesso.")
    senha = st.text_input("Senha", type="password")
    if st.button("Entrar") and senha:
        if hmac.compare_digest(senha, senha_esperada):
            st.session_state["autenticado"] = True
            st.rerun()
        st.error("Senha incorreta.")
    st.stop()


_gate_de_senha()

if not os.environ.get("OPENAI_API_KEY"):
    st.error(
        "OPENAI_API_KEY não configurada. Preencha o .env (local) ou os "
        "Secrets (Streamlit Cloud).")
    st.stop()


@st.cache_resource
def _bootstrap():
    """Garante o banco (disco efemero no Streamlit Cloud) e cria o agente."""
    if not Path(os.environ.get("HR_DB_PATH", "data/hr.db")).exists():
        from etl.pipeline import main as rodar_etl

        rodar_etl()
    from agent.graph import build_agent

    loop = asyncio.new_event_loop()
    agente = loop.run_until_complete(build_agent())
    return loop, agente


loop, agente = _bootstrap()

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.historico = []
    st.session_state.chamadas_mcp = []
    st.session_state.interrupt_pendente = None


def _processar(entrada) -> None:
    from agent.graph import executar

    try:
        with st.spinner("Consultando o agente..."):
            resultado = loop.run_until_complete(
                executar(agente, entrada, st.session_state.thread_id))
    except Exception as exc:  # noqa: BLE001 — erro de LLM/rede não vira traceback na UI
        st.session_state.historico.append({
            "role": "assistant",
            "content": (f"⚠️ Tive um problema ao processar ({type(exc).__name__}). "
                        "Tente novamente em instantes."),
        })
        return
    if resultado["chamadas_mcp"]:
        st.session_state.chamadas_mcp.append(resultado["chamadas_mcp"])
    st.session_state.interrupt_pendente = resultado["interrupt"]
    if resultado["resposta"]:
        st.session_state.historico.append(
            {"role": "assistant", "content": resultado["resposta"]})


# ---------- Sidebar: painel de transparencia MCP ----------
with st.sidebar:
    st.header("🔌 Chamadas MCP")
    st.caption("Cada resposta mostra quais ferramentas o agente chamou "
               "no servidor MCP, com os argumentos usados.")
    if not st.session_state.chamadas_mcp:
        st.info("Nenhuma chamada ainda. Pergunte algo!")
    for i, turno in enumerate(st.session_state.chamadas_mcp, start=1):
        with st.expander(f"Turno {i} — {len(turno)} chamada(s)", expanded=True):
            for chamada in turno:
                st.markdown(f"**`{chamada['tool']}`**")
                st.json(chamada["args"])
    st.divider()
    st.caption("Persona: **Ana Souza — Gestora de RH** · dados sintéticos · "
               "[código no GitHub](https://github.com/)")

# ---------- Chat ----------
st.title("🕐 HR Agent MCP")
st.caption("Converse em vez de navegar: batidas, políticas, aprovações e analytics.")

with st.expander("💡 Sugestões de perguntas"):
    st.markdown("""
- *Como foram as batidas do time esta semana?* (cite um nome para detalhar)
- *Qual a tolerância de atraso pela política?*
- *O que está pendente de aprovação?*
- *Aprove o ajuste 1, o sistema estava fora do ar.*
- *Qual equipe fez mais horas extras por mês?*
""")

for msg in st.session_state.historico:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if st.session_state.interrupt_pendente:
    pend = st.session_state.interrupt_pendente
    with st.chat_message("assistant"):
        st.warning(
            f"⚠️ **Confirmação necessária** — aprovar o ajuste "
            f"**#{pend['ajuste_id']}**?\n\nJustificativa: *{pend['justificativa']}*")
        col1, col2 = st.columns(2)
        if col1.button("✅ Confirmar aprovação", type="primary"):
            from langgraph.types import Command

            _processar(Command(resume="confirmar"))
            st.rerun()
        if col2.button("❌ Cancelar"):
            from langgraph.types import Command

            _processar(Command(resume="cancelar"))
            st.rerun()

if st.session_state.interrupt_pendente:
    st.chat_input("Confirme ou cancele a aprovação acima para continuar.", disabled=True)
else:
    pergunta = st.chat_input("Pergunte sobre ponto, políticas, ajustes ou analytics...")
    if pergunta:
        st.session_state.historico.append({"role": "user", "content": pergunta})
        _processar(pergunta)
        st.rerun()
