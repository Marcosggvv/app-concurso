import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import json
import random
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
    .alt-correta { padding: 10px; background-color: #d4edda; border-left: 5px solid #28a745; border-radius: 5px; margin-bottom: 5px; }
    .alt-errada { padding: 10px; background-color: #f8d7da; border-left: 5px solid #dc3545; border-radius: 5px; margin-bottom: 5px; }
    .alt-neutra { padding: 10px; border-left: 5px solid #e9ecef; margin-bottom: 5px; color: #495057; }
    .alt-gabarito { padding: 10px; background-color: #cce5ff; border-left: 5px solid #004085; border-radius: 5px; margin-bottom: 5px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# ================= CHAVE DEEPSEEK =================
client = OpenAI(api_key=st.secrets["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")

# ================= AGENTE DE BUSCA SNIPER =================
def pesquisar_na_web(query, focar_em_bancos_de_questoes=False):
    try:
        ddgs = DDGS()
        if focar_em_bancos_de_questoes:
            query_otimizada = f'{query} (site:qconcursos.com OR site:tecconcursos.com.br OR site:grancursosonline.com.br)'
            resultados = ddgs.text(query_otimizada, max_results=12)
        else:
            resultados = ddgs.text(query, max_results=8)
            
        contexto = "\n".join([f"- {r['body']}" for r in resultados])
        return contexto if contexto else "Nenhum dado real encontrado na web para estes parâmetros."
    except Exception as e:
        return "Alerta: Busca web indisponível. Utilize apenas a memória consolidada."

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
            nome_novo = st.text_input("Nome do Concurso (Ex: PCDF):")
            banca_nova = st.text_input("Banca Examinadora (Ex: Cebraspe):")
            cargo_novo = st.text_input("Cargo (Ex: Delegado):")
            texto_colado = st.text_area("Cole o texto do Conteúdo Programático aqui:")

            if st.button("Salvar Edital no Perfil", use_container_width=True) and nome_novo and texto_colado:
                with st.spinner("Estruturando matérias com precisão DeepSeek..."):
                    prompt = f"""
                    Leia o texto colado abaixo e liste APENAS os nomes das grandes áreas ou disciplinas.
                    Responda EXCLUSIVAMENTE em formato JSON:
                    {{"materias": ["Disciplina 1", "Disciplina 2"]}}
                    Texto: {texto_colado[:15000]}
                    """
                    try:
                        resposta = client.chat.completions.create(
                            messages=[{"role": "user", "content": prompt}],
                            model="deepseek-chat",
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
            st.success("O histórico de desempenho foi apagado!")
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
            st.warning("Carregue um edital na barra lateral para aplicar o filtro de rigor.")
            c1, c2, c3 = st.columns(3)
            with c1: banca_alvo = st.text_input("Banca", "Cebraspe")
            with c2: cargo_alvo = st.text_input("Cargo", "Delegado")
            with c3: mat_selecionada = st.text_input("Matéria", "Direito Penal")
            tema_selecionado = st.text_input("Tema específico", "Aleatório")

        c3, c4, c5 = st.columns([2, 2, 1])
        with c3: 
            tipo = st.selectbox("Origem do Material", [
                "🧠 Inédita IA (Pesquisa Jurídica Atualizada)", 
                "🌐 Questões Reais (Auditoria e Transcrição Fiel)",
                "📂 Revisão (Sortear banco local)"
            ])
        with c4:
            formato_alvo = st.selectbox("Formato (Apenas p/ Inéditas)", [
                "Múltipla Escolha (A a E)", 
                "Múltipla Escolha (A a D)", 
                "Certo / Errado"
            ])
        with c5: 
            qtd = st.slider("Quantidade", 1, 10, 5)

        if st.button("Forjar Simulado", type="primary", use_container_width=True):
            mat_final = random.choice(e['materias']) if mat_selecionada == "Aleatório" and st.session_state.edital_ativo else mat_selecionada
            instrucao_tema = f"Sorteie um tema complexo em {mat_final}" if tema_selecionado.lower() == "aleatório" else tema_selecionado

            if "Revisão" in tipo:
                st.info("A resgatar histórico do banco local...")
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
                    st.warning("Banco local insuficiente. Gere material Inédito ou Real primeiro!")

            else:
                with st.spinner(f"Acionando Motor DeepSeek e Protocolo de Auditoria para {cargo_alvo} ({banca_alvo})..."):
                    
                    if "Inédita" in tipo:
                        query_questao = f"jurisprudencia STF STJ lei atualizada 2025 2026 {mat_final} {tema_selecionado}"
                        contexto_da_web = pesquisar_na_web(query_questao, focar_em_bancos_de_questoes=False)
                        
                        instrucao_ia = f"Crie questões INÉDITAS mimetizando o rigor da banca {banca_alvo} para o cargo de {cargo_alvo}."
                        
                        if formato_alvo == "Múltipla Escolha (A a E)":
                            regras_json_alt = '"alternativas": {"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."}'
                        elif formato_alvo == "Múltipla Escolha (A a D)":
                            regras_json_alt = '"alternativas": {"A": "...", "B": "...", "C": "...", "D": "..."}'
                        else:
                            regras_json_alt = '"alternativas": {} // DEVE SER EXATAMENTE UM DICIONÁRIO VAZIO'
                            
                        instrucao_formato = f"FORMATO IMPERATIVO: Respeite o formato '{formato_alvo}'."
                        instrucao_fonte = 'Preencha SEMPRE com "Inédita IA - Estilo [Banca] - [Ano]"'
                    
                    else:
                        query_questao = f'"{banca_alvo}" "{cargo_alvo}" "{mat_final}" "{tema_selecionado}"'
                        contexto_da_web = pesquisar_na_web(query_questao, focar_em_bancos_de_questoes=True)
                        
                        instrucao_ia = f"""
                        ATUAÇÃO: AUDITOR DE PROVAS.
                        Sua única função é EXTRAIR questões reais do contexto web fornecido ou da sua memória consolidada.
                        REGRA DE OURO: É TERMINANTEMENTE PROIBIDO inventar um ano, um órgão ou um concurso falso.
                        """
                        regras_json_alt = '"alternativas": {"A": "...", "B": "..."} // Copie as alternativas EXATAMENTE como na prova original, ou deixe vazio se for Certo/Errado.'
                        instrucao_formato = "FORMATO ORIGINAL: MANTENHA a formatação original da prova real, ignorando a preferência do usuário."
                        instrucao_fonte = """
                        MANDATÓRIO PARA A FONTE: 
                        1. Se você tem 100% de certeza do concurso, escreva "[Banca] - [Ano] - [Órgão] - [Cargo]".
                        2. Se você sabe que a questão é real, mas não tem certeza do ano ou órgão, escreva "Banco Histórico [Banca] - Ano/Órgão Desconhecido".
                        3. Se você NÃO achou uma prova real para este tema/cargo, você DEVE assumir e escrever na fonte: "Questão Inédita (Mimetizada) - Origem Real Não Localizada". JAMAIS INVENTE UM CABEÇALHO.
                        """

                    prompt = f"""
                    Atue sob o Protocolo de Rigor Máximo Brasileiro.
                    
                    DADOS COLETADOS NA WEB (AUDITORIA):
                    {contexto_da_web}
                    
                    MISSÃO:
                    Entregue {qtd} questão(ões).
                    Cargo: {cargo_alvo} | Banca: {banca_alvo} | Matéria: {mat_final} | Tema: {instrucao_tema}
                    
                    DIRETRIZES TÉCNICAS:
                    1. {instrucao_ia}
                    2. {instrucao_formato}
                    3. BASE JURÍDICA: Gabarito e explicação obrigatoriamente fundamentados na legislação/jurisprudência brasileira real.
                    4. {instrucao_fonte}
                    
                    Responda em JSON, EXATAMENTE assim:
                    {{
                      "questoes": [
                        {{
                          "enunciado": "Texto da questão",
                          {regras_json_alt},
                          "gabarito": "Letra correta ou Certo/Errado",
                          "explicacao": "Fundamentação legal baseada no ordenamento brasileiro.",
                          "fonte": "Instrução de fonte validada"
                        }}
                      ]
                    }}
                    """

                    try:
                        resposta = client.chat.completions.create(
                            messages=[{"role": "user", "content": prompt}],
                            model="deepseek-chat",
                            temperature=0.0,
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
                            fonte = dados.get("fonte", "Erro de Extração")
                            alts_dict = dados.get("alternativas", {})
                            
                            if "Inédita" in tipo:
                                if "Certo" in formato_alvo:
                                    alts_dict = {} 
                                elif "A a D" in formato_alvo:
                                    alts_dict = {k: v for k, v in alts_dict.items() if k in ["A", "B", "C", "D"]}
                                    
                            alternativas = json.dumps(alts_dict)

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
                    if "Inédita (Mimetizada)" in q_fonte:
                        st.error(f"⚠️ **Atenção:** A inteligência artificial não localizou uma prova original com os critérios exatos exigidos na rede. A questão abaixo foi forjada no estilo da banca para evitar que o simulado ficasse vazio.")
                    
                    st.caption(f"**Item {i+1}** | 📚 {q_mat} | 🏷️ **Origem da Questão:** {q_fonte}")
                    st.markdown(f"#### {q_enun}")
                    
                    opcoes = ["Selecionar..."] + ([f"{letra}) {texto}" for letra, texto in alts.items()] if alts else ["Certo", "Errado"])

                    if q_id in respondidas:
                        status = respondidas[q_id]
                        
                        st.markdown("<br><b>Análise das Alternativas:</b>", unsafe_allow_html=True)
                        for opcao in opcoes[1:]:
                            letra_opcao = opcao.split(")")[0].strip().upper() if alts else opcao.strip().upper()
                            gab_oficial = str(q_gab).strip().upper()
                            
                            is_resposta_usuario = (status['resposta_usuario'] == letra_opcao)
                            is_gabarito = (letra_opcao in gab_oficial or gab_oficial in letra_opcao)
                            
                            if is_resposta_usuario:
                                if status['acertou'] == 1:
                                    st.markdown(f"<div class='alt-correta'>✅ <b>{opcao}</b> (Resposta Correta)</div>", unsafe_allow_html=True)
                                else:
                                    st.markdown(f"<div class='alt-errada'>❌ <b>{opcao}</b> (Sua Resposta)</div>", unsafe_allow_html=True)
                            elif is_gabarito and status['acertou'] == 0:
                                st.markdown(f"<div class='alt-gabarito'>🎯 <b>{opcao}</b> (Gabarito Oficial)</div>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"<div class='alt-neutra'>{opcao}</div>", unsafe_allow_html=True)

                        st.write("<br>", unsafe_allow_html=True)
                        with st.expander("📖 Fundamentação Legal e Correção"): 
                            st.write(q_exp)
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
