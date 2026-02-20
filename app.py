import streamlit as st
import sqlite3
import pdfplumber
import pandas as pd
from datetime import datetime
from google import genai
import json
import random
import time

st.set_page_config(page_title="App Concurso Inteligente", layout="wide", initial_sidebar_state="expanded")

# ================= CHAVE GEMINI COFRE SECRETO =================
client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
# ===========================================================

# ================= BANCO DE DADOS =================
@st.cache_resource
def iniciar_conexao():
    conn = sqlite3.connect("estudos.db", check_same_thread=False)
    c = conn.cursor()
    
    c.execute("""
    CREATE TABLE IF NOT EXISTS questoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        materia TEXT,
        tema TEXT,
        enunciado TEXT,
        gabarito TEXT,
        explicacao TEXT,
        tipo TEXT,
        fonte TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS respostas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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

if "questao_atual" not in st.session_state:
    st.session_state.questao_atual = None

if "dados_edital" not in st.session_state:
    st.session_state.dados_edital = None

# ================= BARRA LATERAL (SIDEBAR) =================
with st.sidebar:
    st.title("⚙️ Configurações")
    st.divider()
    
    st.header("1️⃣ Edital Base")
    edital = st.file_uploader("Upload do Edital (PDF)", type="pdf")

    if edital:
        if st.button("Analisar Edital e Extrair Matérias", use_container_width=True):
            with st.spinner("Mapeando conteúdo programático..."):
                with pdfplumber.open(edital) as pdf:
                    texto = ""
                    for pagina in pdf.pages:
                        if pagina.extract_text():
                            texto += pagina.extract_text() + "\n"

                prompt = f"""
                Você é um especialista em análise de editais de concurso.
                Leia o edital abaixo e extraia o Conteúdo Programático.
                
                Responda EXCLUSIVAMENTE em formato JSON com a seguinte estrutura:
                {{
                  "banca": "Nome da Banca",
                  "disciplinas": {{
                    "Disciplina 1": ["Tópico 1", "Tópico 2"],
                    "Disciplina 2": ["Tópico 1"]
                  }}
                }}
                
                Texto: {texto}
                """

                try:
                    time.sleep(8) 
                    resposta = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=prompt,
                    )
                    
                    texto_json = resposta.text.replace("```json", "").replace("```", "").strip()
                    dados = json.loads(texto_json)
                    st.session_state.dados_edital = dados
                    st.success("Edital mapeado com sucesso!")
                    
                except Exception as e:
                    st.error(f"Erro ao estruturar matérias: {e}")

    st.divider()
    st.header("⚠️ Área de Risco")
    if st.button("Zerar Progresso (Apagar Respostas)", use_container_width=True):
        c.execute("DELETE FROM respostas")
        conn.commit()
        st.success("Histórico apagado com sucesso!")
        st.rerun()

    st.divider()
    st.markdown("### 👨‍💻 Desenvolvedor")
    st.caption("Criado e projetado por **Marcos Gonçalves Versiane**.")
    st.markdown("🌐 [Acessar marcosversiane.com](https://marcosversiane.com)")

# ================= TELA PRINCIPAL (ABAS) =================
st.title("📚 Sistema Inteligente de Estudos")
st.markdown("##### *Criado por Marcos Versiane*")

if st.session_state.dados_edital:
    st.caption(f"🎯 Banca Foco: **{st.session_state.dados_edital.get('banca', 'N/A')}**")

aba1, aba2, aba3 = st.tabs(["⚡ Gerar Questões", "🎯 Modo Foco (Resolver)", "📊 Desempenho Geral"])

# ================= ABA 1: GERAR QUESTÕES =================
with aba1:
    st.header("Criar Novo Material de Estudo")
    st.write("Abasteça o banco de dados com novas questões antes de iniciar o treinamento.")
    
    if st.session_state.dados_edital and "disciplinas" in st.session_state.dados_edital:
        disciplinas_dict = st.session_state.dados_edital["disciplinas"]
        banca_edital = st.session_state.dados_edital.get("banca", "Cebraspe")
        
        lista_materias = ["Aleatório"] + list(disciplinas_dict.keys())
        
        col1, col2 = st.columns(2)
        with col1:
            materia_selecionada = st.selectbox("Escolha a Matéria", lista_materias)
        
        with col2:
            if materia_selecionada == "Aleatório":
                lista_temas = ["Aleatório"]
            else:
                lista_temas = ["Aleatório"] + disciplinas_dict[materia_selecionada]
            
            tema_selecionado = st.selectbox("Escolha o Tema", lista_temas)
            
    else:
        banca_edital = "Estilo da Banca"
        col1, col2 = st.columns(2)
        with col1:
            materia_selecionada = st.text_input("Matéria (ex: Direito Penal)", "Aleatório")
        with col2:
            tema_selecionado = st.text_input("Tema (ex: Inquérito Policial)", "Aleatório")

    col_tipo, col_qtd = st.columns([2, 1])
    with col_tipo:
        tipo = st.selectbox("Origem da Questão", ["Questões Reais de Provas Anteriores", "Inédita IA (Estilo Banca)"])
    with col_qtd:
        quantidade = st.slider("Quantidade de Questões", min_value=1, max_value=10, value=5)

    if st.button("Gerar Questões para o Banco", type="primary"):
        with st.spinner(f"Formulando {quantidade} questão(ões) com fundamentação rigorosa..."):
            
            mat_final = materia_selecionada
            tem_final = tema_selecionado
            
            if st.session_state.dados_edital:
                if mat_final == "Aleatório":
                    mat_final = random.choice(list(disciplinas_dict.keys()))
                    tem_final = random.choice(disciplinas_dict[mat_final])
                elif tem_final == "Aleatório":
                    tem_final = random.choice(disciplinas_dict[mat_final])
            else:
                if mat_final == "Aleatório": mat_final = "Direito Constitucional"
                if tem_final == "Aleatório": tem_final = "Direitos Fundamentais"

            fator_aleatorio = random.randint(10000, 99999)

            prompt = f"""
            Aja como um examinador de concursos públicos de alto nível no Brasil.
            Gere exatamente {quantidade} questão(ões) distinta(s) sobre:
            Banca: {banca_edital}
            Matéria: {mat_final}
            Tema: {tem_final}
            Diretriz de Origem: {tipo}
            Código de Exclusividade: {fator_aleatorio}
            
            Regras Absolutas:
            1. Fundamente a explicação ESTRITAMENTE na legislação brasileira vigente e na jurisprudência real. Jamais invente leis ou súmulas.
            2. Se a diretriz for 'Questões Reais', busque itens autênticos e varie o ano/órgão, garantindo a não repetição de abordagens.
            3. Se for 'Inédita IA', crie abordagens jurídicas complexas e totalmente novas.
            
            Responda EXCLUSIVAMENTE em formato JSON, retornando UMA LISTA (array) com {quantidade} objeto(s), seguindo esta estrutura exata:
            [
              {{
                "enunciado": "O texto da afirmação a ser julgada",
                "gabarito": "Certo" ou "Errado",
                "explicacao": "Explicação completa e assertiva com o respectivo fundamento legal brasileiro vigente.",
                "fonte": "Indique o Ano e o Órgão da prova real ou escreva 'Inédita - Criada por IA'."
              }}
            ]
            """

            try:
                time.sleep(8) 
                resposta = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                )
                
                texto_json = resposta.text.replace("```json", "").replace("```", "").strip()
                lista_questoes = json.loads(texto_json)
                
                # Garante o funcionamento caso o modelo devolva um dicionário único em vez de lista
                if isinstance(lista_questoes, dict):
                    lista_questoes = [lista_questoes]
                
                for dados in lista_questoes:
                    c.execute("""
                    INSERT INTO questoes (materia, tema, enunciado, gabarito, explicacao, tipo, fonte)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (mat_final, tem_final, dados['enunciado'], dados['gabarito'], dados['explicacao'], tipo, dados.get('fonte', 'N/A')))
                
                conn.commit()
                st.success(f"Excelente! {len(lista_questoes)} questão(ões) adicionada(s) ao banco de dados. (Matéria: {mat_final})")
            except Exception as e:
                st.error(f"Erro ao gerar itens: {e}")

# ================= ABA 2: RESOLVER QUESTÃO =================
with aba2:
    st.header("Modo Foco")
    
    if st.button("Sortear Questão Inédita no Treinamento", type="primary"):
        c.execute("""
            SELECT id, materia, tema, enunciado, gabarito, explicacao, tipo, fonte 
            FROM questoes 
            WHERE id NOT IN (SELECT questao_id FROM respostas)
            ORDER BY RANDOM() LIMIT 1
        """)
        q = c.fetchone()
        if q:
            st.session_state.questao_atual = q
            st.session_state.respondida = False
        else:
            c.execute("SELECT COUNT(*) FROM questoes")
            total_questoes = c.fetchone()[0]
            if total_questoes == 0:
                st.warning("O banco de dados está vazio. Acesse a aba 'Gerar Questões' primeiro.")
            else:
                st.success("Todas as questões geradas no momento já receberam respostas. Gere novos itens na Aba 1 para continuar o treinamento.")
            st.session_state.questao_atual = None

    if st.session_state.questao_atual:
        q = st.session_state.questao_atual
        
        with st.container(border=True):
            st.write(f"**📚 {q[1]}** | **📌 {q[2]}**")
            st.caption(f"**🏷️ Origem:** {q[7]}")
            st.markdown(f"### Julgue o item:\n\n{q[3]}")

        if not st.session_state.get("respondida", False):
            st.write("---")
            resposta_usuario = st.radio("Selecione a opção correta:", ["Selecionar...", "Certo", "Errado"], index=0, horizontal=True)
            
            if st.button("Confirmar", use_container_width=True) and resposta_usuario != "Selecionar...":
                gabarito_correto = q[4].strip().lower()
                acertou = 1 if resposta_usuario.lower() == gabarito_correto else 0
                
                c.execute("""
                INSERT INTO respostas (questao_id, resposta_usuario, acertou, data)
                VALUES (?, ?, ?, ?)
                """, (q[0], resposta_usuario, acertou, str(datetime.now())))
                conn.commit()
                
                st.session_state.respondida = True
                st.session_state.ultimo_acerto = acertou
                st.rerun()

        if st.session_state.get("respondida", False):
            st.write("---")
            if st.session_state.ultimo_acerto:
                st.success(f"✅ Exato! O gabarito é: **{q[4]}**")
            else:
                st.error(f"❌ Incorreto! O gabarito é: **{q[4]}**")
                
            with st.expander("📖 Ver Fundamentação Completa", expanded=True):
                st.write(q[5])

# ================= ABA 3: DASHBOARD =================
with aba3:
    st.header("Análise de Resultados")

    df = pd.read_sql_query("SELECT * FROM respostas", conn)

    if not df.empty:
        taxa = round((df["acertou"].sum() / len(df)) * 100, 2)
        colA, colB = st.columns(2)
        colA.metric("Aproveitamento Total", f"{taxa}%")
        colB.metric("Bateria de Resoluções", len(df))
    else:
        st.info("Inicie a resolução de itens para compilar os dados estatísticos.")
