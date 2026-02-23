import streamlit as st
import sqlite3
import pdfplumber
import pandas as pd
from datetime import datetime
import json
import random
from groq import Groq

# ================= CONFIGURAÇÃO VISUAL =================
st.set_page_config(page_title="Sistema de Estudos Avançado", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .metric-box {
        background-color: #f8f9fa; border-radius: 10px; padding: 20px; text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #e9ecef;
    }
    .metric-title { font-size: 14px; color: #6c757d; font-weight: 600; text-transform: uppercase; }
    .metric-value { font-size: 32px; font-weight: 700; color: #212529; margin-top: 5px; }
    .stRadio > div { flex-direction: row; gap: 15px; }
    </style>
""", unsafe_allow_html=True)

# ================= CHAVE GROQ =================
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# ================= BANCO DE DADOS =================
@st.cache_resource
def iniciar_conexao():
    conn = sqlite3.connect("estudos.db", check_same_thread=False)
    c = conn.cursor()
    
    # Tabela de Questões
    c.execute("""
    CREATE TABLE IF NOT EXISTS questoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        materia TEXT, tema TEXT, enunciado TEXT,
        gabarito TEXT, explicacao TEXT, tipo TEXT, fonte TEXT
    )
    """)
    # Tabela de Respostas
    c.execute("""
    CREATE TABLE IF NOT EXISTS respostas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        questao_id INTEGER, resposta_usuario TEXT,
        acertou INTEGER, data TEXT
    )
    """)
    # NOVA Tabela de Editais Salvos
    c.execute("""
    CREATE TABLE IF NOT EXISTS editais_salvos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome_arquivo TEXT,
        dados_json TEXT,
        data_analise TEXT
    )
    """)
    
    try: c.execute("ALTER TABLE questoes ADD COLUMN alternativas TEXT")
    except: pass
    try: c.execute("ALTER TABLE questoes ADD COLUMN cargo TEXT")
    except: pass
    
    conn.commit()
    return conn

conn = iniciar_conexao()
c = conn.cursor()

# ================= INICIALIZAÇÃO DE MEMÓRIA =================
if "bateria_atual" not in st.session_state:
    st.session_state.bateria_atual = []
    
if "dados_edital" not in st.session_state:
    st.session_state.dados_edital = None

# ================= BARRA LATERAL (BIBLIOTECA DE EDITAIS) =================
with st.sidebar:
    st.title("⚙️ Sistema Base")
    st.divider()
    
    st.header("1️⃣ Biblioteca de Editais")
    
    # Busca editais já salvos no banco
    df_editais = pd.read_sql_query("SELECT id, nome_arquivo, dados_json FROM editais_salvos ORDER BY id DESC", conn)
    
    if not df_editais.empty:
        opcoes_editais = ["Selecione um edital salvo..."] + df_editais['nome_arquivo'].tolist()
        edital_selecionado = st.selectbox("Carregar Edital do Banco:", opcoes_editais)
        
        if edital_selecionado != "Selecione um edital salvo...":
            # Carrega o JSON do banco de dados para a memória
            json_salvo = df_editais[df_editais['nome_arquivo'] == edital_selecionado]['dados_json'].iloc[0]
            st.session_state.dados_edital = json.loads(json_salvo)
            st.success("Edital carregado da memória com sucesso!")
    else:
        st.info("Nenhum edital salvo no banco de dados ainda.")

    st.write("---")
    with st.expander("➕ Adicionar Novo Edital", expanded=True if df_editais.empty else False):
        nome_novo_edital = st.text_input("Nome do Concurso (ex: PCDF - Delegado):")
        edital_file = st.file_uploader("Upload do PDF", type="pdf")

        if edital_file and nome_novo_edital:
            if st.button("Analisar e Salvar no Banco", use_container_width=True):
                with st.spinner("Rastreando cargos e matérias..."):
                    with pdfplumber.open(edital_file) as pdf:
                        texto = ""
                        for pagina in pdf.pages:
                            if pagina.extract_text():
                                texto += pagina.extract_text() + "\n"
                    
                    texto_upper = texto.upper()
                    inicio = texto_upper.rfind("CONTEÚDO PROGRAMÁTICO")
                    if inicio == -1: inicio = texto_upper.rfind("CONHECIMENTOS BÁSICOS")
                    if inicio == -1: inicio = texto_upper.rfind("OBJETOS DE AVALIAÇÃO")
                    if inicio == -1: inicio = max(0, len(texto) - 20000) 
                    
                    texto_reduzido = texto[inicio : inicio + 20000]

                    prompt = f"""
                    Você é um especialista em análise de editais.
                    Leia o recorte do edital e extraia a Banca e TODOS OS CARGOS com as suas DISCIPLINAS (Matérias).
                    NÃO extraia subtópicos.
                    
                    Responda EXCLUSIVAMENTE em formato JSON:
                    {{
                      "banca": "Nome da Banca",
                      "cargos": {{
                        "Cargo 1": ["Matéria 1", "Matéria 2"],
                        "Cargo 2": ["Matéria 1"]
                      }}
                    }}
                    Texto a analisar: {texto_reduzido}
                    """

                    try:
                        resposta = client.chat.completions.create(
                            messages=[
                                {"role": "system", "content": "Responda estritamente em JSON válido."},
                                {"role": "user", "content": prompt}
                            ],
                            model="llama-3.3-70b-versatile",
                            temperature=0.1,
                            response_format={"type": "json_object"}
                        )
                        
                        texto_json = resposta.choices[0].message.content.replace("```json", "").replace("```", "").strip()
                        
                        # Salva no Banco de Dados
                        c.execute("""
                        INSERT INTO editais_salvos (nome_arquivo, dados_json, data_analise)
                        VALUES (?, ?, ?)
                        """, (nome_novo_edital, texto_json, str(datetime.now())))
                        conn.commit()
                        
                        st.session_state.dados_edital = json.loads(texto_json)
                        st.success("Análise concluída e salva no banco de dados!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao analisar o edital: {e}")

    st.divider()
    st.header("⚠️ Gestão de Dados")
    if st.button("Limpar Histórico de Respostas", use_container_width=True):
        c.execute("DELETE FROM respostas")
        conn.commit()
        st.session_state.bateria_atual = []
        st.success("Histórico de desempenho limpo!")
        st.rerun()

    st.divider()
    st.markdown("### 👨‍💻 Desenvolvedor")
    st.caption("Criado e projetado por **Marcos Gonçalves Versiane**.")
    st.markdown("🌐 [Aceder a marcosversiane.com](https://marcosversiane.com)")

# ================= PAINEL ÚNICO PRINCIPAL =================
st.title("📚 Plataforma Integrada de Resolução")
st.markdown("##### *Criado por Marcos Versiane*")
st.write("---")

# --- 1. DASHBOARD DE DESEMPENHO NO TOPO ---
df_resp = pd.read_sql_query("SELECT * FROM respostas", conn)
total_resp = len(df_resp)
taxa_acerto = round((df_resp["acertou"].sum() / total_resp) * 100, 1) if total_resp > 0 else 0
acertos = df_resp["acertou"].sum() if total_resp > 0 else 0

colA, colB, colC = st.columns(3)
with colA:
    st.markdown(f'<div class="metric-box"><div class="metric-title">Itens Resolvidos</div><div class="metric-value">{total_resp}</div></div>', unsafe_allow_html=True)
with colB:
    st.markdown(f'<div class="metric-box"><div class="metric-title">Acertos</div><div class="metric-value">{acertos}</div></div>', unsafe_allow_html=True)
with colC:
    st.markdown(f'<div class="metric-box"><div class="metric-title">Aproveitamento Total</div><div class="metric-value" style="color: {"#28a745" if taxa_acerto >= 70 else "#dc3545"};">{taxa_acerto}%</div></div>', unsafe_allow_html=True)

st.write("<br>", unsafe_allow_html=True)

# --- 2. CONFIGURAÇÃO DO LOTE DE QUESTÕES ---
with st.container(border=True):
    st.subheader("⚡ Configurar Nova Bateria de Questões")
    
    banca_edital = "Estilo da Banca"
    lista_cargos = ["Geral"]
    cargo_selecionado = "Geral"
    
    if st.session_state.dados_edital and "cargos" in st.session_state.dados_edital:
        banca_edital = st.session_state.dados_edital.get("banca", "Cebraspe")
        st.caption(f"🎯 **Banca Alvo Identificada:** {banca_edital}")
        
        lista_cargos = list(st.session_state.dados_edital["cargos"].keys())
        cargo_selecionado = st.selectbox("1. Selecione o Cargo Foco", lista_cargos)
        
        lista_materias_edital = st.session_state.dados_edital["cargos"][cargo_selecionado]
        lista_materias = ["Aleatório"] + lista_materias_edital
        
        c1, c2 = st.columns(2)
        with c1:
            materia_selecionada = st.selectbox("2. Escolha a Matéria", lista_materias)
        with c2:
            tema_selecionado = st.text_input("3. Especifique um Tema (ou deixe Aleatório)", "Aleatório")
            
    else:
        st.warning("Nenhum edital carregado. Selecione um na biblioteca ao lado ou cadastre um novo.")
        c1, c2 = st.columns(2)
        with c1: materia_selecionada = st.text_input("Matéria (ex: Direito Penal)", "Aleatório")
        with c2: tema_selecionado = st.text_input("Tema (ex: Inquérito Policial)", "Aleatório")

    c3, c4 = st.columns([2, 1])
    with c3:
        tipo = st.selectbox("Origem do Material", ["Inédita IA (Mimetizar Estilo da Banca)", "Questões Reais de Provas Anteriores"])
    with c4:
        quantidade = st.slider("Quantidade de Questões", 1, 10, 5)

    if st.button("Gerar Material e Iniciar Resolução", type="primary", use_container_width=True):
        with st.spinner(f"A moldar {quantidade} questão(ões) para o cargo de {cargo_selecionado}..."):
            mat_final = materia_selecionada
            tem_final = tema_selecionado
            
            if st.session_state.dados_edital and "cargos" in st.session_state.dados_edital:
                if mat_final == "Aleatório":
                    mat_final = random.choice(lista_materias_edital)

            fator_aleatorio = random.randint(10000, 99999)
            instrucao_tema = f"Sorteie um tema de elevada complexidade dentro da matéria de {mat_final}" if tem_final.lower() == "aleatório" else tem_final

            prompt = f"""
            Aja como um examinador de concursos públicos do Brasil.
            Gere exatamente {quantidade} questão(ões) distinta(s) sobre:
            Banca: {banca_edital}
            Cargo Avaliado: {cargo_selecionado}
            Matéria: {mat_final}
            Tema: {instrucao_tema}
            Diretriz: {tipo}
            Exclusividade: {fator_aleatorio}
            
            REGRAS ABSOLUTAS:
            1. Fundamente a explicação ESTRITAMENTE na legislação brasileira vigente e nas normas brasileiras em geral. Jamais invente jurisprudência ou algo do tipo. Seja assertivo e responsável.
            2. Nível de dificuldade compatível com as exigências para o cargo de {cargo_selecionado}.
            3. MIMETIZE A BANCA: Se a banca {banca_edital} cobra Múltipla Escolha (A, B, C, D, E), crie obrigatoriamente alternativas. Se a banca cobra Certo/Errado (ex: Cebraspe), faça afirmativas simples.
            
            Responda EXCLUSIVAMENTE em formato JSON, utilizando EXATAMENTE a seguinte estrutura:
            {{
              "questoes": [
                {{
                  "enunciado": "O texto da questão ou afirmativa",
                  "alternativas": {{
                    "A": "texto", "B": "texto", "C": "texto", "D": "texto", "E": "texto"
                  }}, // Deixe vazio {{}} SE for banca de Certo/Errado.
                  "gabarito": "Indique a Letra correta ou escreva Certo ou Errado",
                  "explicacao": "Explicação completa, assertiva e alicerçada nas normas brasileiras.",
                  "fonte": "Indique o Ano/Órgão ou Inédita IA"
                }}
              ]
            }}
            """

            try:
                resposta = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "Você responde estritamente em formato JSON válido, respeitando o ordenamento jurídico brasileiro."},
                        {"role": "user", "content": prompt}
                    ],
                    model="llama-3.3-70b-versatile",
                    temperature=0.3,
                    response_format={"type": "json_object"}
                )
                
                texto_json = resposta.choices[0].message.content.replace("```json", "").replace("```", "").strip()
                dados_json = json.loads(texto_json)
                lista_questoes = dados_json.get("questoes", [])
                
                if not lista_questoes and isinstance(dados_json, list): lista_questoes = dados_json
                elif not lista_questoes and isinstance(dados_json, dict) and "gabarito" in str(dados_json).lower(): lista_questoes = [dados_json]
                
                novas_questoes_ids = []

                for dados in lista_questoes:
                    enunciado = dados.get("enunciado", "Enunciado não disponível")
                    gabarito = dados.get("gabarito", "Não informado")
                    explicacao = dados.get("explicacao", "Sem explicação")
                    fonte = dados.get("fonte", "N/A")
                    alternativas_json = json.dumps(dados.get("alternativas", {}))

                    c.execute("""
                    INSERT INTO questoes (cargo, materia, tema, enunciado, alternativas, gabarito, explicacao, tipo, fonte)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (cargo_selecionado, mat_final, tem_final, enunciado, alternativas_json, gabarito, explicacao, tipo, fonte))
                    
                    novas_questoes_ids.append(c.lastrowid)
                
                conn.commit()
                st.session_state.bateria_atual = novas_questoes_ids
                st.success(f"Banco atualizado com {len(lista_questoes)} novas questões!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao forjar as questões: {e}")

# --- 3. FEED DE RESOLUÇÃO CONTÍNUA ---
if st.session_state.bateria_atual:
    st.write("---")
    st.subheader("🎯 Caderno de Resolução")
    
    df_respostas_locais = pd.read_sql_query(f"SELECT questao_id, resposta_usuario, acertou FROM respostas WHERE questao_id IN ({','.join(map(str, st.session_state.bateria_atual))})", conn)
    questoes_respondidas = df_respostas_locais.set_index('questao_id').to_dict('index')

    for index, q_id in enumerate(st.session_state.bateria_atual):
        c.execute("SELECT cargo, materia, tema, enunciado, alternativas, gabarito, explicacao, fonte FROM questoes WHERE id = ?", (q_id,))
        dados_q = c.fetchone()
        
        if dados_q:
            cargo_q, mat_q, tema_q, enun_q, alt_json_q, gab_q, exp_q, fonte_q = dados_q
            alternativas_dict = json.loads(alt_json_q) if alt_json_q else {}
            
            with st.container(border=True):
                st.caption(f"**Questão {index + 1}** | 📚 {mat_q} | 💼 {cargo_q} | 🏷️ {fonte_q}")
                st.markdown(f"#### {enun_q}")
                
                is_multipla = len(alternativas_dict) > 0
                opcoes_radio = ["Selecionar..."]
                
                if is_multipla:
                    for letra, texto_alt in alternativas_dict.items():
                        opcoes_radio.append(f"{letra}) {texto_alt}")
                else:
                    opcoes_radio.extend(["Certo", "Errado"])

                if q_id in questoes_respondidas:
                    status = questoes_respondidas[q_id]
                    if status['acertou'] == 1:
                        st.success(f"✅ Opção marcada: **{status['resposta_usuario']}** (Correta!)")
                    else:
                        st.error(f"❌ Opção marcada: **{status['resposta_usuario']}** (Incorreta!)")
                        
                    st.info(f"**Gabarito Oficial:** {gab_q}")
                    with st.expander("📖 Ler Fundamentação Jurídica"):
                        st.write(exp_q)
                else:
                    st.write("")
                    resposta_selecionada = st.radio("Sua Resposta:", opcoes_radio, key=f"radio_{q_id}", label_visibility="collapsed")
                    
                    if st.button("Confirmar Resposta", key=f"btn_{q_id}"):
                        if resposta_selecionada != "Selecionar...":
                            letra_escolhida = resposta_selecionada.split(")")[0].strip().upper() if is_multipla else resposta_selecionada.strip().upper()
                            gabarito_oficial = gab_q.strip().upper()
                            
                            acertou = 1 if letra_escolhida in gabarito_oficial or gabarito_oficial in letra_escolhida else 0
                            
                            c.execute("""
                            INSERT INTO respostas (questao_id, resposta_usuario, acertou, data)
                            VALUES (?, ?, ?, ?)
                            """, (q_id, letra_escolhida, acertou, str(datetime.now())))
                            conn.commit()
                            st.rerun()
                        else:
                            st.warning("Selecione uma alternativa antes de confirmar.")
