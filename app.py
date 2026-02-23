import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import json
import random
from groq import Groq
from duckduckgo_search import DDGS

# ================= CONFIGURAÇÃO VISUAL =================
st.set_page_config(page_title="Sistema de Estudos Avançado", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .metric-box { background-color: #f8f9fa; border-radius: 10px; padding: 20px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #e9ecef; }
    .metric-title { font-size: 14px; color: #6c757d; font-weight: 600; text-transform: uppercase; }
    .metric-value { font-size: 32px; font-weight: 700; color: #212529; margin-top: 5px; }
    .stRadio > div { flex-direction: row; gap: 15px; }
    </style>
""", unsafe_allow_html=True)

# ================= CHAVE GROQ =================
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# ================= AGENTE DE BUSCA NA WEB =================
def pesquisar_na_web(query):
    """Realiza uma busca invisível na internet para trazer contexto atualizado (2024, 2025, 2026)."""
    try:
        resultados = DDGS().text(query, max_results=5)
        contexto = "\n".join([f"- {r['body']}" for r in resultados])
        return contexto
    except Exception as e:
        return "Sem resultados web no momento. Utilize o conhecimento da base jurídica."

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
        explicacao TEXT, tipo TEXT, fonte TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS respostas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT, questao_id INTEGER, resposta_usuario TEXT,
        acertou INTEGER, data TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS editais_salvos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT, nome_concurso TEXT, banca TEXT, cargo TEXT,
        dados_json TEXT, data_analise TEXT
    )
    """)
    conn.commit()
    return conn

conn = iniciar_conexao()
c = conn.cursor()

# ================= INICIALIZAÇÃO DE MEMÓRIA =================
if "usuario_atual" not in st.session_state: st.session_state.usuario_atual = None
if "bateria_atual" not in st.session_state: st.session_state.bateria_atual = []
if "edital_ativo" not in st.session_state: st.session_state.edital_ativo = None

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

    if st.session_state.usuario_atual:
        st.header("📚 Biblioteca de Editais")
        df_editais = pd.read_sql_query("SELECT id, nome_concurso, banca, cargo, dados_json FROM editais_salvos WHERE usuario = ? ORDER BY id DESC", conn, params=(st.session_state.usuario_atual,))
        
        if not df_editais.empty:
            opcoes_editais = ["Selecione um edital..."] + [f"{row['nome_concurso']} ({row['cargo']})" for _, row in df_editais.iterrows()]
            escolha = st.selectbox("Carregar Edital Salvo:", opcoes_editais)
            
            if escolha != "Selecione um edital...":
                idx_selecionado = opcoes_editais.index(escolha) - 1
                linha_selecionada = df_editais.iloc[idx_selecionado]
                st.session_state.edital_ativo = {
                    "nome_concurso": linha_selecionada['nome_concurso'],
                    "banca": linha_selecionada['banca'],
                    "cargo": linha_selecionada['cargo'],
                    "materias": json.loads(linha_selecionada['dados_json'])['materias']
                }
                st.success("Edital carregado com sucesso!")
        else:
            st.info("A biblioteca está vazia. Adicione um edital abaixo.")

        st.write("---")
        with st.expander("➕ Cadastrar Novo Edital", expanded=True if df_editais.empty else False):
            nome_novo = st.text_input("Nome do Concurso (Ex: PCSP):")
            banca_nova = st.text_input("Banca Examinadora (Ex: Vunesp, Consulplan):")
            cargo_novo = st.text_input("Cargo (Ex: Delegado, Escrivão):")
            texto_colado = st.text_area("Cole o texto do Conteúdo Programático aqui:")

            if st.button("Salvar Edital no Perfil", use_container_width=True) and nome_novo and texto_colado:
                with st.spinner("Estruturando matérias..."):
                    prompt = f"""
                    Leia o texto colado abaixo e liste APENAS os nomes das grandes áreas ou disciplinas.
                    Responda EXCLUSIVAMENTE em formato JSON:
                    {{"materias": ["Disciplina 1", "Disciplina 2"]}}
                    Texto: {texto_colado[:15000]}
                    """
                    try:
                        resposta = client.chat.completions.create(
                            messages=[{"role": "user", "content": prompt}],
                            model="llama-3.3-70b-versatile",
                            temperature=0.1,
                            response_format={"type": "json_object"}
                        )
                        texto_json = resposta.choices[0].message.content
                        c.execute("""
                        INSERT INTO editais_salvos (usuario, nome_concurso, banca, cargo, dados_json, data_analise)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """, (st.session_state.usuario_atual, nome_novo, banca_nova, cargo_novo, texto_json, str(datetime.now())))
                        conn.commit()
                        st.success("Salvo com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error("Erro ao estruturar. Tente novamente.")

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
    st.info("Por favor, selecione ou crie um perfil na barra lateral para iniciar a sessão.")
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
            st.caption(f"🎯 **Foco Atual:** {e['nome_concurso']} | **Banca:** {banca_alvo} | **Cargo:** {cargo_alvo}")
            
            lista_materias = ["Aleatório"] + e['materias']
            c1, c2 = st.columns(2)
            with c1: mat_selecionada = st.selectbox("Escolha a Matéria", lista_materias)
            with c2: tema_selecionado = st.text_input("Tema específico (ou deixe Aleatório)", "Aleatório")
        else:
            st.warning("Carregue um edital na barra lateral para focar a inteligência.")
            c1, c2, c3 = st.columns(3)
            with c1: banca_alvo = st.text_input("Banca", "Cebraspe")
            with c2: cargo_alvo = st.text_input("Cargo", "Geral")
            with c3: mat_selecionada = st.text_input("Matéria", "Direito Constitucional")
            tema_selecionado = st.text_input("Tema específico", "Aleatório")

        c3, c4, c5 = st.columns([2, 2, 1])
        with c3: 
            tipo = st.selectbox("Origem do Material", [
                "🧠 Inédita IA (Pesquisar Legislação Recente)", 
                "🌐 Questões Reais (Vasculhar Web)",
                "📂 Revisão (Sortear banco local)"
            ])
        with c4:
            formato_alvo = st.selectbox("Formato da Prova", [
                "Múltipla Escolha (A a E)", 
                "Múltipla Escolha (A a D)", 
                "Certo / Errado"
            ])
        with c5: 
            qtd = st.slider("Quantidade", 1, 10, 5)

        if st.button("Forjar Simulado", type="primary", use_container_width=True):
            mat_final = random.choice(e['materias']) if mat_selecionada == "Aleatório" and st.session_state.edital_ativo else mat_selecionada
            instrucao_tema = f"Sorteie um tema de alta complexidade em {mat_final}" if tema_selecionado.lower() == "aleatório" else tema_selecionado

            if "Revisão" in tipo:
                st.info("A resgatar histórico de erros e acertos...")
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
                    st.warning("O banco interno ainda não tem questões suficientes. Gere Inéditas ou Reais primeiro!")

            else:
                with st.spinner(f"A ativar Agente Autônomo para varrer a internet e aplicar formato {formato_alvo}..."):
                    if "Inédita" in tipo:
                        termo_busca = f"jurisprudencia STF STJ lei atualizada 2024 2025 2026 {mat_final} {tema_selecionado}"
                        instrucao_ia = f"Crie questões INÉDITAS baseadas nas inovações jurídicas e no contexto web fornecido. A abordagem deve ser no estilo da banca {banca_alvo}."
                    else:
                        termo_busca = f"questão de concurso {banca_alvo} {cargo_alvo} {mat_final} {tema_selecionado} 2022 2023 2024 2025"
                        instrucao_ia = f"Sua missão é atuar como um buscador. Identifique no contexto web ou na sua memória questões REAIS que já foram cobradas pela banca {banca_alvo} para {cargo_alvo}. Não invente, traga a questão literal."

                    contexto_da_web = pesquisar_na_web(termo_busca)

                    prompt = f"""
                    Atue como um examinador sênior de concursos de alto rendimento.
                    
                    DADOS DA BUSCA EM TEMPO REAL:
                    {contexto_da_web}
                    
                    MISSÃO:
                    Gere exatamente {qtd} questão(ões).
                    Cargo: {cargo_alvo} | Matéria: {mat_final} | Tema: {instrucao_tema}
                    
                    DIRETRIZES TÉCNICAS E JURÍDICAS:
                    1. {instrucao_ia}
                    2. FORMATO OBRIGATÓRIO: A prova será no formato '{formato_alvo}'. 
                       - Se for "Múltipla Escolha (A a E)", crie exatamente 5 alternativas (A, B, C, D, E) no campo 'alternativas'.
                       - Se for "Múltipla Escolha (A a D)", crie exatamente 4 alternativas (A, B, C, D) no campo 'alternativas'.
                       - Se for "Certo / Errado", crie uma afirmativa única para julgamento e deixe o objeto 'alternativas' VAZIO {{}}.
                    3. RIGOR BRASILEIRO: O gabarito e a explicação DEVEM respeitar estritamente a legislação brasileira vigente e as normas brasileiras. Jamais invente jurisprudência.
                    4. FONTE OBRIGATÓRIA: O campo "fonte" é sagrado. Preencha SEMPRE com o formato: "[Banca] - [Ano] - [Órgão/Cargo]".
                    
                    Responda em JSON, EXATAMENTE assim:
                    {{
                      "questoes": [
                        {{
                          "enunciado": "Texto da questão",
                          "alternativas": {{"A": "...", "B": "...", "C": "..."}}, // Vazio se Certo/Errado
                          "gabarito": "Letra correta ou Certo/Errado",
                          "explicacao": "Fundamentação jurídica detalhada indicando a norma/lei.",
                          "fonte": "[Banca] - [Ano] - [Cargo/Órgão]"
                        }}
                      ]
                    }}
                    """

                    try:
                        resposta = client.chat.completions.create(
                            messages=[{"role": "user", "content": prompt}],
                            model="llama-3.3-70b-versatile",
                            temperature=0.2,
                            response_format={"type": "json_object"}
                        )
                        
                        dados_json = json.loads(resposta.choices[0].message.content.replace("```json", "").replace("```", "").strip())
                        lista_questoes = dados_json.get("questoes", [])
                        if not lista_questoes and isinstance(dados_json, list): lista_questoes = dados_json
                        
                        novas_ids = []
                        for dados in lista_questoes:
                            enunciado = dados.get("enunciado", "N/A")
                            gabarito = dados.get("gabarito", "N/A")
                            explicacao = dados.get("explicacao", "N/A")
                            fonte = dados.get("fonte", f"{banca_alvo} - Ano Recente - {cargo_alvo}")
                            alternativas = json.dumps(dados.get("alternativas", {}))

                            c.execute("""
                            INSERT INTO questoes (banca, cargo, materia, tema, enunciado, alternativas, gabarito, explicacao, tipo, fonte)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (banca_alvo, cargo_alvo, mat_final, tema_selecionado, enunciado, alternativas, gabarito, explicacao, tipo, fonte))
                            novas_ids.append(c.lastrowid)
                        
                        conn.commit()
                        st.session_state.bateria_atual = novas_ids
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro na extração de dados: {e}")

    # --- RESOLUÇÃO ---
    if st.session_state.bateria_atual:
        st.write("---")
        st.subheader("🎯 Caderno de Prova")
        
        df_respostas = pd.read_sql_query(f"SELECT questao_id, resposta_usuario, acertou FROM respostas WHERE usuario = '{st.session_state.usuario_atual}' AND questao_id IN ({','.join(map(str, st.session_state.bateria_atual))})", conn)
        respondidas = df_respostas.set_index('questao_id').to_dict('index')

        for i, q_id in enumerate(st.session_state.bateria_atual):
            c.execute("SELECT banca, cargo, materia, enunciado, alternativas, gabarito, explicacao, fonte FROM questoes WHERE id = ?", (q_id,))
            dados = c.fetchone()
            
            if dados:
                q_banca, q_cargo, q_mat, q_enun, q_alt, q_gab, q_exp, q_fonte = dados
                alts = json.loads(q_alt) if q_alt else {}
                
                with st.container(border=True):
                    st.caption(f"**Item {i+1}** | {q_mat} | 🏢 {q_banca} | 💼 {q_cargo} | 🏷️ **Fonte:** {q_fonte}")
                    st.markdown(f"#### {q_enun}")
                    
                    opcoes = ["Selecionar..."] + ([f"{letra}) {texto}" for letra, texto in alts.items()] if alts else ["Certo", "Errado"])

                    if q_id in respondidas:
                        status = respondidas[q_id]
                        if status['acertou'] == 1: st.success(f"✅ Marcado: **{status['resposta_usuario']}** (Correto)")
                        else: st.error(f"❌ Marcado: **{status['resposta_usuario']}** (Incorreto)")
                            
                        st.info(f"**Gabarito Oficial:** {q_gab}")
                        with st.expander("📖 Fundamentação Legal"): st.write(q_exp)
                    else:
                        st.write("")
                        resp = st.radio("Sua Resposta:", opcoes, key=f"rad_{q_id}", label_visibility="collapsed")
                        
                        if st.button("Confirmar Resposta", key=f"btn_{q_id}"):
                            if resp != "Selecionar...":
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
