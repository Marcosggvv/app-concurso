import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import json
import random
import re
import hashlib
import time
import traceback
import sys
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
    .metric-box { background-color: #f8f9fa; border-radius: 10px; padding: 20px;
        text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #e9ecef; }
    .metric-title { font-size: 14px; color: #6c757d; font-weight: 600; text-transform: uppercase; }
    .metric-value { font-size: 32px; font-weight: 700; color: #212529; margin-top: 5px; }
    .stRadio > div { flex-direction: row; gap: 15px; }
    .alt-correta  { padding: 10px; background-color: #d4edda; border-left: 5px solid #28a745;
        border-radius: 5px; margin-bottom: 2px; }
    .alt-errada   { padding: 10px; background-color: #f8d7da; border-left: 5px solid #dc3545;
        border-radius: 5px; margin-bottom: 2px; }
    .alt-neutra   { padding: 10px; border-left: 5px solid #e9ecef; margin-bottom: 2px; color: #495057; }
    .alt-gabarito { padding: 10px; background-color: #cce5ff; border-left: 5px solid #004085;
        border-radius: 5px; margin-bottom: 2px; font-weight: bold; }
    .comentario-alt { font-size: 0.9em; color: #555; margin-left: 15px; margin-bottom: 12px;
        border-left: 2px solid #ccc; padding-left: 10px; background-color: #fdfdfd;
        padding-top: 5px; padding-bottom: 5px; }
    .dificuldade-badge { display: inline-block; padding: 5px 12px; border-radius: 20px;
        font-weight: 600; font-size: 12px; }
    .dif-facil   { background-color: #d4edda; color: #155724; }
    .dif-medio   { background-color: #fff3cd; color: #856404; }
    .dif-dificil { background-color: #f8d7da; color: #721c24; }
    .tipo-badge  { display: inline-block; padding: 4px 10px; border-radius: 15px;
        font-size: 11px; font-weight: bold; margin-right: 5px; }
    .tipo-inedita { background-color: #ffd700; color: #333; }
    .tipo-real    { background-color: #87ceeb; color: #000; }
    .debug-box    { background-color: #fff8dc; border: 1px dashed #aaa; padding: 8px 12px;
        border-radius: 5px; font-size: 12px; font-family: monospace; margin-top: 5px; }
    .concurso-box { background-color: #1a1a2e; color: #e0e0e0; border-left: 5px solid #e94560;
        padding: 14px; border-radius: 8px; margin-bottom: 16px; }
    .concurso-box b { color: #e94560; }
    .metric-value-verde { font-size: 32px; font-weight: 700; color: #28a745; margin-top: 5px; }
    .metric-value-vermelho { font-size: 32px; font-weight: 700; color: #dc3545; margin-top: 5px; }
    </style>
    """,
    unsafe_allow_html=True
)

# =========================================================
# CONSTANTES DE PERFIL
# =========================================================
PERFIL_BANCAS: Dict[str, Any] = {
    "Cebraspe": {
        "formatos": ["Certo/Errado"],
        "caracteristicas": [
            "assertivas precisas com pegadinhas em exceções e jurisprudência",
            "interpretação literal e sistemática de normas",
            "tese firmada em repercussão geral/recursos repetitivos",
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
            "aplicação a casos concretos",
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
            "aplicação prática com resultado específico",
        ],
        "quantidade_alternativas": 5,
        "estilo_enunciado": "descritivo com situação fática",
        "dificuldade_base": 3,
    },
}

PERFIL_CARGO_DIFICULDADE: Dict[str, Any] = {
    "Delegado de Polícia Civil": {
        "nível": 5,
        "descrição": "Muito Difícil — Nível Magistratura",
        "exige": [
            "CPP, CP, Leis 11.343/06, 12.850/13, 9.296/96, 13.964/19",
            "Jurisprudência STF/STJ sobre prisões, provas e investigação",
            "Inquérito, ANPP, colaboração, cadeia de custódia",
        ],
        "estilo_questao": [
            "caso concreto com múltiplos institutos em conflito",
            "jurisprudência recente que alterou entendimento",
            "distinção entre institutos processuais similares",
        ],
        "exemplos_temas_avancados": [
            "cadeia de custódia e consequências processuais",
            "agente infiltrado vs. agente provocador",
            "prisão domiciliar e entendimento do STJ",
        ],
    },
    "Delegado": {
        "nível": 5,
        "descrição": "Muito Difícil — Nível Magistratura",
        "exige": ["CPP, CP, legislação penal especial", "jurisprudência STF/STJ atualizada"],
        "estilo_questao": ["caso concreto com múltiplos institutos", "jurisprudência recente"],
        "exemplos_temas_avancados": ["Pacote Anticrime", "ANPP", "cadeia de custódia"],
    },
    "Juiz de Direito": {
        "nível": 5,
        "descrição": "Muito Difícil — Nível Magistratura",
        "exige": ["processo civil e penal avançado", "precedentes e controle de constitucionalidade"],
        "estilo_questao": ["múltiplos recursos/incidentes", "conflito normativo solucionado pelo STF"],
        "exemplos_temas_avancados": ["IRDR", "tutelas de urgência/evidência"],
    },
    "Analista": {
        "nível": 3,
        "descrição": "Médio",
        "exige": ["conceitos sólidos", "casos práticos padrão"],
        "estilo_questao": ["conceito aplicado a caso", "distinção entre procedimentos"],
        "exemplos_temas_avancados": ["prazos e formalidades", "competências do órgão"],
    },
}

# =========================================================
# CLIENTES DE MODELO  — falha silenciosa, sem crash
# =========================================================
client_groq: Optional[Groq] = None
client_deepseek: Optional[OpenAI] = None

try:
    client_groq = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception:
    pass

try:
    client_deepseek = OpenAI(
        api_key=st.secrets["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com",
    )
except Exception:
    pass

# =========================================================
# BANCO DE DADOS
# =========================================================
@st.cache_resource
def iniciar_conexao() -> sqlite3.Connection:
    conn = sqlite3.connect("estudos_multi_user.db", check_same_thread=False)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS usuarios (nome TEXT PRIMARY KEY)")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS questoes (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            banca          TEXT,
            cargo          TEXT,
            materia        TEXT,
            tema           TEXT,
            enunciado      TEXT,
            alternativas   TEXT,
            gabarito       TEXT,
            explicacao     TEXT,
            tipo           TEXT,
            fonte          TEXT,
            dificuldade    INTEGER DEFAULT 3,
            tags           TEXT    DEFAULT '[]',
            formato_questao TEXT   DEFAULT 'Múltipla Escolha',
            eh_real        INTEGER DEFAULT 0,
            ano_prova      INTEGER DEFAULT 0,
            hash_questao   TEXT    DEFAULT '',
            subtema        TEXT    DEFAULT '',
            juris_citada   TEXT    DEFAULT '',
            validado       INTEGER DEFAULT 0,
            created_at     TEXT    DEFAULT ''
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS respostas (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario          TEXT,
            questao_id       INTEGER,
            resposta_usuario TEXT,
            acertou          INTEGER,
            data             TEXT,
            tempo_resposta   INTEGER DEFAULT 0
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS editais_salvos (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario                TEXT,
            nome_concurso          TEXT,
            banca                  TEXT,
            cargo                  TEXT,
            dados_json             TEXT,
            data_analise           TEXT,
            nivel_dificuldade      INTEGER DEFAULT 3,
            formato_questoes       TEXT    DEFAULT '[]',
            nome_concurso_completo TEXT    DEFAULT ''
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS cache_busca (
            chave      TEXT PRIMARY KEY,
            conteudo   TEXT,
            criado_em  TEXT
        )
        """
    )
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
    if re.search(r"\bCERTO\b", g):
        return "CERTO"
    if re.search(r"\bERRADO\b", g):
        return "ERRADO"
    m = re.match(r"^([A-E])[^A-Z]", g)
    if m:
        return m.group(1)
    if len(g) == 1 and g in "ABCDE":
        return g
    m = re.search(r"\b(?:LETRA|ALT(?:ERNATIVA)?|OPÇ?AO)\s+([A-E])\b", g)
    if m:
        return m.group(1)
    m = re.search(r"\b([A-E])\b", g)
    if m:
        return m.group(1)
    return g


def extrair_letra_opcao(opcao_texto: Any, tem_alternativas: bool) -> str:
    texto = str(opcao_texto).strip().upper()
    if texto in ("CERTO", "ERRADO"):
        return texto
    if re.search(r"\bCERTO\b", texto):
        return "CERTO"
    if re.search(r"\bERRADO\b", texto):
        return "ERRADO"
    if tem_alternativas:
        m = re.match(r"^([A-E])\)", texto)
        if m:
            return m.group(1)
        m = re.match(r"^([A-E])\b", texto)
        if m:
            return m.group(1)
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
                melhor_chave, maior_len = chave, len(chave)
    if melhor_chave:
        return PERFIL_CARGO_DIFICULDADE[melhor_chave]
    return {
        "nível": 3,
        "descrição": "Médio",
        "exige": ["Padrão"],
        "estilo_questao": ["Padrão"],
        "exemplos_temas_avancados": [],
    }


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
    return re.sub(r"\s+", " ", txt or "")[:max_chars]


def fingerprint(text: str) -> str:
    tokens = [t for t in re.findall(r"\w+", text.lower()) if len(t) > 3][:80]
    return hashlib.md5(" ".join(tokens).encode()).hexdigest()


def similar(a: str, b: str, threshold: float = 0.35) -> bool:
    sa = set(re.findall(r"\w+", a.lower()))
    sb = set(re.findall(r"\w+", b.lower()))
    if not sa or not sb:
        return False
    return len(sa & sb) / len(sa | sb) >= threshold


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
        if time.time() - datetime.fromisoformat(criado_em).timestamp() > max_age_seconds:
            return None
        return conteudo
    except Exception:
        return None


def set_cache(chave: str, conteudo: str) -> None:
    c.execute(
        "REPLACE INTO cache_busca (chave, conteudo, criado_em) VALUES (?,?,?)",
        (chave, conteudo, datetime.now().isoformat()),
    )
    conn.commit()


def buscar_ddg(queries: List[str], max_res: int = 6, max_chars: int = 8000, cache_prefix: str = "") -> str:
    resultados: List[str] = []
    try:
        ddgs = DDGS()
        for q in queries:
            cache_key = f"{cache_prefix}:{hashlib.md5(q.encode()).hexdigest()}"
            cached = get_cache(cache_key)
            if cached:
                resultados.append(cached)
                continue
            try:
                res = ddgs.text(q, max_results=max_res)
                texto = sanitize_text("\n---\n".join(r.get("body", "") for r in res), max_chars)
                if texto:
                    resultados.append(texto)
                    set_cache(cache_key, texto)
            except Exception:
                continue
    except Exception:
        pass
    return "\n---\n".join(resultados)[:max_chars]


# =========================================================
# RAG / CONTEXTO
# =========================================================
def pesquisar_jurisprudencia_avancada(banca: str, cargo: str, concurso: str, materia: str, tema: str) -> str:
    return buscar_ddg(
        [
            f'"{materia}" "{tema}" STJ STF jurisprudência 2023 2024 informativo',
            f'"{tema}" "{materia}" precedente vinculante STF tese repercussão geral',
            f'"{cargo}" "{materia}" "{tema}" questão julgado recente STJ informativo',
            f'"{tema}" "{materia}" doutrina conceito distinção institutos concurso',
            f'"{banca}" "{cargo}" "{materia}" banca cobrou jurisprudência gabarito',
        ],
        max_res=5,
        max_chars=4000,
        cache_prefix="juris",
    )


def pesquisar_padrao_banca_cargo(banca: str, cargo: str, concurso: str) -> str:
    return buscar_ddg(
        [
            f'"{banca}" "{cargo}" padrão questões dificuldade nível concurso análise',
            f'"{concurso}" análise prova questões dificuldade resolução comentada',
            f'"{banca}" "{cargo}" provas anteriores temas mais cobrados estatísticas',
        ],
        max_res=5,
        max_chars=3000,
        cache_prefix="padrao",
    )


def pesquisar_conteudo_programatico_especifico(cargo: str, concurso: str, materia: str) -> str:
    return buscar_ddg(
        [
            f'"{concurso}" conteúdo programático "{materia}" edital tópicos cobrados',
            f'"{cargo}" "{materia}" temas mais cobrados concurso público 2022 2023 2024',
            f'"{concurso}" edital "{materia}" itens exigidos estudo',
        ],
        max_res=4,
        max_chars=3000,
        cache_prefix="edital",
    )


def pesquisar_questoes_reais_banca(banca: str, cargo: str, concurso: str, materia: str, tema: str, quantidade: int) -> str:
    return buscar_ddg(
        [
            f'questão prova "{concurso}" "{banca}" "{materia}" gabarito resolução',
            f'"{banca}" "{cargo}" "{materia}" prova concurso gabarito site:tecconcursos.com.br',
            f'"{banca}" "{cargo}" "{materia}" site:qconcursos.com questão gabarito',
            f'concurso "{cargo}" "{banca}" "{materia}" "{tema}" questão prova resolvida',
            f'"{banca}" "{cargo}" "{materia}" enunciado alternativas gabarito oficial',
        ],
        max_res=8,
        max_chars=6000,
        cache_prefix="reais",
    )


# =========================================================
# PROMPTS
# =========================================================
def _exemplo_alts(formato: str) -> str:
    if "Certo/Errado" in formato:
        return '"alternativas": {}'
    if "A a D" in formato:
        return '"alternativas": {"A": "...", "B": "...", "C": "...", "D": "..."}'
    return '"alternativas": {"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."}'


def prompt_questoes_ineditas(
    qtd: int, banca: str, cargo: str, concurso: str, materia: str, tema: str,
    ctx_juris: str, ctx_padrao: str, ctx_edital: str,
) -> str:
    perfil_banca = obter_perfil_banca(banca)
    perfil_cargo = obter_perfil_cargo(cargo)
    formato = perfil_banca["formatos"][0]
    nivel = perfil_cargo.get("nível", 3)
    ex_alts = _exemplo_alts(formato)

    return f"""Você é um elaborador de questões de alto nível para concursos públicos brasileiros.

OBRIGAÇÕES (não negociável):
1) Enunciado com CASO CONCRETO contendo 2-3 institutos em conflito. PROIBIDO definição básica.
2) Cite ao menos uma jurisprudência STF/STJ (ano + tese resumida) na explicação.
3) Distratores plausíveis e sofisticados: exceção legal; requisito faltante; entendimento superado; prazo/competência errada; literalidade vs interpretação.
4) Nível {nivel}/5, padrão do cargo {cargo} e banca {banca}.
5) Varie o início do enunciado; não repita moldes dentro do lote.
6) Gere internamente mais itens e devolva apenas os melhores e mais diversos.

CONCURSO: {concurso}
CARGO: {cargo}
BANCA: {banca}
MATÉRIA: {materia}
TEMA: {tema}
FORMATO: {formato}

CONTEXTO JURISPRUDENCIAL:
{ctx_juris[:1500]}

PADRÃO DA BANCA:
{ctx_padrao[:1000]}

CONTEÚDO PROGRAMÁTICO:
{ctx_edital[:1000]}

Gere {qtd} questões. Responda APENAS com JSON válido, sem markdown:

{{
  "questoes": [
    {{
      "enunciado": "Caso concreto complexo...",
      {ex_alts},
      "gabarito": "A",
      "explicacao": "Fundamente com lei (art. X da Lei Y), tese STF/STJ (HC XXXXX, ano), doutrina. Mínimo 5 linhas.",
      "comentarios": {{"A": "motivo A", "B": "motivo B", "C": "motivo C", "D": "motivo D", "E": "motivo E"}},
      "fonte": "Inédita IA — {banca} — {cargo}",
      "dificuldade": {nivel},
      "tags": ["{materia}", "{tema}", "{cargo}"],
      "formato": "{formato}",
      "eh_real": 0
    }}
  ]
}}"""


def prompt_questoes_reais(
    qtd: int, banca: str, cargo: str, concurso: str, materia: str, tema: str, ctx_reais: str,
) -> str:
    perfil_banca = obter_perfil_banca(banca)
    formato = perfil_banca["formatos"][0]
    nivel = obter_perfil_cargo(cargo).get("nível", 3)
    ex_alts = _exemplo_alts(formato)

    return f"""Você é um preparador especializado em concursos públicos.
Transcreva ou reconstrua questões REAIS de provas anteriores da banca {banca} para o cargo {cargo}.
Se o contexto for insuficiente, crie questões no mesmo padrão e nível reais.

CONCURSO: {concurso}
MATÉRIA: {materia} | TEMA: {tema}
FORMATO: {formato} | NÍVEL: {nivel}/5

CONTEXTO DE PROVAS REAIS:
{ctx_reais[:4000]}

Regras:
- Gabarito: apenas letra A-E ou Certo/Errado, sem texto extra.
- Explicação com lei/jurisprudência/doutrina (mínimo 5 linhas).
- Varie moldes e estrutura dos enunciados.

Gere {qtd} questões. Responda APENAS com JSON válido, sem markdown:

{{
  "questoes": [
    {{
      "enunciado": "Enunciado completo...",
      {ex_alts},
      "gabarito": "A",
      "explicacao": "Fundamentação completa.",
      "comentarios": {{"A": "...", "B": "..."}},
      "fonte": "{banca} — {concurso} — Prova Real",
      "dificuldade": {nivel},
      "tags": ["{materia}", "{tema}", "{cargo}", "prova-real"],
      "formato": "{formato}",
      "eh_real": 1,
      "ano_prova": 2023
    }}
  ]
}}"""


# =========================================================
# VALIDAÇÃO, SCORE E DEDUP
# =========================================================
def validar_questao(q: Dict[str, Any]) -> bool:
    enun = q.get("enunciado", "")
    gab = normalizar_gabarito(q.get("gabarito", ""))
    alts = q.get("alternativas", {})
    exp = q.get("explicacao", "")

    if not enun or len(enun) < 120:
        return False
    if gab not in {"A", "B", "C", "D", "E", "CERTO", "ERRADO"}:
        return False
    if isinstance(alts, dict) and "Certo/Errado" not in str(q.get("formato", "")):
        if len(alts) < 2:
            return False
        if any(not v or len(str(v).strip()) < 8 for v in alts.values()):
            return False
    if not re.search(r"(STF|STJ|art\.|Lei|Código)", exp, flags=re.IGNORECASE):
        return False
    if len(exp.strip()) < 200:
        return False
    return True


def score_questao(q: Dict[str, Any]) -> float:
    enun = q.get("enunciado", "")
    exp = q.get("explicacao", "")
    alts = q.get("alternativas", {})
    # CORRIGIDO: garante que alts é dict antes de chamar .values()
    alts_values = list(alts.values()) if isinstance(alts, dict) else []
    score = min(len(enun) / 220.0, 4.5)
    score += min(len(exp) / 320.0, 3.5)
    score += len(alts_values) * 0.3
    score += 1.0 if re.search(r"STF|STJ", exp, re.IGNORECASE) else 0.0
    score += 0.6 if re.search(r"exceç|prazo|competên", " ".join(str(v) for v in alts_values), re.IGNORECASE) else 0.0
    return score


def dedup_lista(lista: List[Dict[str, Any]], materia: str, tema: str, banca: str, cargo: str) -> List[Dict[str, Any]]:
    vistos: Dict[str, str] = {}
    res: List[Dict[str, Any]] = []
    for q in lista:
        gab_norm = normalizar_gabarito(q.get("gabarito", ""))
        h = gerar_hash_questao(q.get("enunciado", ""), gab_norm, materia, tema, banca, cargo)
        fp = fingerprint(q.get("enunciado", ""))
        if h in vistos:
            continue
        if any(similar(fp, v) for v in vistos.values()):
            continue
        vistos[h] = fp
        q["hash_calc"] = h
        res.append(q)
    return res


# =========================================================
# LLM
# =========================================================
def chamar_modelo(
    messages: List[Dict[str, str]],
    modelo: str,
    temperature: float,
    max_tokens: int = 6000,
) -> Any:
    if "groq" in modelo.lower():
        if not client_groq:
            raise RuntimeError("Cliente Groq não configurado. Verifique GROQ_API_KEY em st.secrets.")
        return client_groq.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile",
            temperature=temperature,
            response_format={"type": "json_object"},
            max_tokens=max_tokens,
        )
    else:
        if not client_deepseek:
            raise RuntimeError("Cliente DeepSeek não configurado. Verifique DEEPSEEK_API_KEY em st.secrets.")
        return client_deepseek.chat.completions.create(
            messages=messages,
            model="deepseek-chat",
            temperature=temperature,
            response_format={"type": "json_object"},
            max_tokens=max_tokens,
        )


def gerar_questoes(
    qtd: int, origem: str, banca: str, cargo: str, concurso: str,
    materia: str, tema: str, usar_web: bool, modelo_escolhido: str,
) -> tuple:
    qtd_interno = max(qtd * 3, qtd + 4)

    ctx_juris = ctx_padrao = ctx_edital = ctx_reais = ""

    if usar_web:
        if origem == "Ineditas":
            ctx_juris = pesquisar_jurisprudencia_avancada(banca, cargo, concurso, materia, tema)
            ctx_padrao = pesquisar_padrao_banca_cargo(banca, cargo, concurso)
            ctx_edital = pesquisar_conteudo_programatico_especifico(cargo, concurso, materia)
        else:
            ctx_reais = pesquisar_questoes_reais_banca(banca, cargo, concurso, materia, tema, qtd_interno)
    else:
        ctx_juris = f"Use jurisprudência consolidada de {materia} para {cargo}."
        ctx_padrao = f"Padrão histórico da banca {banca}."
        ctx_edital = f"Conteúdo programático padrão de {cargo}."

    if origem == "Ineditas":
        prompt = prompt_questoes_ineditas(qtd_interno, banca, cargo, concurso, materia, tema, ctx_juris, ctx_padrao, ctx_edital)
        temp = 0.78
    else:
        prompt = prompt_questoes_reais(qtd_interno, banca, cargo, concurso, materia, tema, ctx_reais)
        temp = 0.18

    messages = [
        {"role": "system", "content": "Você gera APENAS JSON válido conforme o esquema fornecido. Sem markdown, sem texto fora do JSON."},
        {"role": "user", "content": prompt},
    ]

    resp = chamar_modelo(messages, modelo_escolhido, temperature=temp)
    raw = resp.choices[0].message.content
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        dados = json.loads(raw)
    except Exception as e:
        raise RuntimeError(f"Falha ao parsear JSON da IA: {e}\n\nResposta recebida:\n{raw[:500]}")

    lista: List[Dict[str, Any]] = dados.get("questoes", []) if isinstance(dados, dict) else (dados if isinstance(dados, list) else [])

    for q in lista:
        q.setdefault("materia", materia)
        q.setdefault("tema", tema)
        q.setdefault("banca", banca)
        q.setdefault("cargo", cargo)

    lista = dedup_lista(lista, materia, tema, banca, cargo)
    lista_validas = [q for q in lista if validar_questao(q)]
    lista_validas.sort(key=score_questao, reverse=True)
    return lista_validas[:qtd], len(lista), len(lista_validas)


# =========================================================
# ESTADO DE SESSÃO
# =========================================================
defaults = {
    "usuario_atual": None,
    "bateria_atual": [],
    "edital_ativo": None,
    "debug_mode": False,
    "tema_cooldown": [],
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

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
        if st.button("Criar e Entrar", use_container_width=True) and novo_nome.strip():
            try:
                c.execute("INSERT INTO usuarios (nome) VALUES (?)", (novo_nome.strip(),))
                conn.commit()
                st.session_state.usuario_atual = novo_nome.strip()
                st.success(f"Bem-vindo, {novo_nome.strip()}!")
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
    st.session_state.debug_mode = st.checkbox("��� Modo Debug", value=False)
    st.divider()

    if st.session_state.usuario_atual:
        st.header("📚 Biblioteca de Editais")

        df_editais = pd.read_sql_query(
            "SELECT id, nome_concurso, banca, cargo, dados_json, nivel_dificuldade, nome_concurso_completo "
            "FROM editais_salvos WHERE usuario = ? ORDER BY id DESC",
            conn,
            params=(st.session_state.usuario_atual,),
        )

        if not df_editais.empty:
            opcoes_editais = ["Selecione um edital..."] + [
                f"{row['nome_concurso']} ({row['cargo']})" for _, row in df_editais.iterrows()
            ]
            escolha = st.selectbox("Carregar Edital", opcoes_editais)
            if escolha != "Selecione um edital...":
                idx = opcoes_editais.index(escolha) - 1
                linha = df_editais.iloc[idx]
                _pcdet = obter_perfil_cargo(linha["cargo"])
                _pbdet = obter_perfil_banca(linha["banca"])
                _nome_completo = linha.get("nome_concurso_completo") or linha["nome_concurso"]
                try:
                    _materias = json.loads(linha["dados_json"]).get("materias", [])
                except Exception:
                    _materias = []
                st.session_state.edital_ativo = {
                    "nome_concurso": linha["nome_concurso"],
                    "nome_concurso_completo": _nome_completo,
                    "banca": linha["banca"],
                    "cargo": linha["cargo"],
                    "materias": _materias,
                    "nivel_dificuldade": _pcdet["nível"],
                    "formatos": _pbdet["formatos"],
                    "perfil_cargo": _pcdet,
                }
                st.success(
                    f"✅ {linha['nome_concurso']} carregado!\n"
                    f"Banca: **{linha['banca']}** | Nível: **{_pcdet['descrição']}**"
                )
        else:
            st.info("Nenhum edital salvo.")

        st.write("---")
        with st.expander("➕ Cadastrar Novo Edital", expanded=df_editais.empty):
            nome_novo = st.text_input("Nome curto (ex: PCDF 2024):")
            nome_completo_novo = st.text_input("Nome completo (opcional):")
            banca_nova = st.text_input("Banca (ex: Cebraspe, FCC):")
            cargo_novo = st.text_input("Cargo (ex: Delegado de Polícia Civil):")
            texto_colado = st.text_area("Cole o conteúdo programático:")

            if st.button("💾 Salvar Edital", use_container_width=True) and nome_novo.strip() and texto_colado.strip():
                with st.spinner("Extraindo matérias..."):
                    _pc = obter_perfil_cargo(cargo_novo)
                    _pb = obter_perfil_banca(banca_nova)
                    _prompt_edit = (
                        "Leia o conteúdo programático e extraia apenas as disciplinas/matérias principais. "
                        'Responda somente com JSON: {"materias": ["Disciplina 1", "Disciplina 2"]}.\n'
                        f"Texto: {texto_colado[:12000]}"
                    )
                    try:
                        if not client_groq:
                            raise RuntimeError("Configure GROQ_API_KEY em st.secrets.")
                        _resp = client_groq.chat.completions.create(
                            messages=[{"role": "user", "content": _prompt_edit}],
                            model="llama-3.3-70b-versatile",
                            temperature=0.1,
                            response_format={"type": "json_object"},
                        )
                        _texto_json = _resp.choices[0].message.content
                        c.execute(
                            """
                            INSERT INTO editais_salvos
                            (usuario, nome_concurso, banca, cargo, dados_json, data_analise,
                             nivel_dificuldade, formato_questoes, nome_concurso_completo)
                            VALUES (?,?,?,?,?,?,?,?,?)
                            """,
                            (
                                st.session_state.usuario_atual,
                                nome_novo.strip(),
                                banca_nova.strip(),
                                cargo_novo.strip(),
                                _texto_json,
                                datetime.now().isoformat(),
                                _pc["nível"],
                                json.dumps(_pb["formatos"]),
                                nome_completo_novo.strip() or nome_novo.strip(),
                            ),
                        )
                        conn.commit()
                        st.success("Edital salvo com sucesso!")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Erro ao estruturar edital: {ex}")

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
    st.title("🔒 Bem-vindo à Plataforma de Alta Performance")
    st.info("Selecione ou crie um perfil na barra lateral para começar.")
    st.stop()

st.title(f"📚 Plataforma de Alta Performance — {st.session_state.usuario_atual}")
st.write("---")

# --- Métricas ---
df_resp = pd.read_sql_query(
    "SELECT acertou FROM respostas WHERE usuario = ?",
    conn,
    params=(st.session_state.usuario_atual,),
)
total_resp = len(df_resp)
acertos = int(df_resp["acertou"].sum()) if total_resp > 0 else 0
taxa_acerto = round((acertos / total_resp) * 100, 1) if total_resp > 0 else 0

# CORRIGIDO: f-string com ternário dentro de atributo HTML — agora usa variável intermediária
cor_taxa = "#28a745" if taxa_acerto >= 70 else "#dc3545"

colA, colB, colC = st.columns(3)
with colA:
    st.markdown(
        '<div class="metric-box">'
        '<div class="metric-title">Itens Resolvidos</div>'
        f'<div class="metric-value">{total_resp}</div>'
        "</div>",
        unsafe_allow_html=True,
    )
with colB:
    st.markdown(
        '<div class="metric-box">'
        '<div class="metric-title">Acertos</div>'
        f'<div class="metric-value">{acertos}</div>'
        "</div>",
        unsafe_allow_html=True,
    )
with colC:
    st.markdown(
        '<div class="metric-box">'
        '<div class="metric-title">Aproveitamento</div>'
        f'<div class="metric-value" style="color:{cor_taxa};">{taxa_acerto}%</div>'
        "</div>",
        unsafe_allow_html=True,
    )

st.write("<br>", unsafe_allow_html=True)

# =========================================================
# GERADOR DE BATERIA
# =========================================================
# CORRIGIDO: border=True removido — compatível com qualquer versão do Streamlit
with st.container():
    st.subheader("⚡ Gerar Bateria de Questões")
    st.write("---")

    e = st.session_state.edital_ativo

    if e:
        banca_alvo = e["banca"]
        cargo_alvo = e["cargo"]
        concurso = e.get("nome_concurso_completo") or e["nome_concurso"]
        perfil_cargo_ativo = e.get("perfil_cargo", obter_perfil_cargo(cargo_alvo))

        st.markdown(
            f"<div class='concurso-box'>"
            f"🎯 <b>CONCURSO:</b> {concurso}<br>"
            f"🏢 <b>BANCA:</b> {banca_alvo} &nbsp;|&nbsp; "
            f"👮 <b>CARGO:</b> {cargo_alvo} &nbsp;|&nbsp; "
            f"🔥 <b>NÍVEL:</b> {perfil_cargo_ativo['descrição']}"
            f"</div>",
            unsafe_allow_html=True,
        )

        lista_materias = ["Aleatório"] + (e.get("materias") or [])
        c1, c2 = st.columns(2)
        with c1:
            mat_sel = st.selectbox("Matéria", lista_materias)
        with c2:
            tema_sel = st.text_input("Tema específico (ou 'Aleatório')", "Aleatório")
    else:
        st.warning("⚠️ Carregue um edital na barra lateral para calibração automática de dificuldade.")
        c1, c2, c3 = st.columns(3)
        with c1:
            banca_alvo = st.text_input("Banca", "Cebraspe")
        with c2:
            cargo_alvo = st.text_input("Cargo", "Delegado de Polícia Civil")
        with c3:
            mat_sel = st.text_input("Matéria", "Direito Penal")
        concurso = st.text_input("Nome do Concurso", "Concurso Público")
        tema_sel = st.text_input("Tema específico", "Aleatório")

    c3col, c4col = st.columns(2)
    with c3col:
        tipo = st.selectbox("Origem", ["🧠 Inéditas IA", "🌐 Questões Reais", "📂 Revisão (Banco Local)"])
    with c4col:
        qtd = st.slider("Quantidade de questões", 1, 10, 5)

    usar_web = st.checkbox("🌐 Pesquisa web avançada (jurisprudência + padrão da banca)", value=True)

    if st.button("🚀 Forjar Bateria", type="primary", use_container_width=True):
        # --- matéria final ---
        if e and mat_sel == "Aleatório" and e.get("materias"):
            mat_final = random.choice(e["materias"])
        else:
            mat_final = mat_sel

        # --- tema final com rotação anti-repetição ---
        if tema_sel.strip().lower() == "aleatório":
            if e and e.get("materias") and st.session_state.tema_cooldown:
                pool = [m for m in e["materias"] if m not in st.session_state.tema_cooldown[-3:]]
                if pool:
                    mat_final = random.choice(pool)
            tema_final = f"Tema mais cobrado e complexo de {mat_final} para {cargo_alvo}"
        else:
            tema_final = tema_sel.strip()

        # --- REVISÃO LOCAL ---
        if "Revisão" in tipo:
            st.info("🔄 Resgatando questões do banco local...")
            c.execute(
                """
                SELECT id FROM questoes
                WHERE (banca LIKE ? OR cargo LIKE ? OR materia LIKE ?)
                ORDER BY dificuldade DESC, RANDOM() LIMIT ?
                """,
                (f"%{banca_alvo}%", f"%{cargo_alvo}%", f"%{mat_final}%", qtd),
            )
            ids = [row[0] for row in c.fetchall()]
            if ids:
                st.session_state.bateria_atual = ids
                st.rerun()
            else:
                st.warning("Banco local insuficiente. Gere novas questões primeiro.")

        # --- GERAR IA ---
        else:
            origem = "Ineditas" if "Inéditas" in tipo else "Reais"
            modelo_flag = "groq" if "Groq" in motor_escolhido else "deepseek"
            progresso = st.progress(0, text="Iniciando...")

            try:
                progresso.progress(20, text="🔍 Buscando contexto..." if usar_web else "📋 Preparando prompt...")
                lista, total_bruto, total_validas = gerar_questoes(
                    qtd=qtd,
                    origem=origem,
                    banca=banca_alvo,
                    cargo=cargo_alvo,
                    concurso=concurso,
                    materia=mat_final,
                    tema=tema_final,
                    usar_web=usar_web,
                    modelo_escolhido=modelo_flag,
                )

                progresso.progress(80, text="💾 Salvando no banco...")
                novas_ids: List[int] = []
                duplicatas = 0

                for q in lista:
                    gab_norm = normalizar_gabarito(q.get("gabarito", ""))
                    hash_q = q.get("hash_calc") or gerar_hash_questao(
                        q.get("enunciado", ""), gab_norm, mat_final, tema_final, banca_alvo, cargo_alvo
                    )
                    if questao_ja_existe(hash_q):
                        duplicatas += 1
                        continue

                    alts_json = json.dumps(q.get("alternativas", {}))
                    exp_json = json.dumps({
                        "geral": q.get("explicacao", ""),
                        "detalhes": q.get("comentarios", {}),
                    })
                    nivel_q = q.get("dificuldade") or obter_perfil_cargo(cargo_alvo).get("nível", 3)

                    c.execute(
                        """
                        INSERT INTO questoes
                        (banca, cargo, materia, tema, enunciado, alternativas, gabarito,
                         explicacao, tipo, fonte, dificuldade, tags, formato_questao,
                         eh_real, ano_prova, hash_questao, subtema, juris_citada, validado, created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            banca_alvo, cargo_alvo, mat_final, tema_final,
                            q.get("enunciado", ""), alts_json, gab_norm, exp_json,
                            tipo, q.get("fonte", f"Inédita IA — {banca_alvo} — {cargo_alvo}"),
                            nivel_q, json.dumps(q.get("tags", [])),
                            q.get("formato", "Múltipla Escolha"),
                            1 if q.get("eh_real") else 0,
                            q.get("ano_prova", 0),
                            hash_q,
                            q.get("subtema", ""),
                            q.get("juris_citada", ""),
                            1,
                            datetime.now().isoformat(),
                        ),
                    )
                    novas_ids.append(c.lastrowid)

                conn.commit()
                st.session_state.bateria_atual = novas_ids
                if e:
                    st.session_state.tema_cooldown.append(mat_final)

                progresso.progress(100, text="✅ Concluído!")
                st.success(
                    f"✅ {len(novas_ids)} questões geradas "
                    f"(brutas: {total_bruto} | válidas: {total_validas} | duplicatas descartadas: {duplicatas})"
                )
                st.rerun()

            except Exception as err:
                progresso.empty()
                if "rate_limit" in str(err).lower() or "429" in str(err):
                    st.error("⚠️ Limite de requisições atingido. Troque para DeepSeek ou aguarde alguns minutos.")
                else:
                    st.error(f"❌ Erro na geração: {err}")
                if st.session_state.debug_mode:
                    st.code(traceback.format_exc())

# =========================================================
# CADERNO DE PROVA
# =========================================================
if st.session_state.bateria_atual:
    st.write("---")
    st.subheader("🎯 Caderno de Prova")

    ids_str = ",".join(map(str, st.session_state.bateria_atual))
    df_respostas = pd.read_sql_query(
        f"SELECT questao_id, resposta_usuario, acertou FROM respostas "
        f"WHERE usuario = ? AND questao_id IN ({ids_str})",
        conn,
        params=(st.session_state.usuario_atual,),
    )
    respondidas = df_respostas.set_index("questao_id").to_dict("index")

    for i, q_id in enumerate(st.session_state.bateria_atual):
        c.execute(
            """
            SELECT banca, cargo, materia, enunciado, alternativas, gabarito, explicacao,
                   fonte, dificuldade, tags, formato_questao, eh_real
            FROM questoes WHERE id = ?
            """,
            (q_id,),
        )
        dados = c.fetchone()
        if not dados:
            continue

        (q_banca, q_cargo, q_mat, q_enun, q_alt_raw, q_gab,
         q_exp_raw, q_fonte, q_dif, q_tags_raw, q_formato, eh_real) = dados

        # parse seguro de JSONs
        try:
            alts: Dict[str, str] = json.loads(q_alt_raw) if q_alt_raw else {}
        except Exception:
            alts = {}
        try:
            tags_list: List[str] = json.loads(q_tags_raw) if q_tags_raw else []
        except Exception:
            tags_list = []
        try:
            exp_data = json.loads(q_exp_raw) if q_exp_raw else {}
            exp_geral = exp_data.get("geral", q_exp_raw) if isinstance(exp_data, dict) else q_exp_raw
            exp_detalhes: Dict[str, str] = exp_data.get("detalhes", {}) if isinstance(exp_data, dict) else {}
        except Exception:
            exp_geral = q_exp_raw or ""
            exp_detalhes = {}

        q_gab_norm = normalizar_gabarito(q_gab)
        is_certo_errado = "Certo/Errado" in (q_formato or "")

        dif_val = q_dif or 3
        dif_idx = min(max(dif_val - 1, 0), 4)
        dif_label = ["Muito Fácil", "Fácil", "Médio", "Difícil", "Muito Difícil"][dif_idx]
        dif_classe = "dif-facil" if dif_val <= 2 else ("dif-medio" if dif_val == 3 else "dif-dificil")
        tipo_questao = "Prova Real" if eh_real else "Inédita IA"
        tipo_classe = "tipo-real" if eh_real else "tipo-inedita"

        if is_certo_errado:
            opcoes = ["Selecionar...", "Certo", "Errado"]
        elif alts:
            opcoes = ["Selecionar..."] + [f"{k}) {v}" for k, v in alts.items()]
        else:
            opcoes = ["Selecionar...", "A", "B", "C", "D", "E"]

        # CORRIGIDO: border=True removido
        with st.container():
            st.write("---")
            col_info, col_tipo, col_dif_col = st.columns([3, 1, 1])
            with col_info:
                st.caption(f"**Item {i+1}** | 🏢 {q_banca} | 📚 {q_mat} | 🎯 {q_formato or 'N/D'}")
            with col_tipo:
                st.markdown(f"<span class='tipo-badge {tipo_classe}'>{tipo_questao}</span>", unsafe_allow_html=True)
            with col_dif_col:
                st.markdown(f"<span class='dificuldade-badge {dif_classe}'>{dif_label}</span>", unsafe_allow_html=True)

            if tags_list:
                st.caption(f"🏷️ {', '.join(tags_list)}")
            if q_fonte:
                st.caption(f"📌 {q_fonte}")

            st.markdown(f"**{q_enun}**")

            # --- Já respondida ---
            if q_id in respondidas:
                status = respondidas[q_id]
                resp_salva = normalizar_gabarito(str(status["resposta_usuario"]))

                if st.session_state.debug_mode:
                    st.markdown(
                        f"<div class='debug-box'>DEBUG | "
                        f"Gabarito banco: <code>{q_gab!r}</code> → norm: <code>{q_gab_norm!r}</code> | "
                        f"Resp salva: <code>{status['resposta_usuario']!r}</code> → norm: <code>{resp_salva!r}</code> | "
                        f"Acertou: <code>{status['acertou']}</code></div>",
                        unsafe_allow_html=True,
                    )

                st.markdown("<br><b>Análise das Alternativas:</b>", unsafe_allow_html=True)
                for opcao in opcoes[1:]:
                    letra_opcao = extrair_letra_opcao(opcao, not is_certo_errado)
                    is_usuario = letra_opcao == resp_salva
                    is_gabarito = letra_opcao == q_gab_norm

                    if is_usuario:
                        css = "alt-correta" if status["acertou"] == 1 else "alt-errada"
                        icon = "✅" if status["acertou"] == 1 else "❌"
                        label = "(Sua Resposta — Correta)" if status["acertou"] == 1 else "(Sua Resposta — Incorreta)"
                        st.markdown(f"<div class='{css}'>{icon} <b>{opcao}</b> {label}</div>", unsafe_allow_html=True)
                    elif is_gabarito and status["acertou"] == 0:
                        st.markdown(f"<div class='alt-gabarito'>🎯 <b>{opcao}</b> (Gabarito Oficial)</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div class='alt-neutra'>{opcao}</div>", unsafe_allow_html=True)

                    if not is_certo_errado and letra_opcao in exp_detalhes and exp_detalhes[letra_opcao]:
                        st.markdown(
                            f"<div class='comentario-alt'>💡 <b>Por que?</b> {exp_detalhes[letra_opcao]}</div>",
                            unsafe_allow_html=True,
                        )

                with st.expander("📖 Fundamentação Legal Completa"):
                    st.write(exp_geral)

            # --- Ainda não respondida ---
            else:
                if st.session_state.debug_mode:
                    st.markdown(
                        f"<div class='debug-box'>DEBUG | Gabarito esperado: <code>{q_gab_norm!r}</code></div>",
                        unsafe_allow_html=True,
                    )

                resp = st.radio("Sua Resposta:", opcoes, key=f"rad_{q_id}", label_visibility="collapsed")
                if st.button("✅ Confirmar Resposta", key=f"btn_{q_id}"):
                    if resp != "Selecionar...":
                        letra_escolhida = extrair_letra_opcao(resp, not is_certo_errado)
                        acertou = 1 if letra_escolhida == q_gab_norm else 0
                        c.execute(
                            "INSERT INTO respostas (usuario, questao_id, resposta_usuario, acertou, data) VALUES (?,?,?,?,?)",
                            (st.session_state.usuario_atual, q_id, letra_escolhida, acertou, datetime.now().isoformat()),
                        )
                        conn.commit()
                        st.rerun()
                    else:
                        st.warning("⚠️ Selecione uma opção antes de confirmar.")
