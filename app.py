import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import json
import random
from groq import Groq
from openai import OpenAI
from duckduckgo_search import DDGS

# ================= CONFIGURAÇÃO VISUAL =================
st.set_page_config(page_title="Plataforma de Alta Performance", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .metric-box { background-color: #f8f9fa; border-radius: 10px; padding: 20px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #e9ecef; }
    .metric-title { font-size: 14px; color: #6c757d; font-weight: 600; text-transform: uppercase; }
    .metric-value { font-size: 32px; font-weight: 700; color: #212529; margin-top: 5px; }
    .stRadio > div { flex-direction: row; gap: 15px; }
    .alt-correta { padding: 10px; background-color: #d4edda; border-left: 5px solid #28a745; border-radius: 5px; margin-bottom: 2px; }
    .alt-errada { padding: 10px; background-color: #f8d7da; border-left: 5px solid #dc3545; border-radius: 5px; margin-bottom: 2px; }
    .alt-neutra { padding: 10px; border-left: 5px solid #e9ecef; margin-bottom: 2px; color: #495057; }
    .alt-gabarito { padding: 10px; background-color: #cce5ff; border-left: 5px solid #004085; border-radius: 5px; margin-bottom: 2px; font-weight: bold; }
    .comentario-alt { font-size: 0.9em; color: #555; margin-left: 15px; margin-bottom: 12px; border-left: 2px solid #ccc; padding-left: 10px; background-color: #fdfdfd; padding-top: 5px; padding-bottom: 5px;}
    .dificuldade-badge { display: inline-block; padding: 5px 12px; border-radius: 20px; font-weight: 600; font-size: 12px; }
    .dif-facil { background-color: #d4edda; color: #155724; }
    .dif-medio { background-color: #fff3cd; color: #856404; }
    .dif-dificil { background-color: #f8d7da; color: #721c24; }
    .banca-info { background-color: #e7f3ff; border-left: 4px solid #0066cc; padding: 12px; border-radius: 5px; margin-bottom: 15px; }
    </style>
""", unsafe_allow_html=True)

# ================= PERFIL DETALHADO DE BANCAS =================
PERFIL_BANCAS = {
    "Cebraspe": {
        "formatos": ["Certo/Errado"],
        "caracteristicas": ["questões assertivas", "análise de jurisprudência", "interpretação de normas", "pegadinhas sutis"],
        "quantidade_alternativas": 2,
        "estilo_enunciado": "objetivo e direto",
        "dificuldade_base": 4,
        "sites_busca": ["cebraspe.com.br", "tecconcursos.com.br", "qconcursos.com"],
        "exemplo": "Para a banca CEBRASPE, use apenas Certo ou Errado. Questões assertivas com jurisprudência consolidada."
    },
    "FCC": {
        "formatos": ["Múltipla Escolha (A a E)"],
        "caracteristicas": ["análise gramatical", "interpretação textual", "conceitos definidos", "raciocínio lógico"],
        "quantidade_alternativas": 5,
        "estilo_enunciado": "contextualizado e descritivo",
        "dificuldade_base": 3,
        "sites_busca": ["fcc.org.br", "tecconcursos.com.br", "qconcursos.com"],
        "exemplo": "Para a banca FCC, use 5 alternativas (A a E). Questões com análise contextual e raciocínio lógico."
    },
    "Vunesp": {
        "formatos": ["Múltipla Escolha (A a E)"],
        "caracteristicas": ["análise crítica", "jurisprudência recente", "aplicação prática", "casos reais"],
        "quantidade_alternativas": 5,
        "estilo_enunciado": "descritivo com contexto",
        "dificuldade_base": 3,
        "sites_busca": ["vunesp.com.br", "tecconcursos.com.br", "qconcursos.com"],
        "exemplo": "Para a banca VUNESP, use 5 alternativas (A a E). Questões com análise crítica e aplicação prática."
    },
    "OAB": {
        "formatos": ["Múltipla Escolha (A a E)"],
        "caracteristicas": ["jurisprudência obrigatória", "súmulas do STF", "código de ética", "princípios fundamentais"],
        "quantidade_alternativas": 5,
        "estilo_enunciado": "preciso e técnico",
        "dificuldade_base": 4,
        "sites_busca": ["oab.org.br", "tecconcursos.com.br", "qconcursos.com"],
        "exemplo": "Para a banca OAB, use 5 alternativas (A a E). Questões baseadas em jurisprudência e códigos éticos."
    },
    "ESAF": {
        "formatos": ["Múltipla Escolha (A a E)"],
        "caracteristicas": ["precisão conceitual", "legislação fiscal", "contabilidade pública", "administração"],
        "quantidade_alternativas": 5,
        "estilo_enunciado": "técnico e objetivo",
        "dificuldade_base": 4,
        "sites_busca": ["esaf.org.br", "tecconcursos.com.br", "qconcursos.com"],
        "exemplo": "Para a banca ESAF, use 5 alternativas (A a E). Questões com precisão conceitual e legislação específica."
    },
    "IADES": {
        "formatos": ["Múltipla Escolha (A a E)"],
        "caracteristicas": ["conceitos aplicados", "análise comparativa", "legislação específica", "raciocínio crítico"],
        "quantidade_alternativas": 5,
        "estilo_enunciado": "contextualizado",
        "dificuldade_base": 3,
        "sites_busca": ["iades.org.br", "tecconcursos.com.br", "qconcursos.com"],
        "exemplo": "Para a banca IADES, use 5 alternativas (A a E). Questões com análise comparativa e aplicação prática."
    },
    "UFF": {
        "formatos": ["Múltipla Escolha (A a D)"],
        "caracteristicas": ["conceitos fundamentais", "legislação básica", "aplicação simples", "interpretação direta"],
        "quantidade_alternativas": 4,
        "estilo_enunciado": "direto e simples",
        "dificuldade_base": 2,
        "sites_busca": ["uff.br", "tecconcursos.com.br", "qconcursos.com"],
        "exemplo": "Para a banca UFF, use 4 alternativas (A a D). Questões com conceitos fundamentais e aplicação simples."
    },
    "UFPR": {
        "formatos": ["Múltipla Escolha (A a E)"],
        "caracteristicas": ["análise profunda", "jurisprudência consolidada", "interpretação doutrinária"],
        "quantidade_alternativas": 5,
        "estilo_enunciado": "aprofundado",
        "dificuldade_base": 4,
        "sites_busca": ["ufpr.br", "tecconcursos.com.br", "qconcursos.com"],
        "exemplo": "Para a banca UFPR, use 5 alternativas (A a E). Questões com análise profunda e jurisprudência consolidada."
    },
    "Defesa": {
        "formatos": ["Múltipla Escolha (A a E)"],
        "caracteristicas": ["legislação militar", "hierarquia", "procedimentos operacionais", "regulamentos específicos"],
        "quantidade_alternativas": 5,
        "estilo_enunciado": "técnico militar",
        "dificuldade_base": 3,
        "sites_busca": ["defesa.gov.br", "tecconcursos.com.br", "qconcursos.com"],
        "exemplo": "Para a banca Defesa, use 5 alternativas (A a E). Questões com legislação militar e procedimentos operacionais."
    },
    "Aeronáutica": {
        "formatos": ["Múltipla Escolha (A a E)"],
        "caracteristicas": ["segurança aérea", "legislação específica", "procedimentos técnicos", "regulamentações FAB"],
        "quantidade_alternativas": 5,
        "estilo_enunciado": "técnico e específico",
        "dificuldade_base": 4,
        "sites_busca": ["fab.mil.br", "tecconcursos.com.br", "qconcursos.com"],
        "exemplo": "Para a banca Aeronáutica, use 5 alternativas (A a E). Questões sobre segurança aérea e regulamentações."
    },
}

# ================= MAPEAMENTO DE DIFICULDADE POR CARGO =================
PERFIL_CARGO_DIFICULDADE = {
    "Juiz": {"nível": 5, "descrição": "Muito Difícil", "características": ["jurisprudência complexa", "precedentes conflitantes", "interpretação doutrinária", "casos reais polêmicos"]},
    "Procurador da República": {"nível": 5, "descrição": "Muito Difícil", "características": ["conhecimento aprofundado", "jurisprudência recente", "constitucionalismo", "ADIN/ADC"]},
    "Procurador": {"nível": 5, "descrição": "Muito Difícil", "características": ["conhecimento aprofundado", "jurisprudência recente", "constitucionalismo"]},
    "Juiz de Direito": {"nível": 5, "descrição": "Muito Difícil", "características": ["jurisprudência consolidada", "súmulas e precedentes", "casos jurisprudenciais reais"]},
    "Delegado de Polícia": {"nível": 4, "descrição": "Difícil", "características": ["processual penal", "direitos humanos", "procedimentos investigativos", "jurisprudência aplicada"]},
    "Delegado da PF": {"nível": 4, "descrição": "Difícil", "características": ["criminalística", "direito penal econômico", "legislação federal"]},
    "Delegado": {"nível": 4, "descrição": "Difícil", "características": ["processual penal", "legislação aplicada"]},
    "Analista": {"nível": 3, "descrição": "Médio", "características": ["conceitos bem definidos", "legislação objetiva", "procedimentos padrão"]},
    "Assistente": {"nível": 2, "descrição": "Fácil a Médio", "características": ["conceitos básicos", "operações simples", "legislação clara"]},
    "Oficial": {"nível": 2, "descrição": "Fácil a Médio", "características": ["procedimentos operacionais", "legislação direta"]},
    "Policial": {"nível": 2, "descrição": "Fácil a Médio", "características": ["procedimentos práticos", "legislação funcional"]},
    "Investigador": {"nível": 3, "descrição": "Médio", "características": ["técnicas de investigação", "legislação processual"]},
    "Auditor": {"nível": 4, "descrição": "Difícil", "características": ["contabilidade aplicada", "legislação tributária", "auditoria"]},
}

# ================= CHAVES DE IA =================
try:
    client_groq = Groq(api_key=st.secrets["GROQ_API_KEY"])
    client_deepseek = OpenAI(api_key=st.secrets["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
except Exception as e:
    st.error("Erro ao carregar as chaves de API. Verifique os Segredos no Streamlit.")

# ================= AGENTE DE BUSCA AVANÇADO =================
def pesquisar_questoes_banca(banca, cargo, materia, tema):
    """Busca otimizada por banca e cargo com foco em padrão de questões."""
    try:
        ddgs = DDGS()
        
        perfil_banca = PERFIL_BANCAS.get(banca, {})
        sites = perfil_banca.get("sites_busca", ["tecconcursos.com.br", "qconcursos.com"])
        
        # Constrói query específica para a banca
        sites_str = " OR ".join([f"site:{site}" for site in sites])
        query_otimizada = f'"{banca}" "{cargo}" "{materia}" "{tema}" ({sites_str})'
        
        resultados = ddgs.text(query_otimizada, max_results=8)
        contexto = "\n".join([f"- {r['body']}" for r in resultados])
        
        return contexto[:8000] if contexto else "Dados insuficientes na busca."
    except Exception as e:
        return "Busca indisponível. Use memória consolidada."

def pesquisar_jurisprudencia_banca(banca, cargo, materia):
    """Busca jurisprudência específica da banca."""
    try:
        ddgs = DDGS()
        
        query = f'jurisprudência "{banca}" "{cargo}" "{materia}" STF STJ (site:stf.jus.br OR site:stj.jus.br OR site:tecconcursos.com.br)'
        resultados = ddgs.text(query, max_results=6)
        contexto = "\n".join([f"- {r['body']}" for r in resultados])
        
        return contexto[:8000] if contexto else "Jurisprudência insuficiente."
    except Exception as e:
        return "Busca de jurisprudência indisponível."

def pesquisar_estilo_questoes_banca(banca):
    """Busca exemplos do estilo específico da banca."""
    try:
        ddgs = DDGS()
        
        query = f'exemplo questões "{banca}" estilo padrão formato (site:tecconcursos.com.br OR site:qconcursos.com OR site:youtube.com)'
        resultados = ddgs.text(query, max_results=5)
        contexto = "\n".join([f"- {r['body']}" for r in resultados])
        
        return contexto[:5000] if contexto else "Exemplos insuficientes."
    except Exception as e:
        return "Busca de estilo indisponível."

# ================= MIGRAÇÃO DO BANCO DE DADOS =================
def migrar_banco_de_dados(conn):
    """Adiciona colunas faltantes ao banco de dados existente."""
    c = conn.cursor()
    
    try:
        c.execute("ALTER TABLE editais_salvos ADD COLUMN nivel_dificuldade INTEGER DEFAULT 3")
        conn.commit()
    except:
        pass
    
    try:
        c.execute("ALTER TABLE editais_salvos ADD COLUMN formato_questoes TEXT DEFAULT '[]'")
        conn.commit()
    except:
        pass
    
    try:
        c.execute("ALTER TABLE questoes ADD COLUMN dificuldade INTEGER DEFAULT 3")
        conn.commit()
    except:
        pass
    
    try:
        c.execute("ALTER TABLE questoes ADD COLUMN tags TEXT DEFAULT '[]'")
        conn.commit()
    except:
        pass
    
    try:
        c.execute("ALTER TABLE questoes ADD COLUMN formato_questao TEXT DEFAULT 'Múltipla Escolha'")
        conn.commit()
    except:
        pass
    
    try:
        c.execute("ALTER TABLE respostas ADD COLUMN tempo_resposta INTEGER DEFAULT 0")
        conn.commit()
    except:
        pass

# ================= BANCO DE DADOS =================
@st.cache_resource
def iniciar_conexao():
    conn = sqlite3.connect("estudos_multi_user.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS usuarios (nome TEXT PRIMARY KEY)""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS questoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        banca TEXT, cargo TEXT, materia TEXT, tema TEXT,
        enunciado TEXT, alternativas TEXT, gabarito TEXT,
        explicacao TEXT, tipo TEXT, fonte TEXT,
        dificuldade INTEGER DEFAULT 3, tags TEXT DEFAULT '[]',
        formato_questao TEXT DEFAULT 'Múltipla Escolha'
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS respostas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT, questao_id INTEGER, resposta_usuario TEXT,
        acertou INTEGER, data TEXT, tempo_resposta INTEGER DEFAULT 0
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS editais_salvos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT, nome_concurso TEXT, banca TEXT, cargo TEXT,
        dados_json TEXT, data_analise TEXT, nivel_dificuldade INTEGER DEFAULT 3,
        formato_questoes TEXT DEFAULT '[]'
    )
    """)
    conn.commit()
    return conn

conn = iniciar_conexao()
migrar_banco_de_dados(conn)
c = conn.cursor()

# ================= INICIALIZAÇÃO DE MEMÓRIA =================
if "usuario_atual" not in st.session_state: st.session_state.usuario_atual = None
if "bateria_atual" not in st.session_state: st.session_state.bateria_atual = []
if "edital_ativo" not in st.session_state: st.session_state.edital_ativo = None

# ================= FUNÇÕES AUXILIARES =================
def obter_perfil_cargo(cargo_nome):
    """Retorna o perfil de dificuldade para um cargo."""
    for chave, valor in PERFIL_CARGO_DIFICULDADE.items():
        if chave.lower() in cargo_nome.lower() or cargo_nome.lower() in chave.lower():
            return valor
    return {"nível": 3, "descrição": "Médio", "características": ["Padrão"]}

def obter_perfil_banca(banca_nome):
    """Retorna o perfil detalhado da banca."""
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
        "exemplo": "Formato padrão com 5 alternativas."
    }

def gerar_prompt_com_banca_e_dificuldade(qtd, banca_alvo, cargo_alvo, mat_final, tema_selecionado, 
                                          tipo, contexto_questoes, contexto_jurisprudencia, contexto_estilo):
    """Gera prompt customizado por banca e cargo."""
    
    perfil_banca = obter_perfil_banca(banca_alvo)
    perfil_cargo = obter_perfil_cargo(cargo_alvo)
    
    nivel_dif = perfil_cargo["nível"]
    descricao_dif = perfil_cargo["descrição"]
    formatos_banca = perfil_banca["formatos"]
    caracteristicas_banca = ", ".join(perfil_banca["caracteristicas"])
    formato_principal = formatos_banca[0]
    qtd_alternativas = perfil_banca["quantidade_alternativas"]
    estilo_enunciado = perfil_banca["estilo_enunciado"]
    
    # Monta instruções específicas por formato
    if "Certo/Errado" in formato_principal:
        instrucao_formato = f"""
        FORMATO OBRIGATÓRIO: Certo/Errado (Padrão da {banca_alvo})
        - Cada questão deve ter uma assertiva clara
        - Gabarito: "Certo" ou "Errado"
        - Sem alternativas A, B, C, D, E
        - Estilo: {estilo_enunciado}
        
        ALTERNATIVAS PARA ANÁLISE (não usar em JSON, apenas explicação):
        {{
          "assertiva": "A assertiva será apresentada como texto",
          "verdadeira_ou_falsa": "Indicar se é verdadeira ou falsa",
          "explicacao_por_que": "Explicar por que está certa ou errada"
        }}
        """
        regras_json_alt = '"alternativas": {}'
    elif "A a D" in formato_principal:
        instrucao_formato = f"""
        FORMATO OBRIGATÓRIO: Múltipla Escolha com 4 alternativas (A, B, C, D)
        - Banca {banca_alvo} usa exatamente 4 opções
        - Estilo: {estilo_enunciado}
        """
        regras_json_alt = '"alternativas": {"A": "...", "B": "...", "C": "...", "D": "..."}'
    else:
        instrucao_formato = f"""
        FORMATO OBRIGATÓRIO: Múltipla Escolha com 5 alternativas (A, B, C, D, E)
        - Banca {banca_alvo} usa exatamente 5 opções
        - Estilo: {estilo_enunciado}
        """
        regras_json_alt = '"alternativas": {"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."}'
    
    instrucao_ia = f"""
    Crie questões INÉDITAS que MIMETIZEM EXATAMENTE o padrão da banca {banca_alvo} para o cargo de {cargo_alvo}.
    
    CONTEXTO DA BANCA: {caracteristicas_banca}
    EXEMPLOS DO ESTILO DA BANCA:
    {contexto_estilo[:2000]}
    
    NÍVEL DE DIFICULDADE: {descricao_dif} (Nível {nivel_dif}/5)
    
    Diretivas de Complexidade:
    - Para NÍVEL 4-5 (Juiz/Procurador/Delegado): Use jurisprudência complexa, precedentes conflitantes, pegadinhas sutis
    - Para NÍVEL 3 (Analista/Investigador): Use conceitos bem definidos, legislação objetiva
    - Para NÍVEL 1-2 (Policial/Assistente): Use procedimentos diretos, legislação clara
    
    JURISPRUDÊNCIA E LEGISLAÇÃO APLICÁVEL:
    {contexto_jurisprudencia[:3000]}
    
    QUESTÕES SIMILARES DA BANCA:
    {contexto_questoes[:3000]}
    """
    
    prompt = f"""
    PROTOCOLO DE GERAÇÃO DE QUESTÕES - MÁXIMA FIDELIDADE À BANCA
    
    {instrucao_ia}
    
    MISSÃO: Entregue {qtd} questão(ões) com dificuldade {descricao_dif} no formato exato da {banca_alvo}.
    Matéria: {mat_final} | Tema: {tema_selecionado}
    
    {instrucao_formato}
    
    DIRETRIZES IMPERATIVAS:
    1. FIDELIDADE AO ESTILO: Copie exatamente o padrão de questões da {banca_alvo}
    2. BASE JURÍDICA: Gabarito fundamentado em jurisprudência consolidada e legislação vigente
    3. ANATOMIA DO ERRO: SEMPRE explique por que CADA alternativa está certa/errada
    4. ALTERNATIVAS PLAUSÍVEIS: Todas devem parecer corretas a quem não estudou o tema
    5. VALIDAÇÃO: Esta questão é realmente do nível {descricao_dif}? Está no formato {formato_principal}?
    
    JSON EXATO (IMPERATIVO):
    {{
      "questoes": [
        {{
          "enunciado": "Texto claro no estilo {estilo_enunciado} da {banca_alvo}",
          {regras_json_alt},
          "gabarito": "Resposta única correta",
          "explicacao": "Fundamentação legal e jurisprudencial completa",
          "comentarios": {{"A": "Por que está certa/errada", "B": "Por que está certa/errada", "C": "Por que está certa/errada"}},
          "fonte": "Inédita IA - Estilo {banca_alvo} - {descricao_dif}",
          "dificuldade": {nivel_dif},
          "tags": ["jurisprudência", "legislação", "{cargo_alvo}"],
          "formato": "{formato_principal}"
        }}
      ]
    }}
    """
    
    return prompt

# ================= BARRA LATERAL =================
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

    st.header("🧠 Motor de Inteligência")
    motor_escolhido = st.radio(
        "Escolha a IA para gerar as questões:",
        ["Groq (Gratuito / Llama 3)", "DeepSeek (Premium / Custo Otimizado)"],
        captions=["Cota diária limitada", "Ilimitado sob demanda"]
    )
    st.divider()

    if st.session_state.usuario_atual:
        st.header("📚 Biblioteca de Editais")
        df_editais = pd.read_sql_query("SELECT id, nome_concurso, banca, cargo, dados_json, nivel_dificuldade FROM editais_salvos WHERE usuario = ? ORDER BY id DESC", conn, params=(st.session_state.usuario_atual,))
        
        if not df_editais.empty:
            opcoes_editais = ["Selecione um edital..."] + [f"{row['nome_concurso']} ({row['cargo']})" for _, row in df_editais.iterrows()]
            escolha = st.selectbox("Carregar Edital Salvo:", opcoes_editais)
            
            if escolha != "Selecione um edital...":
                idx_selecionado = opcoes_editais.index(escolha) - 1
                linha_selecionada = df_editais.iloc[idx_selecionado]
                perfil_cargo_detectado = obter_perfil_cargo(linha_selecionada['cargo'])
                perfil_banca_detectada = obter_perfil_banca(linha_selecionada['banca'])
                st.session_state.edital_ativo = {
                    "nome_concurso": linha_selecionada['nome_concurso'],
                    "banca": linha_selecionada['banca'],
                    "cargo": linha_selecionada['cargo'],
                    "materias": json.loads(linha_selecionada['dados_json'])['materias'],
                    "nivel_dificuldade": perfil_cargo_detectado["nível"],
                    "formatos": perfil_banca_detectada["formatos"]
                }
                st.success(f"✅ Edital carregado! Banca: {linha_selecionada['banca']} | Nível: {perfil_cargo_detectado['descrição']}")
        else:
            st.info("A biblioteca está vazia. Adicione um edital abaixo.")

        st.write("---")
        with st.expander("➕ Cadastrar Novo Edital", expanded=True if df_editais.empty else False):
            nome_novo = st.text_input("Nome do Concurso (Ex: PCDF):")
            banca_nova = st.text_input("Banca Examinadora (Ex: Cebraspe, FCC, Vunesp):")
            cargo_novo = st.text_input("Cargo:")
            texto_colado = st.text_area("Cole o texto do Conteúdo Programático:")

            if st.button("Salvar Edital no Perfil", use_container_width=True) and nome_novo and texto_colado:
                with st.spinner("Estruturando matérias e detectando formato da banca..."):
                    perfil_cargo = obter_perfil_cargo(cargo_novo)
                    perfil_banca = obter_perfil_banca(banca_nova)
                    
                    prompt = f"""
                    Leia o texto abaixo e liste APENAS as disciplinas/matérias. 
                    Responda em JSON: {{"materias": ["Disc 1", "Disc 2"]}}.
                    Texto: {texto_colado[:10000]}
                    """
                    try:
                        resposta = client_groq.chat.completions.create(
                            messages=[{"role": "user", "content": prompt}],
                            model="llama-3.3-70b-versatile",
                            temperature=0.1,
                            response_format={"type": "json_object"}
                        )
                        texto_json = resposta.choices[0].message.content
                        formatos_json = json.dumps(perfil_banca["formatos"])
                        
                        c.execute("""
                        INSERT INTO editais_salvos (usuario, nome_concurso, banca, cargo, dados_json, data_analise, nivel_dificuldade, formato_questoes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (st.session_state.usuario_atual, nome_novo, banca_nova, cargo_novo, texto_json, str(datetime.now()), perfil_cargo["nível"], formatos_json))
                        conn.commit()
                        st.success(f"✅ Edital salvo! Formato detectado: {perfil_banca['formatos'][0]}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao estruturar: {e}")

        st.divider()
        if st.button("Zerar Progresso de Resoluções", use_container_width=True):
            c.execute("DELETE FROM respostas WHERE usuario = ?", (st.session_state.usuario_atual,))
            conn.commit()
            st.session_state.bateria_atual = []
            st.success("O histórico foi apagado!")
            st.rerun()

# ================= TELA PRINCIPAL =================
if not st.session_state.usuario_atual:
    st.title("🔒 Bem-vindo ao Sistema")
    st.info("Por favor, selecione ou crie um perfil na barra lateral.")
else:
    st.title(f"📚 Plataforma de Resolução - {st.session_state.usuario_atual}")
    st.write("---")

    df_resp = pd.read_sql_query("SELECT * FROM respostas WHERE usuario = ?", conn, params=(st.session_state.usuario_atual,))
    total_resp = len(df_resp)
    taxa_acerto = round((df_resp["acertou"].sum() / total_resp) * 100, 1) if total_resp > 0 else 0
    acertos = df_resp["acertou"].sum() if total_resp > 0 else 0

    colA, colB, colC = st.columns(3)
    with colA: st.markdown(f'<div class="metric-box"><div class="metric-title">Itens Resolvidos</div><div class="metric-value">{total_resp}</div></div>', unsafe_allow_html=True)
    with colB: st.markdown(f'<div class="metric-box"><div class="metric-title">Acertos</div><div class="metric-value">{acertos}</div></div>', unsafe_allow_html=True)
    with colC: st.markdown(f'<div class="metric-box"><div class="metric-title">Aproveitamento</div><div class="metric-value" style="color: {"#28a745" if taxa_acerto >= 70 else "#dc3545"};">{taxa_acerto}%</div></div>', unsafe_allow_html=True)

    st.write("<br>", unsafe_allow_html=True)

    with st.container(border=True):
        st.subheader("⚡ Gerar Bateria de Simulado")
        
        if st.session_state.edital_ativo:
            e = st.session_state.edital_ativo
            banca_alvo = e['banca']
            cargo_alvo = e['cargo']
            nivel_dificuldade_auto = e.get('nivel_dificuldade', 3)
            formatos_banca = e.get('formatos', ["Múltipla Escolha (A a E)"])
            perfil_cargo = obter_perfil_cargo(cargo_alvo)
            perfil_banca = obter_perfil_banca(banca_alvo)
            
            st.markdown(f"<div class='banca-info'>🏢 <b>BANCA DETECTADA:</b> {banca_alvo} | <b>FORMATO:</b> {formatos_banca[0]} | <b>CARGO:</b> {cargo_alvo} | <b>NÍVEL:</b> {perfil_cargo['descrição']}</div>", unsafe_allow_html=True)
            
            lista_materias = ["Aleatório"] + e['materias']
            c1, c2 = st.columns(2)
            with c1: mat_selecionada = st.selectbox("Escolha a Matéria", lista_materias)
            with c2: tema_selecionado = st.text_input("Tema específico (ou deixe Aleatório)", "Aleatório")
        else:
            st.warning("⚠️ Carregue um edital na barra lateral para usar a configuração automática.")
            c1, c2, c3 = st.columns(3)
            with c1: banca_alvo = st.text_input("Banca", "Cebraspe")
            with c2: cargo_alvo = st.text_input("Cargo", "Delegado")
            with c3: mat_selecionada = st.text_input("Matéria", "Direito Penal")
            tema_selecionado = st.text_input("Tema específico", "Aleatório")
            nivel_dificuldade_auto = 3
            formatos_banca = ["Múltipla Escolha (A a E)"]
            perfil_banca = obter_perfil_banca(banca_alvo)

        c3, c4 = st.columns(2)
        with c3:
            tipo = st.selectbox("Origem do Material", [
                "🧠 Inédita IA", 
                "🌐 Questões Reais",
                "📂 Revisão (Sortear banco local)"
            ])
        with c4: 
            qtd = st.slider("Quantidade", 1, 10, 5)
            
        usar_web = st.checkbox("🌐 Usar Pesquisa na Web (busca questões similares da banca)", value=True)

        if st.button("Forjar Simulado", type="primary", use_container_width=True):
            mat_final = random.choice(e['materias']) if mat_selecionada == "Aleatório" and st.session_state.edital_ativo else mat_selecionada
            instrucao_tema = f"Sorteie um tema complexo em {mat_final}" if tema_selecionado.lower() == "aleatório" else tema_selecionado

            if "Revisão" in tipo:
                st.info("🔄 A resgatar histórico do banco local...")
                c.execute("""
                    SELECT id FROM questoes 
                    WHERE (banca LIKE ? OR cargo LIKE ? OR materia LIKE ?)
                    ORDER BY RANDOM() LIMIT ?
                """, (f"%{banca_alvo}%", f"%{cargo_alvo}%", f"%{mat_selecionada}%", qtd))
                encontradas = [row[0] for row in c.fetchall()]
                if encontradas:
                    st.session_state.bateria_atual = encontradas
                    st.rerun()
                else:
                    st.warning("Banco local insuficiente.")

            else:
                with st.spinner(f"🔍 Buscando padrão da banca {banca_alvo}..."):
                    contexto_questoes = ""
                    contexto_jurisprudencia = ""
                    contexto_estilo = ""
                    
                    if usar_web:
                        with st.spinner(f"📚 Pesquisando questões similares..."):
                            contexto_questoes = pesquisar_questoes_banca(banca_alvo, cargo_alvo, mat_final, tema_selecionado)
                        
                        with st.spinner(f"⚖️ Buscando jurisprudência..."):
                            contexto_jurisprudencia = pesquisar_jurisprudencia_banca(banca_alvo, cargo_alvo, mat_final)
                        
                        with st.spinner(f"🎯 Analisando estilo da banca..."):
                            contexto_estilo = pesquisar_estilo_questoes_banca(banca_alvo)
                    else:
                        contexto_questoes = f"Estudando questões da {banca_alvo} para {cargo_alvo}"
                        contexto_jurisprudencia = "Usando jurisprudência consolidada de memória"
                        contexto_estilo = "Usando padrão conhecido da banca"

                    prompt = gerar_prompt_com_banca_e_dificuldade(
                        qtd, banca_alvo, cargo_alvo, mat_final, instrucao_tema,
                        tipo, contexto_questoes, contexto_jurisprudencia, contexto_estilo
                    )

                    with st.spinner(f"🚀 Gerando questões no estilo {banca_alvo}..."):
                        try:
                            if "Groq" in motor_escolhido:
                                resposta = client_groq.chat.completions.create(
                                    messages=[{"role": "user", "content": prompt}],
                                    model="llama-3.3-70b-versatile",
                                    temperature=0.0,
                                    response_format={"type": "json_object"}
                                )
                            else:
                                resposta = client_deepseek.chat.completions.create(
                                    messages=[{"role": "user", "content": prompt}],
                                    model="deepseek-chat",
                                    temperature=0.0,
                                    response_format={"type": "json_object"},
                                    max_tokens=4000
                                )
                            
                            dados_json = json.loads(resposta.choices[0].message.content.replace("```json", "").replace("```", "").strip())
                            lista_questoes = dados_json.get("questoes", [])
                            if not lista_questoes and isinstance(dados_json, list): 
                                lista_questoes = dados_json
                            
                            novas_ids = []
                            for dados in lista_questoes:
                                enunciado = dados.get("enunciado", "N/A")
                                gabarito = dados.get("gabarito", "N/A")
                                fonte = dados.get("fonte", f"Inédita IA - {banca_alvo}")
                                dificuldade = dados.get("dificuldade", nivel_dificuldade_auto)
                                tags = json.dumps(dados.get("tags", []))
                                formato_questao = dados.get("formato", formatos_banca[0])
                                alts_dict = dados.get("alternativas", {})
                                
                                alternativas = json.dumps(alts_dict)
                                explicacao_texto = dados.get("explicacao", "N/A")
                                comentarios_dict = dados.get("comentarios", {})
                                explicacao_final = json.dumps({"geral": explicacao_texto, "detalhes": comentarios_dict})

                                c.execute("""
                                INSERT INTO questoes (banca, cargo, materia, tema, enunciado, alternativas, gabarito, explicacao, tipo, fonte, dificuldade, tags, formato_questao)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (banca_alvo, cargo_alvo, mat_final, tema_selecionado, enunciado, alternativas, gabarito, explicacao_final, tipo, fonte, dificuldade, tags, formato_questao))
                                novas_ids.append(c.lastrowid)
                            
                            conn.commit()
                            st.session_state.bateria_atual = novas_ids
                            st.success(f"✅ {len(novas_ids)} questões geradas no padrão da {banca_alvo}!")
                            st.rerun()
                            
                        except Exception as e:
                            if "rate_limit_exceeded" in str(e).lower() or "429" in str(e):
                                st.error("⚠️ **Limite diário do Groq atingido!** Use o motor **DeepSeek**.")
                            else:
                                st.error(f"❌ Erro na geração: {e}")

    if st.session_state.bateria_atual:
        st.write("---")
        st.subheader("🎯 Caderno de Prova")
        
        df_respostas = pd.read_sql_query(f"SELECT questao_id, resposta_usuario, acertou FROM respostas WHERE usuario = '{st.session_state.usuario_atual}' AND questao_id IN ({','.join(map(str, st.session_state.bateria_atual))})", conn)
        respondidas = df_respostas.set_index('questao_id').to_dict('index')

        for i, q_id in enumerate(st.session_state.bateria_atual):
            c.execute("SELECT banca, cargo, materia, enunciado, alternativas, gabarito, explicacao, fonte, dificuldade, tags, formato_questao FROM questoes WHERE id = ?", (q_id,))
            dados = c.fetchone()
            
            if dados:
                q_banca, q_cargo, q_mat, q_enun, q_alt, q_gab, q_exp, q_fonte, q_dif, q_tags, q_formato = dados
                alts = json.loads(q_alt) if q_alt else {}
                tags_list = json.loads(q_tags) if q_tags else []
                
                dif_label = ["Muito Fácil", "Fácil", "Médio", "Difícil", "Muito Difícil"][min(q_dif - 1, 4)] if q_dif else "Médio"
                dif_classe = "dif-facil" if q_dif <= 2 else "dif-medio" if q_dif == 3 else "dif-dificil"
                
                try:
                    exp_data = json.loads(q_exp)
                    if isinstance(exp_data, dict) and "geral" in exp_data:
                        exp_geral = exp_data["geral"]
                        exp_detalhes = exp_data.get("detalhes", {})
                    else:
                        exp_geral = q_exp
                        exp_detalhes = {}
                except:
                    exp_geral = q_exp
                    exp_detalhes = {}
                
                with st.container(border=True):
                    col_info, col_dif = st.columns([4, 1])
                    with col_info:
                        st.caption(f"**Item {i+1}** | 🏢 {q_banca} | 📚 {q_mat} | 🎯 {q_formato}")
                    with col_dif:
                        st.markdown(f"<span class='dificuldade-badge {dif_classe}'>{dif_label}</span>", unsafe_allow_html=True)
                    
                    if tags_list:
                        st.caption(f"Tags: {', '.join(tags_list)}")
                    
                    st.markdown(f"#### {q_enun}")
                    
                    if "Certo/Errado" in q_formato:
                        opcoes = ["Selecionar...", "Certo", "Errado"]
                    else:
                        opcoes = ["Selecionar..."] + [f"{letra}) {texto}" for letra, texto in alts.items()] if alts else ["Selecionar...", "A", "B", "C", "D", "E"]

                    if q_id in respondidas:
                        status = respondidas[q_id]
                        st.markdown("<br><b>Análise Detalhada das Alternativas:</b>", unsafe_allow_html=True)
                        
                        if "Certo/Errado" in q_formato:
                            for opcao in opcoes[1:]:
                                letra_opcao = opcao.strip().upper()
                                gab_oficial = str(q_gab).strip().upper()
                                
                                is_resposta_usuario = (status['resposta_usuario'] == letra_opcao)
                                is_gabarito = (letra_opcao == gab_oficial)
                                
                                if is_resposta_usuario:
                                    if status['acertou'] == 1: st.markdown(f"<div class='alt-correta'>✅ <b>{opcao}</b> (Sua Resposta Correta)</div>", unsafe_allow_html=True)
                                    else: st.markdown(f"<div class='alt-errada'>❌ <b>{opcao}</b> (Sua Resposta Incorreta)</div>", unsafe_allow_html=True)
                                elif is_gabarito and status['acertou'] == 0:
                                    st.markdown(f"<div class='alt-gabarito'>🎯 <b>{opcao}</b> (Gabarito Oficial)</div>", unsafe_allow_html=True)
                                else:
                                    st.markdown(f"<div class='alt-neutra'>{opcao}</div>", unsafe_allow_html=True)
                        else:
                            for opcao in opcoes[1:]:
                                letra_opcao = opcao.split(")")[0].strip().upper() if alts else opcao.strip().upper()
                                gab_oficial = str(q_gab).strip().upper()
                                
                                is_resposta_usuario = (status['resposta_usuario'] == letra_opcao)
                                is_gabarito = (letra_opcao in gab_oficial or gab_oficial in letra_opcao)
                                
                                if is_resposta_usuario:
                                    if status['acertou'] == 1: st.markdown(f"<div class='alt-correta'>✅ <b>{opcao}</b> (Sua Resposta Correta)</div>", unsafe_allow_html=True)
                                    else: st.markdown(f"<div class='alt-errada'>❌ <b>{opcao}</b> (Sua Resposta Incorreta)</div>", unsafe_allow_html=True)
                                elif is_gabarito and status['acertou'] == 0:
                                    st.markdown(f"<div class='alt-gabarito'>🎯 <b>{opcao}</b> (Gabarito Oficial)</div>", unsafe_allow_html=True)
                                else:
                                    st.markdown(f"<div class='alt-neutra'>{opcao}</div>", unsafe_allow_html=True)
                                
                                if letra_opcao in exp_detalhes and exp_detalhes[letra_opcao]:
                                    st.markdown(f"<div class='comentario-alt'>💡 <i><b>Por que?</b> {exp_detalhes[letra_opcao]}</i></div>", unsafe_allow_html=True)

                        st.write("<br>", unsafe_allow_html=True)
                        with st.expander("📖 Fundamentação Legal Geral"): st.write(exp_geral)
                    else:
                        st.write("")
                        resp = st.radio("Sua Resposta:", opcoes, key=f"rad_{q_id}", label_visibility="collapsed")
                        if st.button("Confirmar Resposta", key=f"btn_{q_id}"):
                            if resp != "Selecionar...":
                                if "Certo/Errado" in q_formato:
                                    letra = resp.strip().upper()
                                else:
                                    letra = resp.split(")")[0].strip().upper() if alts else resp.strip().upper()
                                
                                gab = str(q_gab).strip().upper()
                                acertou = 1 if letra in gab or gab in letra else 0
                                c.execute("""
                                INSERT INTO respostas (usuario, questao_id, resposta_usuario, acertou, data)
                                VALUES (?, ?, ?, ?, ?)
                                """, (st.session_state.usuario_atual, q_id, letra, acertou, str(datetime.now())))
                                conn.commit()
                                st.rerun()
                            else:
                                st.warning("Selecione uma opção.")
