import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import json
import random
import re
from groq import Groq
from openai import OpenAI
from duckduckgo_search import DDGS
import hashlib

# ================= CONFIGURAÇÃO VISUAL =================
st.set_page_config(page_title="Plataforma de Alta Performance", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
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
    .banca-info  { background-color: #e7f3ff; border-left: 4px solid #0066cc; padding: 12px; border-radius: 5px; margin-bottom: 15px; }
    .tipo-badge  { display: inline-block; padding: 4px 10px; border-radius: 15px; font-size: 11px; font-weight: bold; margin-right: 5px; }
    .tipo-inedita { background-color: #ffd700; color: #333; }
    .tipo-real    { background-color: #87ceeb; color: #000; }
    .debug-box    { background-color: #fff8dc; border: 1px dashed #aaa; padding: 8px 12px; border-radius: 5px; font-size: 12px; font-family: monospace; margin-top: 5px; }
    .concurso-box { background-color: #1a1a2e; color: #e0e0e0; border-left: 5px solid #e94560; padding: 14px; border-radius: 8px; margin-bottom: 16px; }
    .concurso-box b { color: #e94560; }
    </style>
""", unsafe_allow_html=True)

# =================================================================================
# PERFIS DETALHADOS DE BANCAS
# =================================================================================
PERFIL_BANCAS = {
    "Cebraspe": {
        "formatos": ["Certo/Errado"],
        "caracteristicas": [
            "assertivas precisas que exigem conhecimento profundo",
            "jurisprudência consolidada do STF e STJ",
            "interpretação literal e sistemática de normas",
            "pegadinhas baseadas em exceções legais",
            "teses firmadas em repercussão geral e recursos repetitivos",
        ],
        "quantidade_alternativas": 2,
        "estilo_enunciado": "objetivo, assertivo, frequentemente com pegadinhas sutis em exceções",
        "dificuldade_base": 4,
        "sites_busca": ["cebraspe.org.br", "tecconcursos.com.br", "qconcursos.com", "estrategiaconcursos.com.br"],
    },
    "FCC": {
        "formatos": ["Múltipla Escolha (A a E)"],
        "caracteristicas": [
            "análise textual minuciosa de dispositivos legais",
            "distinção entre institutos jurídicos similares",
            "raciocínio lógico-jurídico",
            "aplicação de normas a casos concretos",
        ],
        "quantidade_alternativas": 5,
        "estilo_enunciado": "contextualizado com caso concreto ou transcrição normativa",
        "dificuldade_base": 3,
        "sites_busca": ["fcc.org.br", "tecconcursos.com.br", "qconcursos.com"],
    },
    "Vunesp": {
        "formatos": ["Múltipla Escolha (A a E)"],
        "caracteristicas": [
            "jurisprudência recente dos tribunais superiores",
            "casos práticos com múltiplos institutos envolvidos",
            "aplicação prática com resultado específico",
        ],
        "quantidade_alternativas": 5,
        "estilo_enunciado": "descritivo com situação fática detalhada",
        "dificuldade_base": 3,
        "sites_busca": ["vunesp.com.br", "tecconcursos.com.br", "qconcursos.com"],
    },
    "OAB": {
        "formatos": ["Múltipla Escolha (A a D)"],
        "caracteristicas": [
            "casos práticos com múltiplos institutos",
            "ética e estatuto da OAB",
            "súmulas vinculantes e precedentes obrigatórios",
            "direitos fundamentais aplicados",
        ],
        "quantidade_alternativas": 4,
        "estilo_enunciado": "caso concreto com cliente/advogado pedindo providência",
        "dificuldade_base": 4,
        "sites_busca": ["oab.org.br", "tecconcursos.com.br", "qconcursos.com"],
    },
    "ESAF": {
        "formatos": ["Múltipla Escolha (A a E)"],
        "caracteristicas": [
            "precisão conceitual técnica e fiscal",
            "legislação tributária federal atualizada",
            "contabilidade e administração pública",
        ],
        "quantidade_alternativas": 5,
        "estilo_enunciado": "técnico com termos fiscais e administrativos",
        "dificuldade_base": 4,
        "sites_busca": ["esaf.org.br", "tecconcursos.com.br", "qconcursos.com"],
    },
    "IADES": {
        "formatos": ["Múltipla Escolha (A a E)"],
        "caracteristicas": [
            "conceitos aplicados com análise comparativa",
            "legislação específica do órgão",
            "raciocínio crítico e análise de situações",
        ],
        "quantidade_alternativas": 5,
        "estilo_enunciado": "contextualizado com comparação de institutos",
        "dificuldade_base": 3,
        "sites_busca": ["iades.org.br", "tecconcursos.com.br", "qconcursos.com"],
    },
    "UFF": {
        "formatos": ["Múltipla Escolha (A a D)"],
        "caracteristicas": ["conceitos fundamentais", "legislação básica", "aplicação simples"],
        "quantidade_alternativas": 4,
        "estilo_enunciado": "direto e simples",
        "dificuldade_base": 2,
        "sites_busca": ["uff.br", "tecconcursos.com.br", "qconcursos.com"],
    },
    "UFPR": {
        "formatos": ["Múltipla Escolha (A a E)"],
        "caracteristicas": ["análise doutrinária profunda", "jurisprudência consolidada", "interpretação sistemática"],
        "quantidade_alternativas": 5,
        "estilo_enunciado": "aprofundado com referência doutrinária",
        "dificuldade_base": 4,
        "sites_busca": ["ufpr.br", "tecconcursos.com.br", "qconcursos.com"],
    },
    "Defesa": {
        "formatos": ["Múltipla Escolha (A a E)"],
        "caracteristicas": ["legislação militar", "hierarquia e disciplina", "regulamentos específicos das Forças Armadas"],
        "quantidade_alternativas": 5,
        "estilo_enunciado": "técnico militar com referência regulamentar",
        "dificuldade_base": 3,
        "sites_busca": ["defesa.gov.br", "tecconcursos.com.br", "qconcursos.com"],
    },
    "Aeronáutica": {
        "formatos": ["Múltipla Escolha (A a E)"],
        "caracteristicas": ["segurança aérea e ANAC", "regulamentações FAB", "procedimentos técnicos aeronáuticos"],
        "quantidade_alternativas": 5,
        "estilo_enunciado": "técnico com terminologia aeronáutica",
        "dificuldade_base": 4,
        "sites_busca": ["fab.mil.br", "tecconcursos.com.br", "qconcursos.com"],
    },
}

# =================================================================================
# PERFIS DETALHADOS DE CARGOS — NÍVEL DE DIFICULDADE E DNA DA PROVA
# =================================================================================
PERFIL_CARGO_DIFICULDADE = {
    "Delegado de Polícia Civil": {
        "nível": 5, "descrição": "Muito Difícil — Nível Magistratura",
        "exige": [
            "domínio absoluto do CPP, CP, Lei de Drogas (11.343/06), Lei de Organização Criminosa (12.850/13)",
            "jurisprudência do STF e STJ sobre prisões, provas ilícitas e investigação criminal",
            "Inquérito Policial: presidência, poderes e limites do Delegado",
            "Acordo de não persecução penal e colaboração premiada",
            "Interceptação telefônica (Lei 9.296/96) e captação ambiental (Lei 13.964/19 - Pacote Anticrime)",
            "Identificação criminal, laudo pericial, cadeia de custódia",
            "Direitos humanos aplicados à atividade policial — Convenção de Belém do Pará, Protocolo de Istambul",
            "Estatuto da Criança e do Adolescente — ato infracional e medidas socioeducativas",
            "Lei Maria da Penha (11.340/06) e feminicídio",
            "Crimes contra a Administração Pública e improbidade",
        ],
        "estilo_questao": [
            "caso concreto complexo com múltiplos institutos em conflito",
            "jurisprudência recente do STF ou STJ que inverteu o entendimento anterior",
            "distinção entre institutos processuais similares (prisão preventiva x temporária, flagrante próprio x impróprio)",
            "aplicação de teses firmadas em HC ou RHC recentes",
            "questão sobre poderes investigatórios do Delegado vs. MP",
        ],
        "exemplos_temas_avancados": [
            "Teoria do crime organizado e infiltração policial",
            "Audiência de custódia e controle de convencionalidade",
            "Nemo tenetur se detegere e seus desdobramentos na investigação",
            "Cadeia de custódia: consequências processuais da violação (Pacote Anticrime)",
            "Distinção entre agente infiltrado e agente provocador",
            "Acordo de não persecução penal: requisitos e consequências do descumprimento",
            "Prisão domiciliar: hipóteses legais e jurisprudência do STJ",
            "Prova emprestada: requisitos de validade e contraditório diferido",
        ],
    },
    "Delegado da Polícia Federal": {
        "nível": 5, "descrição": "Muito Difícil — Nível Magistratura Federal",
        "exige": [
            "Crimes federais: tráfico transnacional, lavagem de dinheiro (9.613/98), crimes cibernéticos",
            "Lei 9.296/96 e Marco Civil da Internet (12.965/14)",
            "Cooperação internacional e extradição",
            "Organização criminosa (12.850/13) e ENCCLA",
            "Sigilo bancário e fiscal: LC 105/01 e STF",
            "Legislação antiterrorismo (13.260/16)",
        ],
        "estilo_questao": [
            "caso concreto com crime transnacional",
            "conflito de competência federal x estadual",
            "distinção entre crimes conexos e continência",
        ],
        "exemplos_temas_avancados": [
            "Lavagem de dinheiro: fases e tipicidade autônoma",
            "Colaboração premiada: natureza jurídica e eficácia probatória",
            "Competência da PF: critérios constitucionais e jurisprudência",
        ],
    },
    "Delegado": {
        "nível": 5, "descrição": "Muito Difícil — Nível Magistratura",
        "exige": [
            "CPP, CP, legislação especial penal",
            "jurisprudência STF/STJ atualizada",
            "investigação criminal e poderes do Delegado",
            "Direitos humanos e garantias fundamentais",
        ],
        "estilo_questao": [
            "caso concreto com múltiplos institutos",
            "jurisprudência recente que alterou entendimento",
            "distinção entre institutos similares",
        ],
        "exemplos_temas_avancados": [
            "Pacote Anticrime e alterações no CPP",
            "Acordo de não persecução penal",
            "Cadeia de custódia da prova",
        ],
    },
    "Juiz de Direito": {
        "nível": 5, "descrição": "Muito Difícil — Nível Magistratura",
        "exige": [
            "processo civil e processo penal em nível avançado",
            "direito constitucional e controle de constitucionalidade",
            "súmulas vinculantes e precedentes obrigatórios",
            "direito civil e empresarial complexo",
        ],
        "estilo_questao": [
            "casos com múltiplos recursos e incidentes processuais",
            "conflito entre normas e solução pelo STF",
            "questões sobre decisão judicial — fundamentação e efeitos",
        ],
        "exemplos_temas_avancados": [
            "IRDR e precedentes vinculantes no CPC/2015",
            "Tutelas de urgência e evidência — distinção e requisitos",
            "Teoria dos precedentes e distinguishing",
        ],
    },
    "Procurador": {
        "nível": 5, "descrição": "Muito Difícil",
        "exige": [
            "direito público em nível avançado",
            "controle de constitucionalidade concentrado e difuso",
            "improbidade administrativa (14.230/21)",
            "responsabilidade civil do Estado",
        ],
        "estilo_questao": ["caso concreto de improbidade", "ADI/ADC e efeitos erga omnes", "responsabilidade objetiva do Estado"],
        "exemplos_temas_avancados": ["Nova Lei de Improbidade e alterações", "Responsabilidade por omissão do Estado"],
    },
    "Analista": {
        "nível": 3, "descrição": "Médio",
        "exige": ["conceitos sólidos da área", "legislação objetiva", "casos práticos padrão"],
        "estilo_questao": ["conceito aplicado a caso", "distinção entre procedimentos", "legislação específica do órgão"],
        "exemplos_temas_avancados": ["fluxos procedimentais", "prazos e formalidades", "competências do órgão"],
    },
    "Assistente": {
        "nível": 2, "descrição": "Fácil a Médio",
        "exige": ["conceitos básicos", "legislação clara e direta", "operações simples"],
        "estilo_questao": ["definição direta", "procedimento padrão", "regra geral sem exceções"],
        "exemplos_temas_avancados": ["atendimento ao público", "documentos e protocolos", "noções de direito"],
    },
    "Investigador": {
        "nível": 3, "descrição": "Médio",
        "exige": ["noções de CPP e CP", "procedimentos de investigação", "atribuições da polícia civil"],
        "estilo_questao": ["procedimento de flagrante", "lavratura de BO", "medidas cautelares básicas"],
        "exemplos_temas_avancados": ["flagrante delito e suas espécies", "preservação da cena do crime", "auto de prisão"],
    },
    "Auditor": {
        "nível": 4, "descrição": "Difícil",
        "exige": ["contabilidade pública avançada", "lei de responsabilidade fiscal", "auditoria governamental"],
        "estilo_questao": ["balanço patrimonial e resultado", "receitas e despesas públicas", "irregularidades e sanções"],
        "exemplos_temas_avancados": ["NBCASP", "SIAFI e controle interno", "Tribunal de Contas"],
    },
    "Oficial": {
        "nível": 2, "descrição": "Fácil a Médio",
        "exige": ["procedimentos operacionais básicos", "legislação direta do órgão"],
        "estilo_questao": ["regra geral aplicada", "procedimento padrão", "competências do cargo"],
        "exemplos_temas_avancados": ["organização policial", "uso da força", "legislação funcional"],
    },
}

# =================================================================================
# FUNÇÕES DE NORMALIZAÇÃO — definidas ANTES do banco
# =================================================================================

def normalizar_gabarito(gabarito_raw):
    """
    Converte qualquer formato de gabarito para letra isolada ou CERTO/ERRADO.
    Exemplos: 'A)', 'Letra A', 'a', 'certo', 'ERRADO', 'A) texto completo' -> 'A' / 'CERTO' / 'ERRADO'
    """
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


def extrair_letra_opcao(opcao_texto, tem_alternativas):
    """
    Extrai a letra de uma opção exibida no radio button.
    'A) texto da alternativa' -> 'A' | 'Certo' -> 'CERTO'
    """
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


# =================================================================================
# CHAVES DE IA
# =================================================================================
try:
    client_groq = Groq(api_key=st.secrets["GROQ_API_KEY"])
    client_deepseek = OpenAI(api_key=st.secrets["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
except Exception as e:
    st.error("Erro ao carregar as chaves de API. Verifique os Segredos no Streamlit.")


# =================================================================================
# FUNÇÕES DE PESQUISA AVANÇADA
# =================================================================================

def pesquisar_questoes_reais_banca(banca, cargo, concurso, materia, tema, quantidade):
    """
    Busca questões reais de provas anteriores com foco no concurso específico.
    Prioriza o concurso exato antes de buscar por cargo/banca genérico.
    """
    try:
        ddgs = DDGS()
        # Queries ordenadas do mais específico ao mais genérico
        queries = [
            f'questão prova "{concurso}" "{banca}" "{materia}" gabarito resolução',
            f'"{banca}" "{cargo}" "{materia}" prova concurso gabarito site:tecconcursos.com.br',
            f'"{banca}" "{cargo}" "{materia}" site:qconcursos.com questão gabarito',
            f'concurso "{cargo}" "{banca}" "{materia}" "{tema}" questão prova resolvida',
            f'"{banca}" "{cargo}" "{materia}" enunciado alternativas gabarito oficial',
        ]
        questoes_encontradas = []
        for query in queries:
            try:
                resultados = ddgs.text(query, max_results=8)
                for r in resultados:
                    texto = r.get('body', '')
                    if any(p in texto.lower() for p in ['gabarito', 'alternativa', 'resposta', 'questão', 'prova']):
                        questoes_encontradas.append(texto)
            except:
                continue
            if len(questoes_encontradas) >= quantidade * 3:
                break
        contexto = "\n---\n".join(questoes_encontradas[:quantidade * 4])
        return contexto[:18000] if contexto else "Nenhuma questão real encontrada."
    except:
        return "Busca indisponível."


def pesquisar_jurisprudencia_avancada(banca, cargo, concurso, materia, tema):
    """
    Busca jurisprudência específica, doutrina e informativos relevantes para o concurso.
    """
    try:
        ddgs = DDGS()
        queries = [
            f'"{materia}" "{tema}" STJ STF jurisprudência 2023 2024 informativo',
            f'"{tema}" "{materia}" precedente vinculante STF tese repercussão geral',
            f'"{cargo}" "{materia}" "{tema}" questão julgado recente STJ informativo',
            f'"{tema}" "{materia}" doutrina conceito distinção institutos concurso',
            f'"{banca}" "{cargo}" "{materia}" banca cobrou jurisprudência gabarito',
        ]
        resultados_compilados = []
        for query in queries:
            try:
                resultados = ddgs.text(query, max_results=6)
                for r in resultados:
                    resultados_compilados.append(r.get('body', ''))
            except:
                continue
        contexto = "\n---\n".join(resultados_compilados)
        return contexto[:12000] if contexto else "Jurisprudência não localizada."
    except:
        return "Busca de jurisprudência indisponível."


def pesquisar_padrao_banca_cargo(banca, cargo, concurso):
    """
    Busca o padrão histórico de questões da banca para aquele cargo específico.
    """
    try:
        ddgs = DDGS()
        queries = [
            f'"{banca}" "{cargo}" padrão questões dificuldade nível concurso análise',
            f'"{concurso}" análise prova questões dificuldade resolução comentada',
            f'"{banca}" "{cargo}" provas anteriores temas mais cobrados estatísticas',
        ]
        resultados_compilados = []
        for query in queries:
            try:
                resultados = ddgs.text(query, max_results=5)
                for r in resultados:
                    resultados_compilados.append(r.get('body', ''))
            except:
                continue
        contexto = "\n---\n".join(resultados_compilados)
        return contexto[:8000] if contexto else "Padrão não localizado."
    except:
        return "Busca indisponível."


def pesquisar_conteudo_programatico_especifico(cargo, concurso, materia):
    """
    Busca os tópicos cobrados especificamente naquele concurso para a matéria.
    """
    try:
        ddgs = DDGS()
        queries = [
            f'"{concurso}" conteúdo programático "{materia}" edital tópicos cobrados',
            f'"{cargo}" "{materia}" temas mais cobrados concurso público 2022 2023 2024',
            f'"{concurso}" edital "{materia}" itens exigidos estudo',
        ]
        resultados_compilados = []
        for query in queries:
            try:
                resultados = ddgs.text(query, max_results=5)
                for r in resultados:
                    resultados_compilados.append(r.get('body', ''))
            except:
                continue
        contexto = "\n---\n".join(resultados_compilados)
        return contexto[:8000] if contexto else ""
    except:
        return ""


# =================================================================================
# MIGRAÇÃO E NORMALIZAÇÃO DO BANCO
# =================================================================================

def migrar_banco_de_dados(conn):
    cur = conn.cursor()
    colunas = [
        ("editais_salvos", "nivel_dificuldade", "INTEGER DEFAULT 3"),
        ("editais_salvos", "formato_questoes",  "TEXT DEFAULT '[]'"),
        ("editais_salvos", "nome_concurso_completo", "TEXT DEFAULT ''"),
        ("questoes", "dificuldade",    "INTEGER DEFAULT 3"),
        ("questoes", "tags",           "TEXT DEFAULT '[]'"),
        ("questoes", "formato_questao","TEXT DEFAULT 'Múltipla Escolha'"),
        ("questoes", "eh_real",        "INTEGER DEFAULT 0"),
        ("questoes", "ano_prova",      "INTEGER DEFAULT 0"),
        ("questoes", "hash_questao",   "TEXT DEFAULT ''"),
        ("respostas", "tempo_resposta","INTEGER DEFAULT 0"),
    ]
    for tabela, coluna, tipo in colunas:
        try:
            cur.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
            conn.commit()
        except:
            pass


def normalizar_gabaritos_no_banco(conn):
    cur = conn.cursor()
    cur.execute("SELECT id, gabarito FROM questoes")
    atualizadas = 0
    for q_id, gab_raw in cur.fetchall():
        gab_norm = normalizar_gabarito(gab_raw)
        if gab_norm != str(gab_raw):
            cur.execute("UPDATE questoes SET gabarito = ? WHERE id = ?", (gab_norm, q_id))
            atualizadas += 1
    conn.commit()
    return atualizadas


# =================================================================================
# BANCO DE DADOS
# =================================================================================

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
            hash_questao TEXT DEFAULT ''
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
    conn.commit()
    return conn


# ── Inicializa e migra ──────────────────────────────────────────────────────────
conn = iniciar_conexao()
migrar_banco_de_dados(conn)
normalizar_gabaritos_no_banco(conn)
c = conn.cursor()

# ── Estado da sessão ────────────────────────────────────────────────────────────
if "usuario_atual"  not in st.session_state: st.session_state.usuario_atual  = None
if "bateria_atual"  not in st.session_state: st.session_state.bateria_atual  = []
if "edital_ativo"   not in st.session_state: st.session_state.edital_ativo   = None
if "debug_mode"     not in st.session_state: st.session_state.debug_mode     = False


# =================================================================================
# FUNÇÕES AUXILIARES
# =================================================================================

def obter_perfil_cargo(cargo_nome):
    """Retorna o perfil do cargo com maior correspondência (maior chave mais específica primeiro)."""
    cargo_upper = cargo_nome.upper()
    melhor_chave = None
    maior_len = 0
    for chave in PERFIL_CARGO_DIFICULDADE:
        if chave.upper() in cargo_upper or cargo_upper in chave.upper():
            if len(chave) > maior_len:
                melhor_chave = chave
                maior_len = len(chave)
    if melhor_chave:
        return PERFIL_CARGO_DIFICULDADE[melhor_chave]
    return {"nível": 3, "descrição": "Médio", "exige": ["Padrão"], "estilo_questao": ["Padrão"], "exemplos_temas_avancados": []}


def obter_perfil_banca(banca_nome):
    for chave, valor in PERFIL_BANCAS.items():
        if chave.lower() in banca_nome.lower() or banca_nome.lower() in chave.lower():
            return valor
    return {
        "formatos": ["Múltipla Escolha (A a E)"],
        "caracteristicas": ["padrão"],
        "quantidade_alternativas": 5,
        "estilo_enunciado": "padrão",
        "dificuldade_base": 3,
        "sites_busca": ["tecconcursos.com.br", "qconcursos.com"],
    }


def gerar_hash_questao(enunciado, gabarito):
    return hashlib.md5(f"{enunciado}_{gabarito}".lower().strip().encode()).hexdigest()


def questao_ja_existe(enunciado, gabarito):
    c.execute("SELECT id FROM questoes WHERE hash_questao = ?", (gerar_hash_questao(enunciado, gabarito),))
    return c.fetchone() is not None


# =================================================================================
# GERAÇÃO DE PROMPTS — ALTA DIFICULDADE
# =================================================================================

def construir_sistema_dificuldade(perfil_cargo, perfil_banca, banca_alvo, cargo_alvo, concurso, mat_final, tema_selecionado):
    """
    Monta o bloco de instruções de dificuldade e estilo com base no perfil do cargo e banca.
    Este é o coração da geração de questões de alto nível.
    """
    nivel = perfil_cargo.get("nível", 3)
    descricao = perfil_cargo.get("descrição", "Médio")
    exige = perfil_cargo.get("exige", [])
    estilos = perfil_cargo.get("estilo_questao", [])
    temas_avancados = perfil_cargo.get("exemplos_temas_avancados", [])
    caract_banca = perfil_banca.get("caracteristicas", [])
    estilo_banca = perfil_banca.get("estilo_enunciado", "")

    exige_str = "\n    - ".join(exige)
    estilos_str = "\n    - ".join(estilos)
    temas_avancados_str = "\n    - ".join(temas_avancados)
    caract_banca_str = "\n    - ".join(caract_banca)

    return f"""
══════════════════════════════════════════════════════════
  PARÂMETROS DO CONCURSO ALVO
══════════════════════════════════════════════════════════
  Concurso: {concurso}
  Cargo: {cargo_alvo}
  Banca: {banca_alvo}
  Matéria: {mat_final}
  Tema: {tema_selecionado}
  Nível de dificuldade: {descricao} ({nivel}/5)

══════════════════════════════════════════════════════════
  O QUE ESTE CARGO EXIGE (BASE DO NÍVEL DE DIFICULDADE)
══════════════════════════════════════════════════════════
    - {exige_str}

══════════════════════════════════════════════════════════
  ESTILO DE QUESTÃO DO CARGO {cargo_alvo}
══════════════════════════════════════════════════════════
    - {estilos_str}

══════════════════════════════════════════════════════════
  EXEMPLOS DE TEMAS AVANÇADOS COBRADOS PARA ESTE CARGO
══════════════════════════════════════════════════════════
    - {temas_avancados_str}

══════════════════════════════════════════════════════════
  CARACTERÍSTICAS DA BANCA {banca_alvo}
══════════════════════════════════════════════════════════
    - {caract_banca_str}
  Estilo de enunciado: {estilo_banca}

══════════════════════════════════════════════════════════
  OBRIGAÇÕES DE DIFICULDADE — NÃO NEGOCIÁVEL
══════════════════════════════════════════════════════════
  1. PROIBIDO fazer questões sobre conceitos básicos ou definições simples.
  2. OBRIGATÓRIO usar casos concretos complexos com múltiplos institutos em conflito.
  3. OBRIGATÓRIO referenciar jurisprudência real (STF/STJ) ou doutrina consolidada.
  4. Os distratores (alternativas erradas) devem ser plausíveis e tecnicamente sofisticados.
  5. O gabarito deve exigir raciocínio jurídico aprofundado, não mera memorização.
  6. A questão deve representar o nível de dificuldade de APROVADOS no concurso {concurso}, não de iniciantes.
  7. Se o cargo é {cargo_alvo}, a questão deve ser equivalente às provas de magistratura ou ministério público quando aplicável.
"""


def gerar_prompt_questoes_ineditas(qtd, banca_alvo, cargo_alvo, concurso, mat_final, tema_selecionado,
                                    contexto_jurisprudencia, contexto_padrao, contexto_conteudo):
    perfil_banca  = obter_perfil_banca(banca_alvo)
    perfil_cargo  = obter_perfil_cargo(cargo_alvo)
    formato_principal = perfil_banca["formatos"][0]

    sistema_dif = construir_sistema_dificuldade(
        perfil_cargo, perfil_banca, banca_alvo, cargo_alvo, concurso, mat_final, tema_selecionado
    )

    if "Certo/Errado" in formato_principal:
        instrucao_formato = f"""
FORMATO: Certo/Errado (Padrão {banca_alvo})
- Assertiva técnica com casos concretos e pegadinhas baseadas em exceções/jurisprudência
- Campo "gabarito": SOMENTE "Certo" ou "Errado" — nenhum texto adicional
- Campo "alternativas": {{}} (vazio)"""
        exemplo_alternativas = '"alternativas": {}'
    elif "A a D" in formato_principal:
        instrucao_formato = f"""
FORMATO: Múltipla Escolha 4 alternativas (A, B, C, D)
- Campo "gabarito": SOMENTE a letra, ex: "B"
- Todas as alternativas devem ser plausíveis e tecnicamente sofisticadas"""
        exemplo_alternativas = '"alternativas": {"A": "...", "B": "...", "C": "...", "D": "..."}'
    else:
        instrucao_formato = f"""
FORMATO: Múltipla Escolha 5 alternativas (A, B, C, D, E)
- Campo "gabarito": SOMENTE a letra, ex: "C"
- Todas as alternativas devem ser plausíveis e tecnicamente sofisticadas
- Distratores devem ser erros sutis que um candidato mediocre cometeria"""
        exemplo_alternativas = '"alternativas": {"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."}'

    nivel = perfil_cargo.get("nível", 3)

    prompt = f"""
Você é um preparador de concursos de alto nível especializado em elaborar questões para os concursos mais difíceis do Brasil.
Sua missão é criar questões INÉDITAS que representem fielmente o nível real do concurso descrito abaixo.

{sistema_dif}

══════════════════════════════════════════════════════════
  JURISPRUDÊNCIA E CONTEXTO PESQUISADOS
══════════════════════════════════════════════════════════
{contexto_jurisprudencia[:3000]}

══════════════════════════════════════════════════════════
  PADRÃO HISTÓRICO DA BANCA PARA ESTE CARGO
══════════════════════════════════════════════════════════
{contexto_padrao[:2000]}

══════════════════════════════════════════════════════════
  CONTEÚDO PROGRAMÁTICO ESPECÍFICO
══════════════════════════════════════════════════════════
{contexto_conteudo[:2000]}

══════════════════════════════════════════════════════════
  INSTRUÇÃO FINAL
══════════════════════════════════════════════════════════
Crie EXATAMENTE {qtd} questões INÉDITAS sobre "{tema_selecionado}" em "{mat_final}".

{instrucao_formato}

⚠️ CAMPO "gabarito": use SOMENTE a letra (ex: "A") ou "Certo"/"Errado" — JAMAIS texto adicional.

Responda APENAS com o JSON abaixo, sem markdown, sem explicações fora do JSON:

{{
  "questoes": [
    {{
      "enunciado": "Caso concreto complexo com múltiplos institutos. NÃO faça pergunta básica de definição.",
      {exemplo_alternativas},
      "gabarito": "A",
      "explicacao": "Fundamentação com referência à legislação (art. X da Lei Y), jurisprudência (STF/STJ - HC XXXXX ou Informativo NNN) e doutrina relevante. Mínimo 5 linhas.",
      "comentarios": {{
        "A": "Por que esta alternativa está correta/errada — explicação técnica com base legal",
        "B": "Por que esta alternativa está correta/errada — explicação técnica com base legal",
        "C": "Por que esta alternativa está correta/errada — explicação técnica com base legal",
        "D": "Por que esta alternativa está correta/errada — explicação técnica com base legal",
        "E": "Por que esta alternativa está correta/errada — explicação técnica com base legal"
      }},
      "fonte": "Inédita IA — Padrão {banca_alvo} — {cargo_alvo} — Nível {nivel}/5",
      "dificuldade": {nivel},
      "tags": ["{mat_final}", "{tema_selecionado}", "{cargo_alvo}", "nível-{nivel}"],
      "formato": "{formato_principal}",
      "eh_real": 0
    }}
  ]
}}
"""
    return prompt


def gerar_prompt_questoes_reais(qtd, banca_alvo, cargo_alvo, concurso, mat_final, tema_selecionado, contexto_reais):
    perfil_banca  = obter_perfil_banca(banca_alvo)
    perfil_cargo  = obter_perfil_cargo(cargo_alvo)
    formato_principal = perfil_banca["formatos"][0]
    nivel = perfil_cargo.get("nível", 3)

    if "Certo/Errado" in formato_principal:
        exemplo_alternativas = '"alternativas": {}'
        instrucao_gab = '"gabarito": SOMENTE "Certo" ou "Errado"'
    elif "A a D" in formato_principal:
        exemplo_alternativas = '"alternativas": {"A": "...", "B": "...", "C": "...", "D": "..."}'
        instrucao_gab = '"gabarito": SOMENTE a letra, ex: "B"'
    else:
        exemplo_alternativas = '"alternativas": {"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."}'
        instrucao_gab = '"gabarito": SOMENTE a letra, ex: "D"'

    prompt = f"""
Você é um preparador de concursos especializado.
Sua missão é recuperar e transcrever questões REAIS de provas anteriores da banca {banca_alvo} para o cargo {cargo_alvo}.

CONCURSO ALVO: {concurso}
MATÉRIA: {mat_final} | TEMA: {tema_selecionado}
FORMATO DA BANCA: {formato_principal}

══════════════════════════════════════════════════════════
  CONTEXTO DE PROVAS REAIS ENCONTRADAS
══════════════════════════════════════════════════════════
{contexto_reais[:5000]}

══════════════════════════════════════════════════════════
  INSTRUÇÃO
══════════════════════════════════════════════════════════
Transcreva EXATAMENTE {qtd} questões reais de provas anteriores da banca {banca_alvo} para o cargo {cargo_alvo}.
Se não houver questões reais suficientes no contexto, crie questões no mesmo padrão e nível das provas reais, sinalizando na fonte.

⚠️ {instrucao_gab} — JAMAIS inclua texto adicional no campo gabarito.
⚠️ As questões devem ter nível de dificuldade REAL do concurso {concurso} (nível {nivel}/5).

Responda APENAS com o JSON abaixo:

{{
  "questoes": [
    {{
      "enunciado": "Enunciado completo da questão real ou simulada no mesmo padrão",
      {exemplo_alternativas},
      "gabarito": "A",
      "explicacao": "Gabarito fundamentado com legislação, jurisprudência e doutrina. Mínimo 5 linhas.",
      "comentarios": {{
        "A": "Análise técnica desta alternativa",
        "B": "Análise técnica desta alternativa"
      }},
      "fonte": "{banca_alvo} — {concurso} — Prova Real ou Padrão Real",
      "dificuldade": {nivel},
      "tags": ["{mat_final}", "{tema_selecionado}", "{cargo_alvo}", "prova-real"],
      "formato": "{formato_principal}",
      "eh_real": 1,
      "ano_prova": 2023
    }}
  ]
}}
"""
    return prompt


# =================================================================================
# BARRA LATERAL
# =================================================================================
with st.sidebar:
    st.title("👤 Identificação")
    df_users = pd.read_sql_query("SELECT nome FROM usuarios", conn)
    lista_users = df_users['nome'].tolist()
    usuario_selecionado = st.selectbox("Selecione o Perfil", ["Novo Usuário..."] + lista_users)

    if usuario_selecionado == "Novo Usuário...":
        novo_nome = st.text_input("Digite o Nome/Login:")
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
        st.session_state.usuario_atual = usuario_selecionado

    st.divider()
    st.header("🧠 Motor de IA")
    motor_escolhido = st.radio(
        "Escolha o modelo:",
        ["Groq (Gratuito / Llama 3)", "DeepSeek (Premium / Recomendado)"],
        captions=["Cota diária limitada", "Melhor qualidade de questões"]
    )

    st.divider()
    st.session_state.debug_mode = st.checkbox(
        "🔍 Modo Debug",
        value=False,
        help="Exibe valores brutos de gabarito para diagnóstico"
    )
    st.divider()

    if st.session_state.usuario_atual:
        st.header("📚 Biblioteca de Editais")
        df_editais = pd.read_sql_query(
            "SELECT id, nome_concurso, banca, cargo, dados_json, nivel_dificuldade, nome_concurso_completo "
            "FROM editais_salvos WHERE usuario = ? ORDER BY id DESC",
            conn, params=(st.session_state.usuario_atual,)
        )

        if not df_editais.empty:
            opcoes_editais = ["Selecione um edital..."] + [
                f"{row['nome_concurso']} ({row['cargo']})" for _, row in df_editais.iterrows()
            ]
            escolha = st.selectbox("Carregar Edital Salvo:", opcoes_editais)

            if escolha != "Selecione um edital...":
                idx = opcoes_editais.index(escolha) - 1
                linha = df_editais.iloc[idx]
                perfil_cargo_det = obter_perfil_cargo(linha['cargo'])
                perfil_banca_det = obter_perfil_banca(linha['banca'])
                nome_completo = linha.get('nome_concurso_completo') or linha['nome_concurso']
                st.session_state.edital_ativo = {
                    "nome_concurso": linha['nome_concurso'],
                    "nome_concurso_completo": nome_completo,
                    "banca": linha['banca'],
                    "cargo": linha['cargo'],
                    "materias": json.loads(linha['dados_json'])['materias'],
                    "nivel_dificuldade": perfil_cargo_det["nível"],
                    "formatos": perfil_banca_det["formatos"],
                    "perfil_cargo": perfil_cargo_det,
                }
                st.success(
                    f"✅ **{linha['nome_concurso']}** carregado!\n\n"
                    f"🏢 Banca: **{linha['banca']}** | 🎯 Nível: **{perfil_cargo_det['descrição']}**"
                )
        else:
            st.info("A biblioteca está vazia. Adicione um edital abaixo.")

        st.write("---")
        with st.expander("➕ Cadastrar Novo Edital", expanded=df_editais.empty):
            nome_novo   = st.text_input("Nome curto do Concurso (Ex: PCDF 2024):")
            nome_completo_novo = st.text_input("Nome completo (Ex: Concurso Público PCDF — Delegado de Polícia 2024):")
            banca_nova  = st.text_input("Banca Examinadora (Ex: Cebraspe, FCC, Vunesp):")
            cargo_novo  = st.text_input("Cargo exato do edital (Ex: Delegado de Polícia Civil):")
            texto_colado = st.text_area("Cole o texto completo do Conteúdo Programático:")

            if st.button("💾 Salvar Edital no Perfil", use_container_width=True) and nome_novo and texto_colado:
                with st.spinner("Estruturando matérias e detectando padrões..."):
                    perfil_cargo = obter_perfil_cargo(cargo_novo)
                    perfil_banca = obter_perfil_banca(banca_nova)
                    prompt_edit  = f"""
Leia o conteúdo programático abaixo e extraia APENAS as disciplinas/matérias principais.
Responda SOMENTE com JSON: {{"materias": ["Disciplina 1", "Disciplina 2"]}}.
Texto: {texto_colado[:12000]}
"""
                    try:
                        resp = client_groq.chat.completions.create(
                            messages=[{"role": "user", "content": prompt_edit}],
                            model="llama-3.3-70b-versatile",
                            temperature=0.1,
                            response_format={"type": "json_object"}
                        )
                        texto_json   = resp.choices[0].message.content
                        formatos_json = json.dumps(perfil_banca["formatos"])
                        nome_completo_final = nome_completo_novo or nome_novo

                        c.execute("""
                            INSERT INTO editais_salvos
                            (usuario, nome_concurso, banca, cargo, dados_json, data_analise,
                             nivel_dificuldade, formato_questoes, nome_concurso_completo)
                            VALUES (?,?,?,?,?,?,?,?,?)
                        """, (
                            st.session_state.usuario_atual, nome_novo, banca_nova, cargo_novo,
                            texto_json, str(datetime.now()), perfil_cargo["nível"],
                            formatos_json, nome_completo_final
                        ))
                        conn.commit()
                        st.success(
                            f"✅ Edital salvo!\n"
                            f"Formato: **{perfil_banca['formatos'][0]}** | "
                            f"Nível: **{perfil_cargo['descrição']}**"
                        )
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Erro ao estruturar: {ex}")

        st.divider()
        if st.button("🗑️ Zerar Progresso de Resoluções", use_container_width=True):
            c.execute("DELETE FROM respostas WHERE usuario = ?", (st.session_state.usuario_atual,))
            conn.commit()
            st.session_state.bateria_atual = []
            st.success("Histórico apagado!")
            st.rerun()


# =================================================================================
# TELA PRINCIPAL
# =================================================================================
if not st.session_state.usuario_atual:
    st.title("🔒 Bem-vindo ao Sistema de Alta Performance")
    st.info("Por favor, selecione ou crie um perfil na barra lateral.")
else:
    st.title(f"📚 Plataforma de Alta Performance — {st.session_state.usuario_atual}")
    st.write("---")

    df_resp   = pd.read_sql_query("SELECT * FROM respostas WHERE usuario = ?", conn, params=(st.session_state.usuario_atual,))
    total_resp = len(df_resp)
    acertos   = int(df_resp["acertou"].sum()) if total_resp > 0 else 0
    taxa_acerto = round((acertos / total_resp) * 100, 1) if total_resp > 0 else 0

    colA, colB, colC = st.columns(3)
    with colA: st.markdown(f'<div class="metric-box"><div class="metric-title">Itens Resolvidos</div><div class="metric-value">{total_resp}</div></div>', unsafe_allow_html=True)
    with colB: st.markdown(f'<div class="metric-box"><div class="metric-title">Acertos</div><div class="metric-value">{acertos}</div></div>', unsafe_allow_html=True)
    with colC: st.markdown(f'<div class="metric-box"><div class="metric-title">Aproveitamento</div><div class="metric-value" style="color:{"#28a745" if taxa_acerto>=70 else "#dc3545"};">{taxa_acerto}%</div></div>', unsafe_allow_html=True)

    st.write("<br>", unsafe_allow_html=True)

    with st.container(border=True):
        st.subheader("⚡ Gerar Bateria de Simulado")

        if st.session_state.edital_ativo:
            e = st.session_state.edital_ativo
            banca_alvo  = e['banca']
            cargo_alvo  = e['cargo']
            concurso    = e.get('nome_concurso_completo') or e['nome_concurso']
            nivel_auto  = e.get('nivel_dificuldade', 3)
            perfil_cargo_ativo = e.get('perfil_cargo', obter_perfil_cargo(cargo_alvo))

            st.markdown(
                f"<div class='concurso-box'>"
                f"🎯 <b>CONCURSO ATIVO:</b> {concurso}<br>"
                f"🏢 <b>BANCA:</b> {banca_alvo} &nbsp;|&nbsp; "
                f"👮 <b>CARGO:</b> {cargo_alvo} &nbsp;|&nbsp; "
                f"🔥 <b>NÍVEL:</b> {perfil_cargo_ativo['descrição']}"
                f"</div>",
                unsafe_allow_html=True
            )

            lista_materias = ["Aleatório"] + e['materias']
            c1, c2 = st.columns(2)
            with c1: mat_selecionada  = st.selectbox("Escolha a Matéria", lista_materias)
            with c2: tema_selecionado = st.text_input("Tema específico (ou 'Aleatório')", "Aleatório")
        else:
            st.warning("⚠️ Carregue um edital na barra lateral para habilitar a calibração automática de dificuldade.")
            c1, c2, c3 = st.columns(3)
            with c1: banca_alvo      = st.text_input("Banca", "Cebraspe")
            with c2: cargo_alvo      = st.text_input("Cargo", "Delegado de Polícia Civil")
            with c3: mat_selecionada = st.text_input("Matéria", "Direito Penal")
            concurso       = st.text_input("Nome do Concurso (Ex: PCDF 2024)", "Concurso Público")
            tema_selecionado = st.text_input("Tema específico", "Aleatório")
            nivel_auto = 3
            e = None

        c3col, c4col = st.columns(2)
        with c3col:
            tipo = st.selectbox("Origem do Material", [
                "🧠 Inédita IA (Alta Dificuldade)",
                "🌐 Questões Reais (Provas Anteriores)",
                "📂 Revisão (Banco Local)"
            ])
        with c4col:
            qtd = st.slider("Quantidade de questões", 1, 10, 5)

        usar_web = st.checkbox(
            "🌐 Pesquisa web avançada (jurisprudência + padrão da banca + conteúdo programático)",
            value=True
        )

        if st.button("🚀 Forjar Simulado de Alto Nível", type="primary", use_container_width=True):
            mat_final = (random.choice(e['materias']) if e and mat_selecionada == "Aleatório" else mat_selecionada)
            instrucao_tema = (
                f"Selecione o tema mais cobrado e complexo de {mat_final} para {cargo_alvo}"
                if tema_selecionado.lower() == "aleatório"
                else tema_selecionado
            )

            # ── REVISÃO DO BANCO LOCAL ────────────────────────────────────────
            if "Revisão" in tipo:
                st.info("🔄 Resgatando questões do banco local...")
                c.execute("""
                    SELECT id FROM questoes
                    WHERE (banca LIKE ? OR cargo LIKE ? OR materia LIKE ?)
                    ORDER BY dificuldade DESC, RANDOM() LIMIT ?
                """, (f"%{banca_alvo}%", f"%{cargo_alvo}%", f"%{mat_selecionada}%", qtd))
                encontradas = [row[0] for row in c.fetchall()]
                if encontradas:
                    st.session_state.bateria_atual = encontradas
                    st.rerun()
                else:
                    st.warning("Banco local insuficiente. Gere novas questões primeiro.")

            # ── QUESTÕES INÉDITAS ─────────────────────────────────────────────
            elif "Inédita" in tipo:
                progresso = st.progress(0, text="Iniciando pesquisa avançada...")

                contexto_jurisprudencia = ""
                contexto_padrao = ""
                contexto_conteudo = ""

                if usar_web:
                    progresso.progress(15, text=f"🔍 Buscando jurisprudência de {mat_final} — {instrucao_tema}...")
                    contexto_jurisprudencia = pesquisar_jurisprudencia_avancada(
                        banca_alvo, cargo_alvo, concurso, mat_final, instrucao_tema
                    )

                    progresso.progress(35, text=f"📋 Analisando padrão da banca {banca_alvo} para {cargo_alvo}...")
                    contexto_padrao = pesquisar_padrao_banca_cargo(banca_alvo, cargo_alvo, concurso)

                    progresso.progress(55, text=f"📚 Levantando conteúdo programático específico do {concurso}...")
                    contexto_conteudo = pesquisar_conteudo_programatico_especifico(cargo_alvo, concurso, mat_final)
                else:
                    contexto_jurisprudencia = f"Usar jurisprudência consolidada de {mat_final} para {cargo_alvo}"
                    contexto_padrao = f"Usar padrão histórico conhecido da banca {banca_alvo}"
                    contexto_conteudo = f"Usar conteúdo programático padrão de {cargo_alvo}"

                prompt = gerar_prompt_questoes_ineditas(
                    qtd, banca_alvo, cargo_alvo, concurso, mat_final, instrucao_tema,
                    contexto_jurisprudencia, contexto_padrao, contexto_conteudo
                )

                progresso.progress(70, text=f"🤖 Gerando {qtd} questões de alto nível com IA...")
                try:
                    if "Groq" in motor_escolhido:
                        resposta = client_groq.chat.completions.create(
                            messages=[
                                {"role": "system", "content": "Você é um elaborador de questões de concursos públicos de alto nível. Gera APENAS JSON válido, sem markdown."},
                                {"role": "user", "content": prompt}
                            ],
                            model="llama-3.3-70b-versatile",
                            temperature=0.6,
                            response_format={"type": "json_object"},
                            max_tokens=6000
                        )
                    else:
                        resposta = client_deepseek.chat.completions.create(
                            messages=[
                                {"role": "system", "content": "Você é um elaborador de questões de concursos públicos de alto nível. Gera APENAS JSON válido, sem markdown."},
                                {"role": "user", "content": prompt}
                            ],
                            model="deepseek-chat",
                            temperature=0.6,
                            response_format={"type": "json_object"},
                            max_tokens=6000
                        )

                    progresso.progress(90, text="💾 Salvando questões no banco...")
                    dados_json   = json.loads(resposta.choices[0].message.content.replace("```json","").replace("```","").strip())
                    lista_questoes = dados_json.get("questoes", [])
                    if not lista_questoes and isinstance(dados_json, list):
                        lista_questoes = dados_json

                    novas_ids = []
                    duplicatas = 0
                    for dados in lista_questoes:
                        enunciado = dados.get("enunciado", "N/A")
                        gabarito  = normalizar_gabarito(dados.get("gabarito", "N/A"))
                        if questao_ja_existe(enunciado, gabarito):
                            duplicatas += 1
                            continue

                        alternativas    = json.dumps(dados.get("alternativas", {}))
                        explicacao_final = json.dumps({
                            "geral": dados.get("explicacao", "N/A"),
                            "detalhes": dados.get("comentarios", {})
                        })
                        c.execute("""
                            INSERT INTO questoes
                            (banca, cargo, materia, tema, enunciado, alternativas, gabarito, explicacao, tipo, fonte,
                             dificuldade, tags, formato_questao, eh_real, hash_questao)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            banca_alvo, cargo_alvo, mat_final, tema_selecionado, enunciado, alternativas,
                            gabarito, explicacao_final, tipo,
                            dados.get("fonte", f"Inédita IA — {banca_alvo} — {cargo_alvo}"),
                            dados.get("dificuldade", nivel_auto),
                            json.dumps(dados.get("tags", [])),
                            dados.get("formato", "Múltipla Escolha"),
                            0, gerar_hash_questao(enunciado, gabarito)
                        ))
                        novas_ids.append(c.lastrowid)

                    conn.commit()
                    st.session_state.bateria_atual = novas_ids
                    progresso.progress(100, text="✅ Concluído!")
                    if duplicatas:
                        st.warning(f"⚠️ {duplicatas} questões duplicadas descartadas.")
                    st.success(f"✅ {len(novas_ids)} questões de alto nível geradas para {concurso}!")
                    st.rerun()

                except Exception as err:
                    progresso.empty()
                    if "rate_limit" in str(err).lower() or "429" in str(err):
                        st.error("⚠️ Limite do Groq atingido. Use **DeepSeek** ou aguarde.")
                    else:
                        st.error(f"❌ Erro na geração: {err}")

            # ── QUESTÕES REAIS ────────────────────────────────────────────────
            else:
                progresso = st.progress(0, text="🔍 Buscando provas anteriores...")

                contexto_reais = ""
                if usar_web:
                    progresso.progress(30, text=f"📂 Pesquisando questões reais de {concurso}...")
                    contexto_reais = pesquisar_questoes_reais_banca(
                        banca_alvo, cargo_alvo, concurso, mat_final, instrucao_tema, qtd
                    )
                else:
                    contexto_reais = "Reconstituir com base em memória de provas conhecidas"

                prompt = gerar_prompt_questoes_reais(
                    qtd, banca_alvo, cargo_alvo, concurso, mat_final, instrucao_tema, contexto_reais
                )

                progresso.progress(60, text=f"🤖 Processando {qtd} questões reais...")
                try:
                    if "Groq" in motor_escolhido:
                        resposta = client_groq.chat.completions.create(
                            messages=[
                                {"role": "system", "content": "Você é um especialista em concursos públicos. Gera APENAS JSON válido, sem markdown."},
                                {"role": "user", "content": prompt}
                            ],
                            model="llama-3.3-70b-versatile",
                            temperature=0.1,
                            response_format={"type": "json_object"},
                            max_tokens=6000
                        )
                    else:
                        resposta = client_deepseek.chat.completions.create(
                            messages=[
                                {"role": "system", "content": "Você é um especialista em concursos públicos. Gera APENAS JSON válido, sem markdown."},
                                {"role": "user", "content": prompt}
                            ],
                            model="deepseek-chat",
                            temperature=0.1,
                            response_format={"type": "json_object"},
                            max_tokens=6000
                        )

                    progresso.progress(85, text="💾 Salvando...")
                    dados_json   = json.loads(resposta.choices[0].message.content.replace("```json","").replace("```","").strip())
                    lista_questoes = dados_json.get("questoes", [])
                    if not lista_questoes and isinstance(dados_json, list):
                        lista_questoes = dados_json

                    novas_ids = []
                    duplicatas = 0
                    for dados in lista_questoes:
                        enunciado = dados.get("enunciado", "N/A")
                        gabarito  = normalizar_gabarito(dados.get("gabarito", "N/A"))
                        if questao_ja_existe(enunciado, gabarito):
                            duplicatas += 1
                            continue

                        alternativas     = json.dumps(dados.get("alternativas", {}))
                        explicacao_final = json.dumps({
                            "geral": dados.get("explicacao", "N/A"),
                            "detalhes": dados.get("comentarios", {})
                        })
                        c.execute("""
                            INSERT INTO questoes
                            (banca, cargo, materia, tema, enunciado, alternativas, gabarito, explicacao, tipo, fonte,
                             dificuldade, tags, formato_questao, eh_real, ano_prova, hash_questao)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            banca_alvo, cargo_alvo, mat_final, tema_selecionado, enunciado, alternativas,
                            gabarito, explicacao_final, tipo,
                            dados.get("fonte", f"Prova Real — {banca_alvo} — {concurso}"),
                            dados.get("dificuldade", nivel_auto),
                            json.dumps(dados.get("tags", [])),
                            dados.get("formato", "Múltipla Escolha"),
                            1, dados.get("ano_prova", 0),
                            gerar_hash_questao(enunciado, gabarito)
                        ))
                        novas_ids.append(c.lastrowid)

                    conn.commit()
                    st.session_state.bateria_atual = novas_ids
                    progresso.progress(100, text="✅ Concluído!")
                    if duplicatas:
                        st.info(f"ℹ️ {duplicatas} questões já estavam no banco.")
                    st.success(f"✅ {len(novas_ids)} questões carregadas de provas reais de {concurso}!")
                    st.rerun()

                except Exception as err:
                    progresso.empty()
                    if "rate_limit" in str(err).lower() or "429" in str(err):
                        st.error("⚠️ Limite do Groq atingido. Use **DeepSeek** ou aguarde.")
                    else:
                        st.error(f"❌ Erro: {err}")

    # =================================================================================
    # CADERNO DE PROVA
    # =================================================================================
    if st.session_state.bateria_atual:
        st.write("---")
        st.subheader("🎯 Caderno de Prova")

        ids_str = ','.join(map(str, st.session_state.bateria_atual))
        df_respostas = pd.read_sql_query(
            f"SELECT questao_id, resposta_usuario, acertou FROM respostas "
            f"WHERE usuario = '{st.session_state.usuario_atual}' AND questao_id IN ({ids_str})",
            conn
        )
        respondidas = df_respostas.set_index('questao_id').to_dict('index')

        for i, q_id in enumerate(st.session_state.bateria_atual):
            c.execute(
                "SELECT banca, cargo, materia, enunciado, alternativas, gabarito, explicacao, "
                "fonte, dificuldade, tags, formato_questao, eh_real FROM questoes WHERE id = ?",
                (q_id,)
            )
            dados = c.fetchone()
            if not dados:
                continue

            q_banca, q_cargo, q_mat, q_enun, q_alt, q_gab, q_exp, q_fonte, q_dif, q_tags, q_formato, eh_real = dados
            alts      = json.loads(q_alt)  if q_alt  else {}
            tags_list = json.loads(q_tags) if q_tags else []

            q_gab_norm    = normalizar_gabarito(q_gab)
            is_certo_errado = "Certo/Errado" in (q_formato or "")

            dif_idx   = min(max((q_dif or 3) - 1, 0), 4)
            dif_label = ["Muito Fácil", "Fácil", "Médio", "Difícil", "Muito Difícil"][dif_idx]
            dif_classe = "dif-facil" if (q_dif or 3) <= 2 else ("dif-medio" if (q_dif or 3) == 3 else "dif-dificil")
            tipo_questao = "Prova Real" if eh_real else "Inédita IA"
            tipo_classe  = "tipo-real"  if eh_real else "tipo-inedita"

            try:
                exp_data = json.loads(q_exp)
                exp_geral    = exp_data.get("geral", q_exp) if isinstance(exp_data, dict) else q_exp
                exp_detalhes = exp_data.get("detalhes", {}) if isinstance(exp_data, dict) else {}
            except:
                exp_geral    = q_exp
                exp_detalhes = {}

            if is_certo_errado:
                opcoes = ["Selecionar...", "Certo", "Errado"]
            else:
                opcoes = (["Selecionar..."] + [f"{k}) {v}" for k, v in alts.items()]) if alts else ["Selecionar...", "A", "B", "C", "D", "E"]

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

                # ── JÁ RESPONDIDA ──────────────────────────────────────────────
                if q_id in respondidas:
                    status = respondidas[q_id]
                    resp_salva = normalizar_gabarito(str(status['resposta_usuario']))

                    if st.session_state.debug_mode:
                        st.markdown(
                            f"<div class='debug-box'>🔎 <b>DEBUG</b> | "
                            f"Gabarito banco: <code>{q_gab!r}</code> → norm: <code>{q_gab_norm!r}</code> | "
                            f"Resposta salva: <code>{status['resposta_usuario']!r}</code> → norm: <code>{resp_salva!r}</code> | "
                            f"Iguais: <code>{resp_salva == q_gab_norm}</code> | "
                            f"acertou: <code>{status['acertou']}</code></div>",
                            unsafe_allow_html=True
                        )

                    st.markdown("<br><b>Análise das Alternativas:</b>", unsafe_allow_html=True)
                    for opcao in opcoes[1:]:
                        letra_opcao = extrair_letra_opcao(opcao, not is_certo_errado)
                        is_usuario  = (letra_opcao == resp_salva)
                        is_gabarito = (letra_opcao == q_gab_norm)

                        if is_usuario:
                            css = "alt-correta" if status['acertou'] == 1 else "alt-errada"
                            icon = "✅" if status['acertou'] == 1 else "❌"
                            label = "(Sua Resposta Correta)" if status['acertou'] == 1 else "(Sua Resposta Incorreta)"
                            st.markdown(f"<div class='{css}'>{icon} <b>{opcao}</b> {label}</div>", unsafe_allow_html=True)
                        elif is_gabarito and status['acertou'] == 0:
                            st.markdown(f"<div class='alt-gabarito'>🎯 <b>{opcao}</b> (Gabarito Oficial)</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<div class='alt-neutra'>{opcao}</div>", unsafe_allow_html=True)

                        if not is_certo_errado and letra_opcao in exp_detalhes and exp_detalhes[letra_opcao]:
                            st.markdown(f"<div class='comentario-alt'>💡 <b>Por que?</b> {exp_detalhes[letra_opcao]}</div>", unsafe_allow_html=True)

                    with st.expander("📖 Fundamentação Legal Completa"):
                        st.write(exp_geral)

                # ── AINDA NÃO RESPONDIDA ───────────────────────────────────────
                else:
                    if st.session_state.debug_mode:
                        st.markdown(
                            f"<div class='debug-box'>🔎 <b>DEBUG</b> | "
                            f"Gabarito banco: <code>{q_gab!r}</code> → norm esperado: <code>{q_gab_norm!r}</code></div>",
                            unsafe_allow_html=True
                        )

                    resp = st.radio("Sua Resposta:", opcoes, key=f"rad_{q_id}", label_visibility="collapsed")
                    if st.button("✅ Confirmar Resposta", key=f"btn_{q_id}"):
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
