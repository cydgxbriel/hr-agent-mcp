"""Logica de negocio das tools operacionais, pura e testavel (SQLite)."""

import os
import sqlite3
from datetime import datetime, timezone


def _conectar(db_path: str | None) -> sqlite3.Connection:
    caminho = db_path or os.environ.get("HR_DB_PATH", "data/hr.db")
    conn = sqlite3.connect(caminho)
    conn.row_factory = sqlite3.Row
    return conn


def consultar_batidas(
    nome_colaborador: str, data_inicio: str, data_fim: str, db_path: str | None = None
) -> str:
    try:
        conn = _conectar(db_path)
    except Exception as exc:  # noqa: BLE001 — tool nunca vaza traceback
        return f"Erro ao consultar batidas: {type(exc).__name__}. Tente novamente."
    try:
        colab = conn.execute(
            "SELECT id, nome FROM colaboradores WHERE nome LIKE ? AND id != 1",
            (f"%{nome_colaborador}%",),
        ).fetchone()
        if colab is None:
            return (f"Não encontrei colaborador com nome parecido com "
                    f"'{nome_colaborador}' na equipe.")
        linhas = conn.execute(
            """SELECT data, entrada, saida_almoco, volta_almoco, saida,
                      atraso_minutos, hora_extra_minutos, batida_incompleta
               FROM batidas
               WHERE colaborador_id = ? AND data BETWEEN ? AND ?
               ORDER BY data""",
            (colab["id"], data_inicio, data_fim),
        ).fetchall()
        if not linhas:
            return (f"{colab['nome']} não tem batidas registradas entre "
                    f"{data_inicio} e {data_fim}.")
        saida = [f"Batidas de {colab['nome']} ({data_inicio} a {data_fim}):",
                 "data | entrada | almoço | volta | saída | atraso(min) | extra(min)"]
        for r in linhas:
            alerta = " ⚠️ INCOMPLETA" if r["batida_incompleta"] else ""
            saida.append(
                f"{r['data']} | {r['entrada'] or '—'} | {r['saida_almoco'] or '—'} | "
                f"{r['volta_almoco'] or '—'} | {r['saida'] or '—'} | "
                f"{r['atraso_minutos']} | {r['hora_extra_minutos']}{alerta}")
        return "\n".join(saida)
    except Exception as exc:  # noqa: BLE001 — tool nunca vaza traceback
        return f"Erro ao consultar batidas: {type(exc).__name__}. Tente novamente."
    finally:
        conn.close()


def listar_ajustes_pendentes(db_path: str | None = None) -> str:
    try:
        conn = _conectar(db_path)
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao listar ajustes: {type(exc).__name__}. Tente novamente."
    try:
        linhas = conn.execute(
            """SELECT a.id, c.nome, a.data, a.campo, a.valor_proposto, a.motivo
               FROM ajustes a JOIN colaboradores c ON c.id = a.colaborador_id
               WHERE a.status = 'pendente' ORDER BY a.data""",
        ).fetchall()
        if not linhas:
            return "Não há ajustes de ponto pendentes de aprovação. 🎉"
        saida = [f"Há {len(linhas)} ajuste(s) pendente(s):"]
        for r in linhas:
            saida.append(
                f"#{r['id']} — {r['nome']} | {r['data']} | corrigir '{r['campo']}' "
                f"para {r['valor_proposto']} | motivo: {r['motivo']}")
        return "\n".join(saida)
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao listar ajustes: {type(exc).__name__}. Tente novamente."
    finally:
        conn.close()


def aprovar_ajuste(
    ajuste_id: int, justificativa: str, db_path: str | None = None
) -> str:
    try:
        conn = _conectar(db_path)
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao aprovar ajuste: {type(exc).__name__}. Nada foi gravado."
    try:
        ajuste = conn.execute(
            "SELECT * FROM ajustes WHERE id = ?", (ajuste_id,)).fetchone()
        if ajuste is None:
            return f"Não encontrei ajuste com id {ajuste_id}."
        if ajuste["status"] != "pendente":
            return f"O ajuste #{ajuste_id} já foi processado (status: {ajuste['status']})."

        campo = ajuste["campo"]
        if campo not in ("entrada", "saida_almoco", "volta_almoco", "saida"):
            return f"Campo de ajuste inválido: {campo}."
        conn.execute(
            f"UPDATE batidas SET {campo} = ? WHERE colaborador_id = ? AND data = ?",
            (ajuste["valor_proposto"], ajuste["colaborador_id"], ajuste["data"]))
        conn.execute("UPDATE ajustes SET status = 'aprovado' WHERE id = ?", (ajuste_id,))
        conn.execute(
            """INSERT INTO audit_log (ajuste_id, acao, justificativa, autor, criado_em)
               VALUES (?, 'aprovado', ?, 'Ana Souza (gestora)', ?)""",
            (ajuste_id, justificativa, datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return (f"Ajuste #{ajuste_id} aprovado: '{campo}' corrigido para "
                f"{ajuste['valor_proposto']} em {ajuste['data']}. "
                f"Registrado na trilha de auditoria.")
    except Exception as exc:  # noqa: BLE001
        return f"Erro ao aprovar ajuste: {type(exc).__name__}. Nada foi gravado."
    finally:
        conn.close()
