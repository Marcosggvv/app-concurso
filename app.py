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
    .debug-box    { background-color: #fff8dc; border: 1px dashed #aaa; padding: 8px 12px; border-radius: 5px; font-size: 12px; font-family: monospace; margin-top: 5px; }
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
            "Jurisprudência STF/STJ sobre prisões, provas e investigação",
            "Inquérito, ANPP, colaboração, cadeia de custódia"
        ],
        "estilo_questao": [
            "caso concreto com múltiplos institutos em conflito",
            "jurisprudência recente que alterou entendimento",
            "distinção entre institutos processuais similares"
        ],
        "exemplos_temas_avancados": [
            "cadeia de custódia e consequências processuais",
            "agente infiltrado vs. agente provocador",
            "prisão domiciliar e entendimento do STJ"
        ],
    },
    "Delegado": {
        "nível": 5, "descrição": "Muito Difícil — Nível Magistratura",
        "exige": ["CPP, CP, legislação penal especial", "jurisprudência STF/STJ atualizada"],
        "estilo_questao": ["caso concreto com múltiplos institutos", "jurisprudência recente"],
        "exemplos_temas_avancados": ["Pacote Anticrime", "ANPP", "cadeia de custódia"]
    },
    "Juiz de Direito": {
        "nível": 5, "descrição": "Muito Difícil — Nível Magistratura",
        "exige": ["processo civil e penal avançado", "precedentes e controle de constitucionalidade"],
        "estilo_questao": ["múltiplos recursos/incidentes", "conflito normativo solucionado pelo STF"],
        "exemplos_temas_avancados": ["IRDR", "tutelas de urgência/evidência"]
    },
    "Analista": {
        "nível": 3, "descrição": "Médio",
        "exige": ["conceitos sólidos", "casos práticos padrão"],
        "estilo_questao": ["conceito aplicado a caso", "distinção entre procedimentos"],
        "exemplos_temas_avancados": ["prazos e formalidades", "competências do órgão"]
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
# BANCO DE DADOS
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
            subtema TEXT DEFAULT '',
            juris_citada TEXT DEFAULT '',
            validado INTEGER DEFAULT 0,
            created_at TEXT DEFAULT ''
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

# =========================================================
# UTILITÁRIOS
# =========================================================
def normalizar_gabarito(gabarito_raw: Any) -> str:
    if not gabarito_raw:
        return ""
    g = str(gabarito_raw).strip().upper()
    if re.search(r'\bCERTO\b', g):
        return "CERTO"
    if re.search(r'\bERRADO\b', g):
        return "ERRADO"
    match = re.match(r'^([A-E])[^A-Z]', g)
    if match:
        return match.group(1)
    if len(g) == 1 and g in "ABCDE":
        return g
    match = re.search(r'\b(?:LETRA|ALT(?:ERNATIVA)?|OPÇ?AO)\s+([A-E])\b', g)
    if match:
        return match.group(1)
    match = re.search(r'\b([A-E])\b', g)
    if match:
        return match.group(1)
    return g

def extrair_letra_opcao(opcao_texto: Any, tem_alternativas: bool) -> str:
    texto = str(opcao_texto).strip().upper()
    if texto in ("CERTO", "ERRADO"):
        return texto
    if re.search(r'\bCERTO\b', texto):
        return "CERTO"
    if re.search(r'\bERRADO\b', texto):
        return "ERRADO"
    if tem_alternativas:
        match = re.match(r'^([A-E])\)', texto)
        if match:
            return match.group(1)
        match = re.match(r'^([A-E])\b', texto)
        if match:
            return match.group(1)
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
    if melhor_chave:
        return PERFIL_CARGO_DIFICULDADE[melhor_chave]
    return {"nível": 3, "descrição": "Médio", "exige": ["Padrão"], "estilo_questao": ["Padrão"], "exemplos_temas_avancados": []}

def obter_perfil_banca(banca_nome: str) -> Dict[str, Any]:
    for chave, valor in PERFIL_BANCAS.items():
        if chave.lower() in banca_nome.lower() or banca_nome.lower() in chave.lower():
            return valor
    return {
        "formatos": ["Múltipla Escolha (A a E)"],
        "caracteristicas": ["padrão"],
        "quantidade_alternativas": 5,
        "estilo_enunciado": "padrão",
        "dificuldade_base": 3,
    }

def sanitize_text(txt: str, max_chars: int) -> str:
    return re.sub(r'\s+', ' ', txt or '')[:max_chars]

def fingerprint(text: str) -> str:
    tokens = re.findall(r'\w+', text.lower())
    tokens = [t for t in tokens if len(t) > 3]
    tokens = tokens[:80]
    return hashlib.md5(" ".join(tokens).encode()).hexdigest()

def similar(a: str, b: str, threshold: float = 0.35) -> bool:
    sa = set(re.findall(r'\w+', a.lower()))
    sb = set(re.findall(r'\w+', b.lower()))
    if not sa or not sb:
        return False
    j = len(sa & sb) / len(sa | sb)
    return j >= threshold

# =========================================================
# CACHE DE BUSCA
# =========================================================
def get_cache(chave: str, max_age_seconds: int = 86400) -> Optional[str]:
    c.execute("SELECT conteudo, criado_em FROM cache_busca WHERE chave = ?", (chave,))
    row = c.fetchone()
    if not row:
        return None
    conteudo, criado_em = row
    try:
        ts = datetime.fromisoformat(criado_em).timestamp()
        if time.time() - ts > max_age_seconds:
            return None
        return conteudo
    except Exception:
        return None

def set_cache(chave: str, conteudo: str):
    c.execute(
        "REPLACE INTO cache_busca (chave, conteudo, criado_em) VALUES (?,?,?)",
        (chave, conteudo, datetime.now().isoformat())
    )
    conn.commit()

def buscar_ddg(queries: List[str], max_res: int = 6, max_chars: int = 8000, cache_prefix: str = "") -> str:
    ddgs = DDGS()
    resultados = []
    for q in queries:
        cache_key = f"{cache_prefix}:{hashlib.md5(q.encode()).hexdigest()}"
        cached = get_cache(cache_key)
        if cached:
            resultados.append(cached)
            continue
        try:
            res = ddgs.text(q, max_results=max_res)
            textos = [r.get("body", "") for r in res]
            texto = "\n---\n".join(textos)
            texto = sanitize_text(texto, max_chars)
            resultados.append(texto)
            set_cache(cache_key, texto)
        except Exception:
            continue
    return "\n---\n".join([r for r in resultados if r])[:max_chars]

# =========================================================
# RAG LEVE / CONTEXTO
# =========================================================
def pesquisar_jurisprudencia_avancada(banca, cargo, concurso, materia, tema):
    queries = [
        f'"{materia}" "{tema}" STJ STF jurisprudência 2023 2024 informativo',
        f'"{tema}" "{materia}" precedente vinculante STF tese repercussão geral',
        f'"{cargo}" "{materia}" "{tema}" questão julgado recente STJ informativo',
        f'"{tema}" "{materia}" doutrina conceito distinção institutos concurso',
        f'"{banca}" "{cargo}" "{materia}" banca cobrou jurisprudência gabarito',
    ]
    return buscar_ddg(queries, max_res=5, max_chars=4000, cache_prefix="juris")

def pesquisar_padrao_banca_cargo(banca, cargo, concurso):
    queries = [
        f'"{banca}" "{cargo}" padrão questões dificuldade nível concurso análise',
        f'"{concurso}" análise prova questões dificuldade resolução comentada',
        f'"{banca}" "{cargo}" provas anteriores temas mais cobrados estatísticas',
    ]
    return buscar_ddg(queries, max_res=5, max_chars=3000, cache_prefix="padrao")

def pesquisar_conteudo_programatico_especifico(cargo, concurso, materia):
    queries = [
        f'"{concurso}" conteúdo programático "{materia}" edital tópicos cobrados',
        f'"{cargo}" "{materia}" temas mais cobiados concurso público 2022 2023 2024',
        f'"{concurso}" edital "{materia}" itens exigidos estudo',
    ]
    return buscar_ddg(queries, max_res=4, max_chars=3000, cache_prefix="edital")

def pesquisar_questoes_reais_banca(banca, cargo, concurso, materia, tema, quantidade):
    queries = [
        f'questão prova "{concurso}" "{banca}" "{materia}" gabarito resolução',
        f'"{banca}" "{cargo}" "{materia}" prova concurso gabarito site:tecconcursos.com.br',
        f'"{banca}" "{cargo}" "{materia}" site:qconcursos.com questão gabarito',
        f'concurso "{cargo}" "{banca}" "{materia}" "{tema}" questão prova resolvida',
        f'"{banca}" "{cargo}" "{materia}" enunciado alternativas gabarito oficial',
    ]
    return buscar_ddg(queries, max_res=8, max_chars=6000, cache_prefix="reais")

# =========================================================
# PROMPTS
# =========================================================
def prompt_questoes_ineditas(qtd, banca, cargo, concurso, materia, tema, contexto_juris, contexto_padrao, contexto_edital):
    perfil_banca = obter_perfil_banca(banca)
    perfil_cargo = obter_perfil_cargo(cargo)
    formato = perfil_banca["formatos"][0]
    nivel = perfil_cargo.get("nível", 3)

    if "Certo/Errado" in formato:
        exemplo_alts = '"alternativas": {}'
    elif "A a D" in formato:
        exemplo_alts = '"alternativas": {"A": "...", "B": "...", "C": "...", "D": "..."}'
    else:
        exemplo_alts = '"alternativas": {"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."}'

    rubricas_variação = """
- Varie início do enunciado; não repita moldes no lote.
- Use 2-3 institutos em conflito e cite um precedente STF/STJ (ano, tese) na explicação.
- Distratores: exceção legal; requisito faltante; entendimento superado; prazo/competência errada; literalidade vs interpretação.
- Gere internamente mais itens e devolva apenas os diversos e válidos.
"""

    return f"""
Você é um elaborador de questões de alto nível.

OBRIGAÇÕES:
1) Caso concreto com 2-3 institutos em conflito (proibido definição básica).
2) Cite jurisprudência STF/STJ (ano + tese) na explicação.
3) Distratores plausíveis e sofisticados; variação frasal.
4) Nível {nivel}/5, padrão do cargo {cargo} e banca {banca}.
5) Não reutilizar moldes de enunciado no lote.
6) Se algo ficar raso, regenere internamente e só devolva válidos.
{rubricas_variação}

CONCURSO: {concurso}
CARGO: {cargo}
BANCA: {banca}
MATÉRIA: {materia}
TEMA: {tema}
FORMATO: {formato}

CONTEXTOS (resumidos):
[JURIS] {contexto_juris[:1500]}
[PADRÃO BANCA] {contexto_padrao[:1000]}
[CONTEÚDO EDITAL] {contexto_edital[:1000]}

Gere {qtd} questões (produza mais internamente e filtre).
Responda APENAS com JSON válido:

{{
  "questoes": [
    {{
      "enunciado": "Caso concreto...",
      {exemplo_alts},
      "gabarito": "A",
      "explicacao": "Fundamente com lei, tese STF/STJ (ano/órgão), doutrina. >=5 linhas.",
      "comentarios": {{"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."}},
      "fonte": "Inédita IA — {banca} — {cargo}",
      "dificuldade": {nivel},
      "tags": ["{materia}", "{tema}", "{cargo}", "nível-{nivel}"],
      "formato": "{formato}",
      "eh_real": 0
    }}
  ]
}}
"""

def prompt_questoes_reais(qtd, banca, cargo, concurso, materia, tema, contexto_reais):
    perfil_banca = obter_perfil_banca(banca)
    formato = perfil_banca["formatos"][0]
    nivel = obter_perfil_cargo(cargo).get("nível", 3)

    if "Certo/Errado" in formato:
        exemplo_alts = '"alternativas": {}'
    elif "A a D" in formato:
        exemplo_alts = '"alternativas": {"A": "...", "B": "...", "C": "...", "D": "..."}'
    else:
        exemplo_alts = '"alternativas": {"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."}'

    return f"""
Você é um preparador especializado. Transcreva ou reconstrua em padrão real {qtd} questões da banca {banca} para o cargo {cargo}. Se faltar contexto, crie no padrão real.

CONCURSO: {concurso}
MATÉRIA: {materia} | TEMA: {tema}
FORMATO: {formato}
NÍVEL REAL: {nivel}/5

CONTEXTO DE PROVAS REAIS (resumido):
{contexto_reais[:4000]}

Regras:
- Gabarito: apenas letra A-E ou Certo/Errado, sem texto extra.
- Preserve padrão de dificuldade e estilo da banca.
- Explicação com lei/jurisprudência/doutrina (>=5 linhas).
- Varie moldes; não repita introduções.

Responda somente com JSON:

{{
  "questoes": [
    {{
      "enunciado": "Enunciado completo",
      {exemplo_alts},
      "gabarito": "A",
      "explicacao": "Fundamentação",
      "comentarios": {{"A": "...", "B": "..."}},
      "fonte": "{banca} — {concurso} — Prova Real ou Padrão Real",
      "dificuldade": {nivel},
      "tags": ["{materia}", "{tema}", "{cargo}", "prova-real"],
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
    enun = q.get("enunciado", "")
    gab = normalizar_gabarito(q.get("gabarito", ""))
    alts = q.get("alternativas", {})
    exp = q.get("explicacao", "")
    if not enun or len(enun) < 120:
        return False
    if gab not in ["A", "B", "C", "D", "E", "CERTO", "ERRADO"]:
        return False
    if isinstance(alts, dict) and "Certo/Errado" not in str(q.get("formato", "")):
        if len(alts.keys()) < 2:
            return False
        if any(not v or len(str(v).strip()) < 8 for v in alts.values()):
            return False
    if not re.search(r'(STF|STJ|art\.|Lei|Código)', exp, flags=re.IGNORECASE):
        return False
    if len(exp.strip()) < 200:
        return False
    return True

def score_questao(q: Dict[str, Any]) -> float:
    score = 0.0
    enun = q.get("enunciado", "")
    exp = q.get("explicacao", "")
    alts = q.get("alternativas", {})
    score += min(len(enun) / 220.0, 4.5)
    score += min(len(exp) / 320.0, 3.5)
    score += len([k for k in alts.keys()]) * 0.3
    score += 1 if re.search(r'STF|STJ', exp, re.IGNORECASE) else 0
    score += 0.6 if re.search(r'exceç|prazo|competên', " ".join(alts.values()), re.IGNORECASE) else 0
    return score

def dedup_lista(lista: List[Dict[str, Any]], materia: str, tema: str, banca: str, cargo: str) -> List[Dict[str, Any]]:
    vistos = {}
    res = []
    for q in lista:
        gab_norm = normalizar_gabarito(q.get("gabarito", ""))
        h = gerar_hash_questao(q.get("enunciado", ""), gab_norm, materia, tema, banca, cargo)
        fp = fingerprint(q.get("enunciado", ""))
        if h in vistos:
            continue
        if any(similar(q.get("enunciado", ""), v) for v in vistos.values()):
            continue
        vistos[h] = fp
        q["hash_calc"] = h
        res.append(q)
    return res

# =========================================================
# LLM CALL
# =========================================================
def chamar_modelo(messages: List[Dict[str, str]], modelo: str, temperature: float, max_tokens: int = 6000, response_json: bool = True):
    if "groq" in modelo.lower():
        if not client_groq:
            raise RuntimeError("Cliente Groq não configurado")
        return client_groq.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile",
            temperature=temperature,
            response_format={"type": "json_object"} if response_json else None,
            max_tokens=max_tokens
        )
    else:
        if not client_deepseek:
            raise RuntimeError("Cliente DeepSeek não configurado")
        return client_deepseek.chat.completions.create(
            messages=messages,
            model="deepseek-chat",
            temperature=temperature,
            response_format={"type": "json_object"} if response_json else None,
            max_tokens=max_tokens
        )

def gerar_questoes(qtd, origem, banca, cargo, concurso, materia, tema, usar_web, modelo_escolhido):
    qtd_interno = max(qtd * 3, qtd + 4)

    contexto_juris = contexto_padrao = contexto_edital = contexto_reais = ""
    if usar_web:
        if origem == "Ineditas":
            contexto_juris = pesquisar_jurisprudencia_avancada(banca, cargo, concurso, materia, tema)
            contexto_padrao = pesquisar_padrao_banca_cargo(banca, cargo, concurso)
            contexto_edital = pesquisar_conteudo_programatico_especifico(cargo, concurso, materia)
        else:
            contexto_reais = pesquisar_questoes_reais_banca(banca, cargo, concurso, materia, tema, qtd_interno)
    else:
        contexto_juris = f"Use jurisprudência consolidada de {materia} para {cargo}."
        contexto_padrao = f"Padrão histórico conhecido da banca {banca}."
        contexto_edital = f"Conteúdo programático padrão de {cargo}."

    if origem == "Ineditas":
        prompt = prompt_questoes_ineditas(qtd_interno, banca, cargo, concurso, materia, tema, contexto_juris, contexto_padrao, contexto_edital)
        temp = 0.78
    else:
        prompt = prompt_questoes_reais(qtd_interno, banca, cargo, concurso, materia, tema, contexto_reais)
        temp = 0.18

    messages = [
        {"role": "system", "content": "Você gera APENAS JSON válido. Siga o esquema fornecido. Não inclua markdown."},
        {"role": "user", "content": prompt}
    ]

    resp = chamar_modelo(messages, modelo_escolhido, temperature=temp)
    conteudo = resp.choices[0].message.content
    try:
        dados = json.loads(conteudo.replace("```json", "").replace("```", "").strip())
    except Exception as e:
        raise RuntimeError(f"Falha ao parsear JSON: {e}")

    lista = dados.get("questoes", []) if isinstance(dados, dict) else (dados if isinstance(dados, list) else [])
    for q in lista:
        q["materia"] = materia
        q["tema"] = tema
        q["banca"] = banca
        q["cargo"] = cargo

    lista = dedup_lista(lista, materia, tema, banca, cargo)
    lista_validas = [q for q in lista if validar_questao(q)]
    lista_validas.sort(key=score_questao, reverse=True)
    return lista_validas[:qtd], len(lista), len(lista_validas)

# =========================================================
# ESTADO DE SESSÃO
# =========================================================
if "usuario_atual" not in st.session_state: st.session_state.usuario_atual = None
if "bateria_atual" not in st.session_state: st.session_state.bateria_atual = []
if "edital_ativo" not in st.session_state: st.session_state.edital_ativo = None
if "debug_mode" not in st.session_state: st.session_state.debug_mode = False
if "tema_cooldown" not in st.session_state: st.session_state.tema_cooldown = []

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.title("👤 Perfil")
    df_users = pd.read_sql_query("SELECT nome FROM usuarios", conn)
    lista_users = df_users["nome"].tolist()
    usuario_sel = st.selectbox("Selecione o Perfil", ["Novo Usuário..."] + lista_users)

    if usuario_sel == "Novo Usuário...":
        novo_nome = st.text_input("Nome/Login:")
        if st.button("Criar e Entrar", use_container_width=True) and novo_nome:
            try:
                c.execute("INSERT INTO usuarios (nome) VALUES (?)", (novo_nome.strip(),))
                conn.commit()
                st.session_state.usuario_atual = novo_nome.strip()
                st.success(f"Bem-vindo, {novo_nome}!")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("Este nome já existe.")
    else:
        st.session_state.usuario_atual = usuario_sel

    st.divider()
    st.header("🧠 Motor de IA")
    motor_escolhido = st.radio(
        "Modelo:",
        ["Groq (Llama3)", "DeepSeek"],
        captions=["Cota gratuita limitada", "Mais robusto"],
    )

    st.session_state.debug_mode = st.checkbox("🔍 Modo Debug", value=False)
    st.divider()

    if st.session_state.usuario_atual:
        st.header("📚 Biblioteca de Editais")
        df_editais = pd.read_sql_query(
            "SELECT id, nome_concurso, banca, cargo, dados_json, nivel_dificuldade, nome_concurso_completo FROM editais_salvos WHERE usuario = ? ORDER BY id DESC",
            conn,
            params=(st.session_state.usuario_atual,)
        )
        if not df_editais.empty:
            opcoes_editais = ["Selecione um edital..."] + [f"{row['nome_concurso']} ({row['cargo']})" for _, row in df_editais.iterrows()]
            escolha = st.selectbox("Carregar Edital", opcoes_editais)
            if escolha != "Selecione um edital...":
                idx = opcoes_editais.index(escolha) - 1
                linha = df_editais.iloc[idx]
                perfil_cargo_det = obter_perfil_cargo(linha["cargo"])
                perfil_banca_det = obter_perfil_banca(linha["banca"])
                nome_completo = linha.get("nome_concurso_completo") or linha["nome_concurso"]
                st.session_state.edital_ativo = {
                    "nome_concurso": linha["nome_concurso"],
                    "nome_concurso_completo": nome_completo,
                    "banca": linha["banca"],
                    "cargo": linha["cargo"],
                    "materias": json.loads(linha["dados_json"])["materias"],
                    "nivel_dificuldade": perfil_cargo_det["nível"],
                    "formatos": perfil_banca_det["formatos"],
                    "perfil_cargo": perfil_cargo_det,
                }
                st.success(
                    f"✅ {linha['nome_concurso']} carregado! "
                    f"Banca: {linha['banca']} | Nível: {perfil_cargo_det['descrição']}"
                )
        else:
            st.info("Nenhum edital salvo.")

        st.write("---")
        with st.expander("➕ Cadastrar Novo Edital", expanded=df_editais.empty):
            nome_novo = st.text_input("Nome curto (ex: PCDF 2024):")
            nome_completo_novo = st.text_input("Nome completo:")
            banca_nova = st.text_input("Banca (ex: Cebraspe, FCC):")
            cargo_novo = st.text_input("Cargo (ex: Delegado de Polícia Civil):")
            texto_colado = st.text_area("Cole o conteúdo programático:")

            if st.button("💾 Salvar Edital", use_container_width=True) and nome_novo and texto_colado:
                with st.spinner("Extraindo matérias..."):
                    perfil_cargo = obter_perfil_cargo(cargo_novo)
                    perfil_banca = obter_perfil_banca(banca_nova)
                    prompt_edit = f"""
Leia o conteúdo programático e extraia apenas as disciplinas principais.
Responda somente com JSON: {{"materias": ["Disciplina 1", "Disciplina 2"]}}.
Texto: {texto_colado[:12000]}
"""
                    try:
                        if not client_groq:
                            raise RuntimeError("Configure GROQ_API_KEY")
                        resp = client_groq.chat.completions.create(
                            messages=[{"role": "user", "content": prompt_edit}],
                            model="llama-3.3-70b-versatile",
                            temperature=0.1,
                            response_format={"type": "json_object"}
                        )
                        texto_json = resp.choices[0].message.content
                        formatos_json = json.dumps(perfil_banca["formatos"])
                        nome_completo_final = nome_completo_novo or nome_novo
                        c.execute(
                            """
                            INSERT INTO editais_salvos
                            (usuario, nome_concurso, banca, cargo, dados_json, data_analise,
                             nivel_dificuldade, formato_questoes, nome_concurso_completo)
                            VALUES (?,?,?,?,?,?,?,?,?)
                            """,
                            (
                                st.session_state.usuario_atual, nome_novo, banca_nova, cargo_novo,
                                texto_json, str(datetime.now()), perfil_cargo["nível"],
                                formatos_json, nome_completo_final
                            )
                        )
                        conn.commit()
                        st.success("Edital salvo!")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Erro ao estruturar: {ex}")

        st.divider()
        if st.button("🗑️ Zerar Progresso", use_container_width=True):
            c.execute("DELETE FROM respostas WHERE usuario = ?", (st.session_state.usuario_atual,))
            conn.commit()
            st.session_state.bateria_atual = []
            st.success("Histórico apagado!")
            st.rerun()

# =========================================================
# TELA PRINCIPAL
# =========================================================
if not st.session_state.usuario_atual:
    st.title("🔒 Bem-vindo")
    st.info("Selecione ou crie um perfil na barra lateral.")
    st.stop()

st.title(f"📚 Plataforma — {st.session_state.usuario_atual}")
st.write("---")

df_resp = pd.read_sql_query("SELECT * FROM respostas WHERE usuario = ?", conn, params=(st.session_state.usuario_atual,))
total_resp = len(df_resp)
acertos = int(df_resp["acertou"].sum()) if total_resp > 0 else 0
taxa_acerto = round((acertos / total_resp) * 100, 1) if total_resp > 0 else 0

colA, colB, colC = st.columns(3)
with colA:
    st.markdown(f'<div class="metric-box"><div class="metric-title">Itens Resolvidos</div><div class="metric-value">{total_resp}</div></div>', unsafe_allow_html=True)
with colB:
    st.markdown(f'<div class="metric-box"><div class="metric-title">Acertos</div><div class="metric-value">{acertos}</div></div>', unsafe_allow_html=True)
with colC:
    st.markdown(f'<div class="metric-box"><div class="metric-title">Aproveitamento</div><div class="metric-value" style="color:{"#28a745" if taxa_acerto>=70 else "#dc3545"};">{taxa_acerto}%</div></div>', unsafe_allow_html=True)

st.write("<br>", unsafe_allow_html=True)

# =========================================================
# GERADOR DE SIMULADO
# =========================================================
with st.container(border=True):
    st.subheader("⚡ Gerar Bateria")

    if st.session_state.edital_ativo:
        e = st.session_state.edital_ativo
        banca_alvo = e["banca"]
        cargo_alvo = e["cargo"]
        concurso = e.get("nome_concurso_completo") or e["nome_concurso"]
        perfil_cargo_ativo = e.get("perfil_cargo", obter_perfil_cargo(cargo_alvo))

        st.markdown(
            f"<div class='concurso-box'>🎯 <b>CONCURSO:</b> {concurso}<br>"
            f"🏢 <b>BANCA:</b> {banca_alvo} | 👮 <b>CARGO:</b> {cargo_alvo} | 🔥 <b>NÍVEL:</b> {perfil_cargo_ativo['descrição']}</div>",
            unsafe_allow_html=True
        )
        lista_materias = ["Aleatório"] + e["materias"]
        c1, c2 = st.columns(2)
        with c1:
            mat_sel = st.selectbox("Matéria", lista_materias)
        with c2:
            tema_sel = st.text_input("Tema específico (ou 'Aleatório')", "Aleatório")
    else:
        st.warning("Carregue um edital para calibração automática.")
        c1, c2, c3 = st.columns(3)
        with c1:
            banca_alvo = st.text_input("Banca", "Cebraspe")
        with c2:
            cargo_alvo = st.text_input("Cargo", "Delegado de Polícia Civil")
        with c3:
            mat_sel = st.text_input("Matéria", "Direito Penal")
        concurso = st.text_input("Nome do Concurso", "Concurso Público")
        tema_sel = st.text_input("Tema específico", "Aleatório")
        e = None

    c3col, c4col = st.columns(2)
    with c3col:
        tipo = st.selectbox("Origem", ["🧠 Inéditas IA", "🌐 Questões Reais", "📂 Revisão (Banco Local)"])
    with c4col:
        qtd = st.slider("Quantidade", 1, 10, 5)

    usar_web = st.checkbox("🌐 Pesquisa web avançada", value=True)

    if st.button("🚀 Forjar Bateria", type="primary", use_container_width=True):
        mat_final = (random.choice(e["materias"]) if e and mat_sel == "Aleatório" else mat_sel)

        # rotação/aleatório de tema com proteção quando não há edital
        if tema_sel.lower() == "aleatório":
            if e and st.session_state.tema_cooldown:
                pool = [m for m in e["materias"] if m not in st.session_state.tema_cooldown[-3:]]
                if pool:
                    mat_final = random.choice(pool)
            tema_final = f"Tema mais cobrado e complexo de {mat_final} para {cargo_alvo}"
        else:
            tema_final = tema_sel

        if "Revisão" in tipo:
            st.info("🔄 Resgatando questões do banco local...")
            c.execute(
                """
                SELECT id FROM questoes
                WHERE (banca LIKE ? OR cargo LIKE ? OR materia LIKE ?)
                ORDER BY dificuldade DESC, RANDOM() LIMIT ?
                """,
                (f"%{banca_alvo}%", f"%{cargo_alvo}%", f"%{mat_final}%", qtd)
            )
            ids = [row[0] for row in c.fetchall()]
            if ids:
                st.session_state.bateria_atual = ids
                st.rerun()
            else:
                st.warning("Banco local insuficiente. Gere novas questões.")
        else:
            origem = "Ineditas" if "Inéditas" in tipo else "Reais"
            modelo_flag = "groq" if "Groq" in motor_escolhido else "deepseek"
            progresso = st.progress(0, text="Preparando...")

            try:
                progresso.progress(25, text="🔍 Buscando contexto..." if usar_web else "Contexto padrão...")
                lista, total_bruto, total_validas = gerar_questoes(
                    qtd=qtd,
                    origem=origem,
                    banca=banca_alvo,
                    cargo=cargo_alvo,
                    concurso=concurso,
                    materia=mat_final,
                    tema=tema_final,
                    usar_web=usar_web,
                    modelo_escolhido=modelo_flag
                )
                progresso.progress(75, text="💾 Salvando no banco...")
                novas_ids, duplicatas = [], 0
                for q in lista:
                    gab_norm = normalizar_gabarito(q.get("gabarito", ""))
                    hash_q = q.get("hash_calc") or gerar_hash_questao(q.get("enunciado", ""), gab_norm, mat_final, tema_final, banca_alvo, cargo_alvo)
                    if questao_ja_existe(hash_q):
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
                         dificuldade, tags, formato_questao, eh_real, ano_prova, hash_questao, subtema, juris_citada, validado, created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            banca_alvo, cargo_alvo, mat_final, tema_final, q.get("enunciado", ""), alternativas,
                            gab_norm, explicacao_final, tipo,
                            q.get("fonte", f"Inédita IA — {banca_alvo} — {cargo_alvo}"),
                            q.get("dificuldade", obter_perfil_cargo(cargo_alvo).get("nível", 3)),
                            json.dumps(q.get("tags", [])),
                            q.get("formato", "Múltipla Escolha"),
                            1 if q.get("eh_real") else 0,
                            q.get("ano_prova", 0),
                            hash_q,
                            q.get("subtema", ""),
                            q.get("juris_citada", ""),
                            1,
                            datetime.now().isoformat()
                        )
                    )
                    novas_ids.append(c.lastrowid)
                conn.commit()
                st.session_state.bateria_atual = novas_ids
                if e:
                    st.session_state.tema_cooldown.append(mat_final)
                progresso.progress(100, text="✅ Concluído!")
                st.success(f"Geradas {len(novas_ids)} questões (brutas: {total_bruto}, válidas: {total_validas}, descartadas como duplicatas: {duplicatas}).")
                st.rerun()
            except Exception as err:
                progresso.empty()
                st.error(f"❌ Erro: {err}")

# =========================================================
# CADERNO DE PROVA
# =========================================================
if st.session_state.bateria_atual:
    st.write("---")
    st.subheader("🎯 Caderno de Prova")

    ids_str = ",".join(map(str, st.session_state.bateria_atual))
    df_respostas = pd.read_sql_query(
        f"SELECT questao_id, resposta_usuario, acertou FROM respostas WHERE usuario = ? AND questao_id IN ({ids_str})",
        conn,
        params=(st.session_state.usuario_atual,)
    )
    respondidas = df_respostas.set_index("questao_id").to_dict("index")

    for i, q_id in enumerate(st.session_state.bateria_atual):
        c.execute(
            """
            SELECT banca, cargo, materia, enunciado, alternativas, gabarito, explicacao,
                   fonte, dificuldade, tags, formato_questao, eh_real
            FROM questoes WHERE id = ?
            """,
            (q_id,)
        )
        dados = c.fetchone()
        if not dados:
            continue

        q_banca, q_cargo, q_mat, q_enun, q_alt, q_gab, q_exp, q_fonte, q_dif, q_tags, q_formato, eh_real = dados
        alts = json.loads(q_alt) if q_alt else {}
        tags_list = json.loads(q_tags) if q_tags else []
        q_gab_norm = normalizar_gabarito(q_gab)
        is_certo_errado = "Certo/Errado" in (q_formato or "")

        dif_idx = min(max((q_dif or 3) - 1, 0), 4)
        dif_label = ["Muito Fácil", "Fácil", "Médio", "Difícil", "Muito Difícil"][dif_idx]
        dif_classe = "dif-facil" if (q_dif or 3) <= 2 else ("dif-medio" if (q_dif or 3) == 3 else "dif-dificil")
        tipo_questao = "Prova Real" if eh_real else "Inédita IA"
        tipo_classe = "tipo-real" if eh_real else "tipo-inedita"

        try:
            exp_data = json.loads(q_exp)
            exp_geral = exp_data.get("geral", q_exp) if isinstance(exp_data, dict) else q_exp
            exp_detalhes = exp_data.get("detalhes", {}) if isinstance(exp_data, dict) else {}
        except Exception:
            exp_geral = q_exp
            exp_detalhes = {}

        opcoes = ["Selecionar...", "Certo", "Errado"] if is_certo_errado else (["Selecionar..."] + [f"{k}) {v}" for k, v in alts.items()]) if alts else ["Selecionar...", "A", "B", "C", "D", "E"]

        with st.container(border=True):
            col_info, col_tipo, col_dif = st.columns([3, 1, 1])
            with col_info:
                st.caption(f"**Item {i+1}** | 🏢 {q_banca} | 📚 {q_mat} | 🎯 {q_formato}")
            with col_tipo:
                st.markdown(f"<span class='tipo-badge {tipo_classe}'>{tipo_questao}</span>", unsafe_allow_html=True)
            with col_dif:
                st.markdown(f"<span class='dificuldade-badge {dif_classe}'>{dif_label}</span>", unsafe_allow_html=True)

            if tags_list:
                st.caption(f"🏷️ {', '.join(tags_list)}")
            st.caption(f"📌 {q_fonte}")
            st.markdown(f"#### {q_enun}")

            if q_id in respondidas:
                status = respondidas[q_id]
                resp_salva = normalizar_gabarito(str(status["resposta_usuario"]))

                if st.session_state.debug_mode:
                    st.markdown(
                        f"<div class='debug-box'>DEBUG | Gabarito: {q_gab!r} → {q_gab_norm!r} | Resp: {status['resposta_usuario']!r} → {resp_salva!r} | Acertou: {status['acertou']}</div>",
                        unsafe_allow_html=True
                    )

                st.markdown("<br><b>Análise das Alternativas:</b>", unsafe_allow_html=True)
                for opcao in opcoes[1:]:
                    letra_opcao = extrair_letra_opcao(opcao, not is_certo_errado)
                    is_usuario = (letra_opcao == resp_salva)
                    is_gabarito = (letra_opcao == q_gab_norm)

                    if is_usuario:
                        css = "alt-correta" if status["acertou"] == 1 else "alt-errada"
                        icon = "✅" if status["acertou"] == 1 else "❌"
                        label = "(Sua Resposta Correta)" if status["acertou"] == 1 else "(Sua Resposta Incorreta)"
                        st.markdown(f"<div class='{css}'>{icon} <b>{opcao}</b> {label}</div>", unsafe_allow_html=True)
                    elif is_gabarito and status["acertou"] == 0:
                        st.markdown(f"<div class='alt-gabarito'>🎯 <b>{opcao}</b> (Gabarito Oficial)</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div class='alt-neutra'>{opcao}</div>", unsafe_allow_html=True)

                    if not is_certo_errado and letra_opcao in exp_detalhes and exp_detalhes[letra_opcao]:
                        st.markdown(f"<div class='comentario-alt'>💡 {exp_detalhes[letra_opcao]}</div>", unsafe_allow_html=True)

                with st.expander("📖 Fundamentação"):
                    st.write(exp_geral)
            else:
                if st.session_state.debug_mode:
                    st.markdown(
                        f"<div class='debug-box'>DEBUG | Gabarito esperado: {q_gab_norm!r}</div>",
                        unsafe_allow_html=True
                    )
                resp = st.radio("Sua Resposta:", opcoes, key=f"rad_{q_id}", label_visibility="collapsed")
                if st.button("✅ Confirmar", key=f"btn_{q_id}"):
                    if resp != "Selecionar...":
                        letra_escolhida = extrair_letra_opcao(resp, not is_certo_errado)
                        acertou = 1 if letra_escolhida == q_gab_norm else 0
                        c.execute(
                            "INSERT INTO respostas (usuario, questao_id, resposta_usuario, acertou, data) VALUES (?,?,?,?,?)",
                            (st.session_state.usuario_atual, q_id, letra_escolhida, acertou, str(datetime.now()))
                        )
                        conn.commit()
                        st.rerun()
                    else:
                        st.warning("Selecione uma opção antes de confirmar.")
