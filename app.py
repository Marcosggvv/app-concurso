import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import json
import random
import re
import hashlib
import time
from typing import List, Dict, Any, Optional
from groq import Groq
from openai import OpenAI
from duckduckgo_search import DDGS


# =========================================================
# CONFIGURAÇÃO GLOBAL
# =========================================================
st.set_page_config(
    page_title="Plataforma de Alta Performance",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# PERFIS DE BANCA
# =========================================================
PERFIL_BANCAS = {
    "Cebraspe": {
        "formatos": ["Certo/Errado"],
        "quantidade_alternativas": 2,
        "dificuldade_base": 4,
    },
    "FCC": {
        "formatos": ["Múltipla Escolha (A a E)"],
        "quantidade_alternativas": 5,
        "dificuldade_base": 3,
    },
    "Vunesp": {
        "formatos": ["Múltipla Escolha (A a E)"],
        "quantidade_alternativas": 5,
        "dificuldade_base": 3,
    },
}


PERFIL_CARGO_DIFICULDADE = {
    "Delegado": {
        "nível": 5,
        "descrição": "Muito Difícil — Nível Magistratura"
    },
    "Juiz": {
        "nível": 5,
        "descrição": "Muito Difícil — Nível Magistratura"
    },
    "Analista": {
        "nível": 3,
        "descrição": "Médio"
    }
}


# =========================================================
# CLIENTES DE IA
# =========================================================
try:
    client_groq = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception:
    client_groq = None

try:
    client_deepseek = OpenAI(
        api_key=st.secrets["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com"
    )
except Exception:
    client_deepseek = None


# =========================================================
# BANCO DE DADOS
# =========================================================
@st.cache_resource
def iniciar_conexao():
    conn = sqlite3.connect("estudos_multi_user.db", check_same_thread=False)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        nome TEXT PRIMARY KEY
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS questoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        banca TEXT,
        cargo TEXT,
        materia TEXT,
        tema TEXT,
        enunciado TEXT,
        alternativas TEXT,
        gabarito TEXT,
        explicacao TEXT,
        tipo TEXT,
        fonte TEXT,
        dificuldade INTEGER DEFAULT 3,
        tags TEXT DEFAULT '[]',
        formato_questao TEXT DEFAULT 'Múltipla Escolha',
        eh_real INTEGER DEFAULT 0,
        ano_prova INTEGER DEFAULT 0,
        hash_questao TEXT DEFAULT '',
        fingerprint TEXT DEFAULT '',
        subtema TEXT DEFAULT '',
        juris_citada TEXT DEFAULT '',
        validado INTEGER DEFAULT 0,
        created_at TEXT DEFAULT ''
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS respostas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT,
        questao_id INTEGER,
        resposta_usuario TEXT,
        acertou INTEGER,
        data TEXT
    )
    """)

    conn.commit()
    return conn


conn = iniciar_conexao()
c = conn.cursor()
# =========================================================
# UTILITÁRIOS
# =========================================================

def normalizar_gabarito(g):
    if not g:
        return ""
    g = str(g).strip().upper()

    if "CERTO" in g:
        return "CERTO"
    if "ERRADO" in g:
        return "ERRADO"

    if len(g) == 1 and g in "ABCDE":
        return g

    match = re.search(r'\b([A-E])\b', g)
    if match:
        return match.group(1)

    return g


def gerar_hash_questao(enunciado, gabarito, materia, tema, banca, cargo):
    base = f"{enunciado.strip().lower()}|{gabarito}|{materia}|{tema}|{banca}|{cargo}"
    return hashlib.sha256(base.encode()).hexdigest()


def fingerprint(texto):
    tokens = re.findall(r'\w+', texto.lower())
    tokens = [t for t in tokens if len(t) > 4]
    tokens = sorted(set(tokens))
    base = " ".join(tokens[:120])
    return hashlib.md5(base.encode()).hexdigest()


def similar_hash(fp1, fp2):
    iguais = sum(a == b for a, b in zip(fp1, fp2))
    return iguais / len(fp1)


# =========================================================
# VALIDAÇÃO JURÍDICA FORTE
# =========================================================

def validar_questao(q):

    enun = q.get("enunciado", "")
    gab = normalizar_gabarito(q.get("gabarito", ""))
    alts = q.get("alternativas", {})
    exp = q.get("explicacao", "")

    if len(enun) < 180:
        return False

    if gab not in ["A", "B", "C", "D", "E", "CERTO", "ERRADO"]:
        return False

    if isinstance(alts, dict) and len(alts) < 2:
        return False

    if len(exp) < 350:
        return False

    # Exigir tese real
    if not re.search(r'(Tema\s?\d+|RE\s?\d+|HC\s?\d+|RHC\s?\d+|Informativo\s?\d+)', exp, re.IGNORECASE):
        return False

    return True


# =========================================================
# SCORE AVANÇADO
# =========================================================

def score_questao(q):

    score = 0
    enun = q.get("enunciado", "")
    exp = q.get("explicacao", "")
    alts = q.get("alternativas", {})

    score += min(len(enun) / 250, 4)
    score += min(len(exp) / 400, 4)

    if re.search(r'(Tema\s?\d+|RE\s?\d+|HC\s?\d+)', exp):
        score += 1.5

    if re.search(r'exceç|prazo|competên', " ".join(alts.values()), re.IGNORECASE):
        score += 1

    if re.search(r'Considerando que|Em relação a|No caso apresentado', enun):
        score -= 0.8

    return score


# =========================================================
# DEDUPLICAÇÃO FORTE
# =========================================================

def dedup_lista(lista, materia, tema, banca, cargo):

    vistos_hash = set()
    vistos_fp = []
    resultado = []

    for q in lista:

        gab_norm = normalizar_gabarito(q.get("gabarito", ""))

        hash_q = gerar_hash_questao(
            q.get("enunciado", ""),
            gab_norm,
            materia,
            tema,
            banca,
            cargo
        )

        fp = fingerprint(q.get("enunciado", ""))

        if hash_q in vistos_hash:
            continue

        if any(similar_hash(fp, fprev) > 0.85 for fprev in vistos_fp):
            continue

        vistos_hash.add(hash_q)
        vistos_fp.append(fp)

        q["hash_calc"] = hash_q
        q["fingerprint_calc"] = fp

        resultado.append(q)

    return resultado


# =========================================================
# ADAPTATIVIDADE POR MATÉRIA
# =========================================================

def materia_prioritaria(usuario):

    df = pd.read_sql_query("""
        SELECT q.materia, AVG(r.acertou) as taxa
        FROM respostas r
        JOIN questoes q ON r.questao_id = q.id
        WHERE r.usuario = ?
        GROUP BY q.materia
        ORDER BY taxa ASC
    """, conn, params=(usuario,))

    if not df.empty:
        return df.iloc[0]["materia"]

    return None
    # =========================================================
# CHAMADA DO MODELO
# =========================================================

def chamar_modelo(messages, modelo="groq", temperature=0.7):

    if modelo == "groq":
        if not client_groq:
            raise RuntimeError("Configure GROQ_API_KEY no secrets.toml")

        return client_groq.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile",
            temperature=temperature,
            response_format={"type": "json_object"},
            max_tokens=6000
        )

    else:
        if not client_deepseek:
            raise RuntimeError("Configure DEEPSEEK_API_KEY no secrets.toml")

        return client_deepseek.chat.completions.create(
            messages=messages,
            model="deepseek-chat",
            temperature=temperature,
            response_format={"type": "json_object"},
            max_tokens=6000
        )


# =========================================================
# PROMPT BASE
# =========================================================

def montar_prompt(qtd, banca, cargo, materia, tema):

    return f"""
Você é elaborador de questões de altíssimo nível.

Regras obrigatórias:
- Caso concreto complexo
- Múltiplos institutos em conflito
- Explicação com citação de Tema, RE, HC ou Informativo
- Distratores tecnicamente plausíveis
- Responder APENAS JSON

Formato esperado:

{{
  "questoes": [
    {{
      "enunciado": "...",
      "alternativas": {{
        "A": "...",
        "B": "...",
        "C": "...",
        "D": "...",
        "E": "..."
      }},
      "gabarito": "A",
      "explicacao": "...",
      "comentarios": {{}}
    }}
  ]
}}

Gerar {qtd} questões.

Banca: {banca}
Cargo: {cargo}
Matéria: {materia}
Tema: {tema}
"""


# =========================================================
# GERAR QUESTÕES
# =========================================================

def gerar_questoes(qtd, banca, cargo, materia, tema, modelo="groq"):

    prompt = montar_prompt(qtd * 3, banca, cargo, materia, tema)

    messages = [
        {"role": "system", "content": "Responda apenas JSON válido."},
        {"role": "user", "content": prompt}
    ]

    resp = chamar_modelo(messages, modelo=modelo)
    conteudo = resp.choices[0].message.content

    try:
        dados = json.loads(conteudo)
    except:
        raise RuntimeError("Modelo retornou JSON inválido.")

    lista = dados.get("questoes", [])

    lista = dedup_lista(lista, materia, tema, banca, cargo)

    lista_validas = [q for q in lista if validar_questao(q)]

    lista_validas.sort(key=score_questao, reverse=True)

    return lista_validas[:qtd]


# =========================================================
# SALVAR QUESTÕES NO BANCO
# =========================================================

def salvar_questoes(lista, banca, cargo, materia, tema, tipo="Inédita IA"):

    novas_ids = []
    duplicatas = 0

    for q in lista:

        fingerprint_calc = q.get("fingerprint_calc", fingerprint(q.get("enunciado", "")))
        gab_norm = normalizar_gabarito(q.get("gabarito", ""))

        hash_q = q.get("hash_calc") or gerar_hash_questao(
            q.get("enunciado", ""),
            gab_norm,
            materia,
            tema,
            banca,
            cargo
        )

        c.execute("SELECT id FROM questoes WHERE hash_questao = ?", (hash_q,))
        if c.fetchone():
            duplicatas += 1
            continue

        alternativas = json.dumps(q.get("alternativas", {}))

        explicacao_final = json.dumps({
            "geral": q.get("explicacao", ""),
            "detalhes": q.get("comentarios", {})
        })

        c.execute(
            """
            INSERT INTO questoes
            (banca, cargo, materia, tema, enunciado, alternativas, gabarito, explicacao, tipo, fonte,
             dificuldade, tags, formato_questao, eh_real, ano_prova,
             hash_questao, fingerprint, subtema, juris_citada,
             validado, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                banca,
                cargo,
                materia,
                tema,
                q.get("enunciado", ""),
                alternativas,
                gab_norm,
                explicacao_final,
                tipo,
                f"Inédita IA — {banca}",
                4,
                json.dumps([materia, tema]),
                "Múltipla Escolha",
                0,
                0,
                hash_q,
                fingerprint_calc,
                "",
                "",
                1,
                datetime.now().isoformat()
            )
        )

        novas_ids.append(c.lastrowid)

    conn.commit()

    return novas_ids, duplicatas
    # =========================================================
# ESTADO DE SESSÃO
# =========================================================

if "usuario_atual" not in st.session_state:
    st.session_state.usuario_atual = None

if "bateria_atual" not in st.session_state:
    st.session_state.bateria_atual = []


# =========================================================
# SIDEBAR — LOGIN
# =========================================================

with st.sidebar:

    st.title("👤 Perfil")

    df_users = pd.read_sql_query("SELECT nome FROM usuarios", conn)
    lista_users = df_users["nome"].tolist()

    usuario_sel = st.selectbox("Selecione:", ["Novo Usuário"] + lista_users)

    if usuario_sel == "Novo Usuário":
        novo_nome = st.text_input("Nome:")
        if st.button("Criar"):
            if novo_nome:
                try:
                    c.execute("INSERT INTO usuarios (nome) VALUES (?)", (novo_nome,))
                    conn.commit()
                    st.session_state.usuario_atual = novo_nome
                    st.rerun()
                except:
                    st.error("Usuário já existe.")
    else:
        st.session_state.usuario_atual = usuario_sel

    st.divider()

    modelo_escolhido = st.radio("Modelo IA:", ["Groq", "DeepSeek"])


# =========================================================
# BLOQUEIO SE NÃO LOGADO
# =========================================================

if not st.session_state.usuario_atual:
    st.title("Faça login na barra lateral.")
    st.stop()


# =========================================================
# DASHBOARD
# =========================================================

st.title(f"📚 Plataforma — {st.session_state.usuario_atual}")

df_resp = pd.read_sql_query(
    "SELECT * FROM respostas WHERE usuario = ?",
    conn,
    params=(st.session_state.usuario_atual,)
)

total = len(df_resp)
acertos = int(df_resp["acertou"].sum()) if total else 0
taxa = round((acertos / total) * 100, 1) if total else 0

col1, col2, col3 = st.columns(3)
col1.metric("Resolvidas", total)
col2.metric("Acertos", acertos)
col3.metric("Aproveitamento", f"{taxa}%")


# =========================================================
# GERADOR
# =========================================================

st.divider()
st.subheader("Gerar Questões")

banca = st.text_input("Banca", "Cebraspe")
cargo = st.text_input("Cargo", "Delegado")
materia = st.text_input("Matéria", "Direito Penal")
tema = st.text_input("Tema", "Crimes contra a Administração Pública")

qtd = st.slider("Quantidade", 1, 5, 3)

if st.button("Gerar Agora"):

    materia_erro = materia_prioritaria(st.session_state.usuario_atual)
    if materia_erro:
        materia = materia_erro

    modelo_flag = "groq" if modelo_escolhido == "Groq" else "deepseek"

    with st.spinner("Gerando questões de alto nível..."):

        lista = gerar_questoes(
            qtd=qtd,
            banca=banca,
            cargo=cargo,
            materia=materia,
            tema=tema,
            modelo=modelo_flag
        )

        ids, dup = salvar_questoes(
            lista,
            banca,
            cargo,
            materia,
            tema
        )

        st.session_state.bateria_atual = ids

        st.success(f"{len(ids)} questões geradas. {dup} descartadas.")


# =========================================================
# EXIBIÇÃO DAS QUESTÕES
# =========================================================

if st.session_state.bateria_atual:

    st.divider()
    st.subheader("Caderno")

    for q_id in st.session_state.bateria_atual:

        c.execute("""
            SELECT enunciado, alternativas, gabarito, explicacao
            FROM questoes WHERE id = ?
        """, (q_id,))

        row = c.fetchone()
        if not row:
            continue

        enun, alt_json, gab, exp_json = row

        alternativas = json.loads(alt_json)
        exp_data = json.loads(exp_json)

        st.markdown(f"### {enun}")

        opcoes = ["Selecionar"] + [f"{k}) {v}" for k, v in alternativas.items()]

        resp = st.radio("Resposta:", opcoes, key=f"rad_{q_id}")

        if st.button("Confirmar", key=f"btn_{q_id}"):

            if resp != "Selecionar":

                letra = resp[0]
                gab_norm = normalizar_gabarito(gab)
                acertou = 1 if letra == gab_norm else 0

                c.execute("""
                    INSERT INTO respostas
                    (usuario, questao_id, resposta_usuario, acertou, data)
                    VALUES (?,?,?,?,?)
                """, (
                    st.session_state.usuario_atual,
                    q_id,
                    letra,
                    acertou,
                    str(datetime.now())
                ))

                conn.commit()

                if acertou:
                    st.success("Correto!")
                else:
                    st.error("Errado!")

                with st.expander("Ver Fundamentação"):
                    st.write(exp_data.get("geral", ""))

                st.rerun()
