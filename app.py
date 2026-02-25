import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import json
import random
import re
import hashlib
import time
import concurrent.futures
from typing import List, Dict, Any, Optional, Tuple
from groq import Groq
from openai import OpenAI
from duckduckgo_search import DDGS

# =========================================================
# CONFIGURAÇÃO GLOBAL E ESTILO
# =========================================================
st.set_page_config(
    page_title="Plataforma de Alta Performance",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(
    """
    <style>
    .metric-box { background-color: #f8f9fa; border-radius: 10px; padding: 20px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #e9ecef; }
    .metric-title { font-size: 14px; color: #6c757d; font-weight: 600; text-transform: uppercase; }
    .metric-value { font-size: 32px; font-weight: 700; color: #212529; margin-top: 5px; }
    .stRadio > div { flex-direction: row; gap: 15px; }
    .alt-correta  { padding: 10px; background-color: #d4edda; border-left: 5px solid #28a745; border-radius: 5px; margin-bottom: 2px; }
    .alt-errada   { padding: 10px; background-color: #f8d7da; border-left: 5px solid #dc3545; border-radius: 5px; margin-bottom: 2px; }
    .alt-neutra   { padding: 10px; border-left: 5px solid #e9ecef; margin-bottom: 2px; color: #495057; }
    .alt-gabarito { padding: 10px; background-color: #cce5ff; border-left: 5px solid #004085; border-radius: 5px; margin-bottom: 2px; font-weight: bold; }
    .comentario-alt { font-size: 0.9em; color: #555; margin-left: 15px; margin-bottom: 12px; border-left: 2px solid #ccc; padding-left: 10px; background-color: #fdfdfd; padding-top: 5px; padding-bottom: 5px; }
    .dificuldade-badge { display: inline-block; padding: 5px 12px; border-radius: 20px; font-weight: 600; font-size: 12px; }
    .dif-facil   { background-color: #d4edda; color: #155724; }
    .dif-medio   { background-color: #fff3cd; color: #856404; }
    .dif-dificil { background-color: #f8d7da; color: #721c24; }
    .tipo-badge  { display: inline-block; padding: 4px 10px; border-radius: 15px; font-size: 11px; font-weight: bold; margin-right: 5px; }
    .tipo-inedita { background-color: #ffd700; color: #333; }
    .tipo-real    { background-color: #87ceeb; color: #000; }
    .concurso-box { background-color: #1a1a2e; color: #e0e0e0; border-left: 5px solid #e94560; padding: 14px; border-radius: 8px; margin-bottom: 16px; }
    .concurso-box b { color: #e94560; }
    </style>
    """,
    unsafe_allow_html=True
)

# =========================================================
# CONSTANTES DE PERFIL
# =========================================================
PERFIL_BANCAS = {
    "Cebraspe": {
        "formatos": ["Certo/Errado"],
        "caracteristicas": [
            "assertivas precisas com pegadinhas em exceções e jurisprudência",
            "interpretação literal e sistemática de normas",
            "tese firmada em repercussão geral/recursos repetitivos"
        ],
        "quantidade_alternativas": 2,
        "estilo_enunciado": "objetivo, assertivo, com pegadinhas sutis",
        "dificuldade_base": 4,
    },
    "FCC": {
        "formatos": ["Múltipla Escolha (A a E)"],
        "caracteristicas": [
            "análise textual minuciosa",
            "distinção entre institutos similares",
            "aplicação a casos concretos"
        ],
        "quantidade_alternativas": 5,
        "estilo_enunciado": "contextualizado com caso concreto",
        "dificuldade_base": 3,
    },
    "Vunesp": {
        "formatos": ["Múltipla Escolha (A a E)"],
        "caracteristicas": [
            "jurisprudência recente",
            "casos práticos com múltiplos institutos",
            "aplicação prática com resultado específico"
        ],
        "quantidade_alternativas": 5,
        "estilo_enunciado": "descritivo com situação fática",
        "dificuldade_base": 3,
    },
}

PERFIL_CARGO_DIFICULDADE = {
    "Delegado de Polícia Civil": {
        "nível": 5, "descrição": "Muito Difícil — Nível Magistratura",
        "exige": [
            "CPP, CP, Leis 11.343/06, 12.850/13, 9.296/96, 13.964/19",
            "Jurisprudência STF/STJ sobre prisões, provas e investigação"
        ]
    },
    "Delegado": {
        "nível": 5, "descrição": "Muito Difícil — Nível Magistratura",
        "exige": ["CPP, CP, legislação penal especial", "jurisprudência STF/STJ atualizada"]
    },
    "Juiz de Direito": {
        "nível": 5, "descrição": "Muito Difícil — Nível Magistratura",
        "exige": ["processo civil e penal avançado", "precedentes e controle de constitucionalidade"]
    },
    "Analista": {
        "nível": 3, "descrição": "Médio",
        "exige": ["conceitos sólidos", "casos práticos padrão"]
    },
}

# =========================================================
# CLIENTES DE MODELO
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
# BANCO DE DADOS E MIGRAÇÕES
# =========================================================
@st.cache_resource
def iniciar_conexao():
    conn = sqlite3.connect("estudos_multi_user.db", check_same_thread=False)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS usuarios (nome TEXT PRIMARY KEY)")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS questoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            banca TEXT, cargo TEXT, materia TEXT, tema TEXT,
            enunciado TEXT, alternativas TEXT, gabarito TEXT,
            explicacao TEXT, tipo TEXT, fonte TEXT,
            dificuldade INTEGER DEFAULT 3, tags TEXT DEFAULT '[]',
            formato_questao TEXT DEFAULT 'Múltipla Escolha',
            eh_real INTEGER DEFAULT 0, ano_prova INTEGER DEFAULT 0,
            hash_questao TEXT DEFAULT '',
            subtema TEXT DEFAULT '', juris_citada TEXT DEFAULT '',
            validado INTEGER DEFAULT 0, created_at TEXT DEFAULT ''
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS respostas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT, questao_id INTEGER, resposta_usuario TEXT,
            acertou INTEGER, data TEXT, tempo_resposta INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS editais_salvos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT, nome_concurso TEXT, banca TEXT, cargo TEXT,
            dados_json TEXT, data_analise TEXT,
            nivel_dificuldade INTEGER DEFAULT 3,
            formato_questoes TEXT DEFAULT '[]',
            nome_concurso_completo TEXT DEFAULT ''
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cache_busca (
            chave TEXT PRIMARY KEY,
            conteudo TEXT,
            criado_em TEXT
        )
    """)
    conn.commit()
    return conn

conn = iniciar_conexao()
c = conn.cursor()

def migrar_banco_de_dados(conn):
    cur = conn.cursor()
    colunas_questoes = [
        ("dificuldade", "INTEGER DEFAULT 3"), ("tags", "TEXT DEFAULT '[]'"), 
        ("formato_questao", "TEXT DEFAULT 'Múltipla Escolha'"), ("eh_real", "INTEGER DEFAULT 0"),
        ("ano_prova", "INTEGER DEFAULT 0"), ("hash_questao", "TEXT DEFAULT ''"),
        ("subtema", "TEXT DEFAULT ''"), ("juris_citada", "TEXT DEFAULT ''"),
        ("validado", "INTEGER DEFAULT 0"), ("created_at", "TEXT DEFAULT ''")
    ]
    for col, tipo in colunas_questoes:
        try: cur.execute(f"ALTER TABLE questoes ADD COLUMN {col} {tipo}"); conn.commit()
        except: pass
        
    colunas_editais = [
        ("nivel_dificuldade", "INTEGER DEFAULT 3"), ("formato_questoes", "TEXT DEFAULT '[]'"),
        ("nome_concurso_completo", "TEXT DEFAULT ''")
    ]
    for col, tipo in colunas_editais:
        try: cur.execute(f"ALTER TABLE editais_salvos ADD COLUMN {col} {tipo}"); conn.commit()
        except: pass

migrar_banco_de_dados(conn)

# =========================================================
# UTILITÁRIOS
# =========================================================
def normalizar_gabarito(gabarito_raw: Any) -> str:
    if not gabarito_raw: return ""
    g = str(gabarito_raw).strip().upper()
    if re.search(r'\bCERTO\b', g): return "CERTO"
    if re.search(r'\bERRADO\b', g): return "ERRADO"
    match = re.match(r'^([A-E])[^A-Z]', g)
    if match: return match.group(1)
    if len(g) == 1 and g in "ABCDE": return g
    match = re.search(r'\b(?:LETRA|ALT(?:ERNATIVA)?|OPÇ?AO)\s+([A-E])\b', g)
    if match: return match.group(1)
    match = re.search(r'\b([A-E])\b', g)
    if match: return match.group(1)
    return g

def extrair_letra_opcao(opcao_texto: Any, tem_alternativas: bool) -> str:
    texto = str(opcao_texto).strip().upper()
    if texto in ("CERTO", "ERRADO"): return texto
    if re.search(r'\bCERTO\b', texto): return "CERTO"
    if re.search(r'\bERRADO\b', texto): return "ERRADO"
    if tem_alternativas:
        match = re.match(r'^([A-E])\)', texto)
        if match: return match.group(1)
        match = re.match(r'^([A-E])\b', texto)
        if match: return match.group(1)
    return texto

def gerar_hash_questao(enunciado: str, gabarito: str, materia: str, tema: str, banca: str, cargo: str) -> str:
    base = f"{enunciado.strip().lower()}|{gabarito}|{materia}|{tema}|{banca}|{cargo}"
    return hashlib.sha256(base.encode()).hexdigest()

def questao_ja_existe(hash_questao: str) -> bool:
    c.execute("SELECT id FROM questoes WHERE hash_questao = ?", (hash_questao,))
    return c.fetchone() is not None

def obter_perfil_cargo(cargo_nome: str) -> Dict[str, Any]:
    cargo_upper = cargo_nome.upper()
    melhor_chave, maior_len = None, 0
    for chave in PERFIL_CARGO_DIFICULDADE:
        if chave.upper() in cargo_upper or cargo_upper in chave.upper():
            if len(chave) > maior_len:
                melhor_chave = chave
                maior_len = len(chave)
    if melhor_chave: return PERFIL_CARGO_DIFICULDADE[melhor_chave]
    return {"nível": 3, "descrição": "Médio"}

def obter_perfil_banca(banca_nome: str) -> Dict[str, Any]:
    for chave, valor in PERFIL_BANCAS.items():
        if chave.lower() in banca_nome.lower() or banca_nome.lower() in chave.lower():
            return valor
    return {"formatos": ["Múltipla Escolha (A a E)"], "quantidade_alternativas": 5, "estilo_enunciado": "padrão", "dificuldade_base": 3}

def sanitize_text(txt: str, max_chars: int) -> str:
    return re.sub(r'\s+', ' ', txt or '')[:max_chars]

def fingerprint(text: str) -> str:
    tokens = re.findall(r'\w+', text.lower())
    return hashlib.md5(" ".join([t for t in tokens if len(t) > 3][:80]).encode()).hexdigest()

def similar(a: str, b: str, threshold: float = 0.35) -> bool:
    sa, sb = set(re.findall(r'\w+', a.lower())), set(re.findall(r'\w+', b.lower()))
    if not sa or not sb: return False
    return (len(sa & sb) / len(sa | sb)) >= threshold

# =========================================================
# CACHE E BUSCA PARALELA BLINDADA (SEM ERROS SQLITE)
# =========================================================
def get_cache(chave: str, max_age_seconds: int = 86400) -> Optional[str]:
    c.execute("SELECT conteudo, criado_em FROM cache_busca WHERE chave = ?", (chave,))
    row = c.fetchone()
    if not row: return None
    try:
        if time.time() - datetime.fromisoformat(row[1]).timestamp() > max_age_seconds: return None
        return row[0]
    except Exception: return None

def set_cache(chave: str, conteudo: str):
    c.execute("REPLACE INTO cache_busca (chave, conteudo, criado_em) VALUES (?,?,?)", (chave, conteudo, datetime.now().isoformat()))
    conn.commit()

def buscar_ddg(queries: List[str], max_res: int = 6, max_chars: int = 8000, cache_prefix: str = "") -> str:
    resultados = []
    queries_to_fetch = []
    cache_mapping = {}
    
    # 1. Leitura sequencial do banco de dados (Seguro)
    for q in queries:
        cache_key = f"{cache_prefix}:{hashlib.md5(q.encode()).hexdigest()}"
        cached = get_cache(cache_key)
        if cached: cache_mapping[q] = cached
        else: queries_to_fetch.append(q)

    # 2. Busca na web em paralelo (Nenhuma operação no banco aqui dentro!)
    def fetch_single_query(q):
        try:
            ddgs = DDGS()
            res = ddgs.text(q, max_results=max_res)
            return q, sanitize_text("\n---\n".join([r.get("body", "") for r in res]), max_chars)
        except Exception: return q, ""

    if queries_to_fetch:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(queries_to_fetch), 5)) as executor:
            fetched_results = list(executor.map(fetch_single_query, queries_to_fetch))
        
        # 3. Gravação sequencial no banco de dados (Seguro)
        for q, texto_limpo in fetched_results:
            if texto_limpo:
                cache_mapping[q] = texto_limpo
                cache_key = f"{cache_prefix}:{hashlib.md5(q.encode()).hexdigest()}"
                set_cache(cache_key, texto_limpo)
    
    for q in queries:
        if q in cache_mapping and cache_mapping[q]: resultados.append(cache_mapping[q])
            
    return "\n---\n".join(resultados)[:max_chars]

# =========================================================
# RAG LEVE / CONTEXTO
# =========================================================
def pesquisar_jurisprudencia_avancada(banca, cargo, concurso, materia, tema):
    return buscar_ddg([
        f'"{materia}" "{tema}" STJ STF jurisprudência 2023 2024 informativo',
        f'"{tema}" "{materia}" precedente vinculante STF tese repercussão geral',
        f'"{cargo}" "{materia}" "{tema}" questão julgado recente STJ informativo'
    ], max_res=5, max_chars=4000, cache_prefix="juris")

def pesquisar_padrao_banca_cargo(banca, cargo, concurso):
    return buscar_ddg([
        f'"{banca}" "{cargo}" padrão questões dificuldade nível concurso análise',
        f'"{concurso}" análise prova questões dificuldade'
    ], max_res=5, max_chars=3000, cache_prefix="padrao")

def pesquisar_conteudo_programatico_especifico(cargo, concurso, materia):
    return buscar_ddg([
        f'"{concurso}" conteúdo programático "{materia}" edital tópicos',
        f'"{cargo}" "{materia}" temas mais cobiados concurso público'
    ], max_res=4, max_chars=3000, cache_prefix="edital")

def pesquisar_questoes_reais_banca(banca, cargo, concurso, materia, tema, quantidade):
    return buscar_ddg([
        f'questão prova "{concurso}" "{banca}" "{materia}" gabarito resolução',
        f'"{banca}" "{cargo}" "{materia}" prova concurso gabarito site:tecconcursos.com.br',
        f'"{banca}" "{cargo}" "{materia}" site:qconcursos.com questão gabarito'
    ], max_res=8, max_chars=6000, cache_prefix="reais")

# =========================================================
# PROMPTS
# =========================================================
def prompt_questoes_ineditas(qtd, banca, cargo, concurso, materia, tema, contexto_juris, contexto_padrao, contexto_edital):
    formato = obter_perfil_banca(banca)["formatos"][0]
    nivel = obter_perfil_cargo(cargo).get("nível", 3)
    if "Certo/Errado" in formato: exemplo_alts = '"alternativas": {}'
    elif "A a D" in formato: exemplo_alts = '"alternativas": {"A": "...", "B": "...", "C": "...", "D": "..."}'
    else: exemplo_alts = '"alternativas": {"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."}'

    return f"""
Você é um elaborador de questões de alto nível para concursos.
1) Enunciado com caso concreto.
2) Cite ao menos uma jurisprudência STF/STJ na explicação.
3) Nível {nivel}/5, padrão {cargo} e banca {banca}.

CONCURSO: {concurso} | MATÉRIA: {materia} | TEMA: {tema} | FORMATO: {formato}
[JURIS] {contexto_juris[:1500]}
[PADRÃO BANCA] {contexto_padrao[:1000]}

Gere {qtd} questões inéditas.
Responda APENAS com JSON válido:
{{
  "questoes": [
    {{
      "enunciado": "Caso concreto...",
      {exemplo_alts},
      "gabarito": "A",
      "explicacao": "Fundamente com lei/tese.",
      "comentarios": {{"A": "...", "B": "..."}},
      "fonte": "Inédita IA — {banca}",
      "dificuldade": {nivel},
      "tags": ["{materia}", "{tema}", "{cargo}"],
      "formato": "{formato}",
      "eh_real": 0
    }}
  ]
}}
"""

def prompt_questoes_reais(qtd, banca, cargo, concurso, materia, tema, contexto_reais):
    formato = obter_perfil_banca(banca)["formatos"][0]
    nivel = obter_perfil_cargo(cargo).get("nível", 3)
    if "Certo/Errado" in formato: exemplo_alts = '"alternativas": {}'
    elif "A a D" in formato: exemplo_alts = '"alternativas": {"A": "...", "B": "...", "C": "...", "D": "..."}'
    else: exemplo_alts = '"alternativas": {"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."}'

    return f"""
Você é um preparador especializado. Transcreva {qtd} questões reais da banca {banca}.
MATÉRIA: {materia} | TEMA: {tema} | FORMATO: {formato}
CONTEXTO REAIS: {contexto_reais[:4000]}

Responda somente com JSON:
{{
  "questoes": [
    {{
      "enunciado": "Enunciado completo real",
      {exemplo_alts},
      "gabarito": "A",
      "explicacao": "Fundamentação real",
      "comentarios": {{"A": "...", "B": "..."}},
      "fonte": "{banca} — Prova Real",
      "dificuldade": {nivel},
      "tags": ["{materia}", "prova-real"],
      "formato": "{formato}",
      "eh_real": 1,
      "ano_prova": 2023
    }}
  ]
}}
"""

# =========================================================
# VALIDAÇÃO, RANQUEAMENTO E DEDUP
# =========================================================
def validar_questao(q: Dict[str, Any]) -> bool:
    gab = normalizar_gabarito(q.get("gabarito", ""))
    if gab not in ["A", "B", "C", "D", "E", "CERTO", "ERRADO"]: return False
    return True

def score_questao(q: Dict[str, Any]) -> float:
    score = min(len(q.get("enunciado", "")) / 220.0, 4.5) + min(len(q.get("explicacao", "")) / 320.0, 3.5)
    score += 1 if re.search(r'STF|STJ', q.get("explicacao", ""), re.IGNORECASE) else 0
    return score

def dedup_lista(lista: List[Dict[str, Any]], materia: str, tema: str, banca: str, cargo: str) -> List[Dict[str, Any]]:
    vistos, res = {}, []
    for q in lista:
        h = gerar_hash_questao(q.get("enunciado", ""), normalizar_gabarito(q.get("gabarito", "")), materia, tema, banca, cargo)
        fp = fingerprint(q.get("enunciado", ""))
        if h in vistos or any(similar(q.get("enunciado", ""), v) for v in vistos.values()): continue
        vistos[h] = fp
        q["hash_calc"] = h
        res.append(q)
    return res

# =========================================================
# LLM CALL (EXTRATOR BLINDADO)
# =========================================================
def gerar_questoes(qtd, origem, banca, cargo, concurso, materia, tema, usar_web, modelo_escolhido):
    qtd_interno = max(qtd * 2, qtd + 2)
    contexto_juris = contexto_padrao = contexto_edital = contexto_reais = ""
    
    if usar_web:
        if origem == "Ineditas":
            contexto_juris = pesquisar_jurisprudencia_avancada(banca, cargo, concurso, materia, tema)
            contexto_padrao = pesquisar_padrao_banca_cargo(banca, cargo, concurso)
            contexto_edital = pesquisar_conteudo_programatico_especifico(cargo, concurso, materia)
        else:
            contexto_reais = pesquisar_questoes_reais_banca(banca, cargo, concurso, materia, tema, qtd_interno)

    prompt = prompt_questoes_ineditas(qtd_interno, banca, cargo, concurso, materia, tema, contexto_juris, contexto_padrao, contexto_edital) if origem == "Ineditas" else prompt_questoes_reais(qtd_interno, banca, cargo, concurso, materia, tema, contexto_reais)
    
    messages = [{"role": "system", "content": "Gere APENAS JSON válido."}, {"role": "user", "content": prompt}]
    
    if "groq" in modelo_escolhido:
        resp = client_groq.chat.completions.create(messages=messages, model="llama-3.3-70b-versatile", temperature=0.7 if origem == "Ineditas" else 0.1)
    else:
        resp = client_deepseek.chat.completions.create(messages=messages, model="deepseek-chat", temperature=0.7 if origem == "Ineditas" else 0.1, response_format={"type": "json_object"})

    conteudo = resp.choices[0].message.content
    match = re.search(r'\{.*\}', conteudo, re.DOTALL) # Extrator Seguro
    conteudo_limpo = match.group(0) if match else conteudo
        
    try: dados = json.loads(conteudo_limpo.replace("```json", "").replace("```", "").strip())
    except Exception as e: raise RuntimeError(f"Falha de JSON: {e}")

    lista = dados.get("questoes", []) if isinstance(dados, dict) else (dados if isinstance(dados, list) else [])
    for q in lista: q.update({"materia": materia, "tema": tema, "banca": banca, "cargo": cargo})
    lista_validas = [q for q in dedup_lista(lista, materia, tema, banca, cargo) if validar_questao(q)]
    lista_validas.sort(key=score_questao, reverse=True)
    return lista_validas[:qtd], len(lista), len(lista_validas)

# =========================================================
# ESTADO E SIDEBAR
# =========================================================
if "usuario_atual" not in st.session_state: st.session_state.usuario_atual = None
if "bateria_atual" not in st.session_state: st.session_state.bateria_atual = []
if "edital_ativo" not in st.session_state: st.session_state.edital_ativo = None
if "tema_cooldown" not in st.session_state: st.session_state.tema_cooldown = []

with st.sidebar:
    st.title("👤 Perfil")
    df_users = pd.read_sql_query("SELECT nome FROM usuarios", conn)
    usuario_sel = st.selectbox("Selecione o Perfil", ["Novo Usuário..."] + df_users["nome"].tolist())
    if usuario_sel == "Novo Usuário...":
        novo_nome = st.text_input("Nome/Login:")
        if st.button("Criar e Entrar", use_container_width=True) and novo_nome:
            try:
                c.execute("INSERT INTO usuarios (nome) VALUES (?)", (novo_nome.strip(),)); conn.commit()
                st.session_state.usuario_atual = novo_nome.strip(); st.rerun()
            except sqlite3.IntegrityError: st.error("Nome já existe.")
    else:
        st.session_state.usuario_atual = usuario_sel

    st.divider()
    motor_escolhido = st.radio("🧠 IA:", ["Groq (Llama3)", "DeepSeek"])
    st.divider()

    if st.session_state.usuario_atual:
        df_editais = pd.read_sql_query("SELECT * FROM editais_salvos WHERE usuario = ? ORDER BY id DESC", conn, params=(st.session_state.usuario_atual,))
        if not df_editais.empty:
            escolha = st.selectbox("Carregar Edital", ["Selecione..."] + [f"{r['nome_concurso']} ({r['cargo']})" for _, r in df_editais.iterrows()])
            if escolha != "Selecione...":
                linha = df_editais.iloc[["Selecione..."].index(escolha) - 1 if escolha in ["Selecione..."] else df_editais[df_editais['nome_concurso'] == escolha.split(" (")[0]].index[0]]
                st.session_state.edital_ativo = {
                    "nome_concurso": linha["nome_concurso"], "banca": linha["banca"], "cargo": linha["cargo"],
                    "materias": json.loads(linha["dados_json"])["materias"], "nivel_dificuldade": obter_perfil_cargo(linha["cargo"])["nível"]
                }
                st.success("✅ Edital carregado!")
        with st.expander("➕ Novo Edital"):
            nome_novo, banca_nova, cargo_novo = st.text_input("Nome:"), st.text_input("Banca:"), st.text_input("Cargo:")
            texto_colado = st.text_area("Conteúdo Programático:")
            if st.button("💾 Salvar") and nome_novo and texto_colado:
                resp = client_groq.chat.completions.create(messages=[{"role": "user", "content": f"Extraia as disciplinas em JSON: {{\"materias\": [\"Disc 1\"]}}. Texto: {texto_colado[:5000]}"}], model="llama-3.3-70b-versatile", response_format={"type": "json_object"})
                c.execute("INSERT INTO editais_salvos (usuario, nome_concurso, banca, cargo, dados_json, nivel_dificuldade) VALUES (?,?,?,?,?,?)", (st.session_state.usuario_atual, nome_novo, banca_nova, cargo_novo, resp.choices[0].message.content, obter_perfil_cargo(cargo_novo)["nível"]))
                conn.commit(); st.rerun()

# =========================================================
# TELA PRINCIPAL
# =========================================================
if not st.session_state.usuario_atual: st.stop()

st.title(f"📚 Plataforma — {st.session_state.usuario_atual}")
df_resp = pd.read_sql_query("SELECT * FROM respostas WHERE usuario = ?", conn, params=(st.session_state.usuario_atual,))
total_resp = len(df_resp)
acertos = int(df_resp["acertou"].sum()) if total_resp > 0 else 0
taxa_acerto = round((acertos / total_resp) * 100, 1) if total_resp > 0 else 0

colA, colB, colC = st.columns(3)
colA.markdown(f'<div class="metric-box"><div class="metric-title">Resolvidos</div><div class="metric-value">{total_resp}</div></div>', unsafe_allow_html=True)
colB.markdown(f'<div class="metric-box"><div class="metric-title">Acertos</div><div class="metric-value">{acertos}</div></div>', unsafe_allow_html=True)
cor_taxa = "#28a745" if taxa_acerto >= 70 else "#dc3545"
colC.markdown(f'<div class="metric-box"><div class="metric-title">Aproveitamento</div><div class="metric-value" style="color:{cor_taxa};">{taxa_acerto}%</div></div>', unsafe_allow_html=True)

with st.container(border=True):
    st.subheader("⚡ Gerar Bateria")
    if st.session_state.edital_ativo:
        e = st.session_state.edital_ativo
        banca_alvo, cargo_alvo = e["banca"], e["cargo"]
        mat_sel = st.selectbox("Matéria", ["Aleatório"] + e["materias"])
        tema_sel = st.text_input("Tema específico", "Aleatório")
    else:
        c1, c2, c3 = st.columns(3)
        banca_alvo, cargo_alvo, mat_sel = c1.text_input("Banca", "Cebraspe"), c2.text_input("Cargo", "Delegado"), c3.text_input("Matéria", "Penal")
        tema_sel = st.text_input("Tema específico", "Aleatório")

    c3col, c4col = st.columns(2)
    tipo = c3col.selectbox("Origem", ["🧠 Inéditas IA", "🌐 Questões Reais", "📂 Revisão (Focada em Erros)"])
    qtd = c4col.slider("Quantidade", 1, 10, 5)
    usar_web = st.checkbox("🌐 Pesquisa web avançada", value=True)

    if st.button("🚀 Forjar Bateria", type="primary", use_container_width=True):
        mat_final = random.choice(e["materias"]) if st.session_state.edital_ativo and mat_sel == "Aleatório" else mat_sel
        tema_final = tema_sel if tema_sel != "Aleatório" else f"Tema complexo de {mat_final}"
        
        if "Revisão" in tipo:
            st.info("🔄 Resgatando questões (priorizando erros)...")
            c.execute("""
                SELECT q.id FROM questoes q LEFT JOIN respostas r ON q.id = r.questao_id AND r.usuario = ?
                WHERE (q.banca LIKE ? OR q.cargo LIKE ? OR q.materia LIKE ?)
                ORDER BY CASE WHEN r.acertou = 0 THEN 1 ELSE 2 END, RANDOM() LIMIT ?
            """, (st.session_state.usuario_atual, f"%{banca_alvo}%", f"%{cargo_alvo}%", f"%{mat_final}%", qtd))
            ids = [row[0] for row in c.fetchall()]
            if ids: st.session_state.bateria_atual = ids; st.rerun()
            else: st.warning("Banco local insuficiente.")
        else:
            progresso = st.progress(25, text="Buscando contexto...")
            try:
                lista, _, _ = gerar_questoes(qtd, "Ineditas" if "Inéditas" in tipo else "Reais", banca_alvo, cargo_alvo, "Concurso", mat_final, tema_final, usar_web, "groq" if "Groq" in motor_escolhido else "deepseek")
                progresso.progress(75, text="Salvando no banco...")
                novas_ids = []
                for q in lista:
                    gab_norm = normalizar_gabarito(q.get("gabarito", ""))
                    hash_q = q.get("hash_calc") or gerar_hash_questao(q.get("enunciado", ""), gab_norm, mat_final, tema_final, banca_alvo, cargo_alvo)
                    if questao_ja_existe(hash_q): continue
                    c.execute("""
                        INSERT INTO questoes (banca, cargo, materia, tema, enunciado, alternativas, gabarito, explicacao, tipo, fonte, dificuldade, tags, formato_questao, eh_real, ano_prova, hash_questao, subtema, juris_citada, validado, created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (banca_alvo, cargo_alvo, mat_final, tema_final, q.get("enunciado", ""), json.dumps(q.get("alternativas", {})), gab_norm, json.dumps({"geral": q.get("explicacao", ""), "detalhes": q.get("comentarios", {})}), tipo, q.get("fonte", "IA"), 3, "[]", q.get("formato", "Múltipla Escolha"), 1 if "Reais" in tipo else 0, 0, hash_q, "", "", 1, datetime.now().isoformat()))
                    novas_ids.append(c.lastrowid)
                conn.commit()
                st.session_state.bateria_atual = novas_ids
                progresso.progress(100, text="✅ Concluído!"); st.rerun()
            except Exception as err:
                progresso.empty(); st.error(f"❌ Erro: {err}")

# =========================================================
# CADERNO DE PROVA
# =========================================================
if st.session_state.bateria_atual:
    st.write("---"); st.subheader("🎯 Caderno de Prova")
    df_respostas = pd.read_sql_query(f"SELECT questao_id, resposta_usuario, acertou FROM respostas WHERE usuario = '{st.session_state.usuario_atual}' AND questao_id IN ({','.join(map(str, st.session_state.bateria_atual))})", conn)
    respondidas = df_respostas.set_index("questao_id").to_dict("index")

    for i, q_id in enumerate(st.session_state.bateria_atual):
        c.execute("SELECT banca, cargo, materia, enunciado, alternativas, gabarito, explicacao, fonte, dificuldade, tags, formato_questao, eh_real FROM questoes WHERE id = ?", (q_id,))
        dados = c.fetchone()
        if not dados: continue

        q_banca, q_cargo, q_mat, q_enun, q_alt, q_gab, q_exp, q_fonte, q_dif, q_tags, q_formato, eh_real = dados
        alts = json.loads(q_alt) if q_alt else {}
        q_gab_norm = normalizar_gabarito(q_gab)
        is_certo_errado = "Certo/Errado" in str(q_formato)
        
        try: exp_data = json.loads(q_exp); exp_geral, exp_detalhes = exp_data.get("geral", q_exp), exp_data.get("detalhes", {})
        except: exp_geral, exp_detalhes = q_exp, {}

        opcoes = ["Selecionar...", "Certo", "Errado"] if is_certo_errado else (["Selecionar..."] + [f"{k}) {v}" for k, v in alts.items()]) if alts else ["Selecionar...", "A", "B", "C", "D", "E"]

        with st.container(border=True):
            col_info, col_tipo = st.columns([4, 1])
            col_info.caption(f"**Item {i+1}** | 🏢 {q_banca} | 📚 {q_mat}")
            col_tipo.markdown(f"<span class='tipo-badge {'tipo-real' if eh_real else 'tipo-inedita'}'>{'Prova Real' if eh_real else 'Inédita IA'}</span>", unsafe_allow_html=True)
            st.markdown(f"#### {q_enun}")

            if q_id in respondidas:
                status = respondidas[q_id]
                resp_salva = normalizar_gabarito(str(status["resposta_usuario"]))
                st.markdown("<br><b>Análise:</b>", unsafe_allow_html=True)
                for opcao in opcoes[1:]:
                    letra_opcao = extrair_letra_opcao(opcao, not is_certo_errado)
                    if letra_opcao == resp_salva:
                        st.markdown(f"<div class='{'alt-correta' if status['acertou']==1 else 'alt-errada'}'>{'✅' if status['acertou']==1 else '❌'} <b>{opcao}</b> (Sua Resposta)</div>", unsafe_allow_html=True)
                    elif letra_opcao == q_gab_norm and status["acertou"] == 0:
                        st.markdown(f"<div class='alt-gabarito'>🎯 <b>{opcao}</b> (Gabarito Oficial)</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div class='alt-neutra'>{opcao}</div>", unsafe_allow_html=True)
                    if not is_certo_errado and letra_opcao in exp_detalhes and exp_detalhes[letra_opcao]:
                        st.markdown(f"<div class='comentario-alt'>💡 {exp_detalhes[letra_opcao]}</div>", unsafe_allow_html=True)
                with st.expander("📖 Fundamentação"): st.write(exp_geral)
            else:
                resp = st.radio("Sua Resposta:", opcoes, key=f"rad_{q_id}", label_visibility="collapsed")
                if st.button("✅ Confirmar", key=f"btn_{q_id}"):
                    if resp != "Selecionar...":
                        letra_esc = extrair_letra_opcao(resp, not is_certo_errado)
                        c.execute("INSERT INTO respostas (usuario, questao_id, resposta_usuario, acertou, data) VALUES (?,?,?,?,?)", (st.session_state.usuario_atual, q_id, letra_esc, 1 if letra_esc == q_gab_norm else 0, str(datetime.now())))
                        conn.commit(); st.rerun()
                    else: st.warning("Selecione uma opção.")
