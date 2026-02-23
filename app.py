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
    </style>
""", unsafe_allow_html=True)

# ================= CHAVES DE IA =================
try:
    client_groq = Groq(api_key=st.secrets["GROQ_API_KEY"])
    client_deepseek = OpenAI(api_key=st.secrets["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
except Exception as e:
    st.error("Erro ao carregar as chaves de API. Verifique os Segredos no Streamlit.")

# ================= AGENTE DE BUSCA SNIPER OTIMIZADO =================
def pesquisar_na_web(query, focar_em_bancos_de_questoes=False):
    """Busca otimizada: limita o texto para economizar tokens de entrada ($$$)."""
    try:
        ddgs = DDGS()
        if focar_em_bancos_de_questoes:
            query_otimizada = f'{query} (site:qconcursos.com OR site:tecconcursos.com.br)'
            resultados = ddgs.text(query_otimizada, max_results=5)
        else:
            resultados = ddgs.text(query, max_results=4)
            
        contexto = "\n".join([f"- {r['body']}" for r in resultados])
        return contexto[:4000] if contexto else "Nenhum dado encontrado."
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

    # --- CHAVE SELETORA DE MOTOR DE IA ---
    st.header("🧠 Motor de Inteligência")
    motor_escolhido = st.radio(
        "Escolha a IA para gerar as questões:",
        ["Groq (Gratuito / Llama 3)", "DeepSeek (Premium / Custo Otimizado)"],
        captions=["Cota diária limitada", "Ilimitado sob demanda"]
    )
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
                st.success("Edital carregado!")
        else:
            st.info("A biblioteca está vazia. Adicione um edital abaixo.")

        st.write("---")
        with st.expander("➕ Cadastrar Novo Edital", expanded=True if df_editais.empty else False):
            nome_novo = st.text_input("Nome do Concurso (Ex: PCDF):")
            banca_nova = st.text_input("Banca Examinadora:")
            cargo_novo = st.text_input("Cargo:")
            texto_colado = st.text_area("Cole o texto do Conteúdo Programático:")

            if st.button("Salvar Edital no Perfil", use_container_width=True) and nome_novo and texto_colado:
                with st.spinner("Estruturando matérias..."):
                    prompt = f"""
                    Leia o texto abaixo e liste APENAS as disciplinas. Responda em JSON: {{"materias": ["Disc 1"]}}.
                    Texto: {texto_colado[:10000]}
                    """
                    try:
                        # Para estruturar edital, usa o Groq por ser mais rápido e gratuito
                        resposta = client_groq.chat.completions.create(
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
            st.caption(f"🎯 **Foco Atual:** {e['nome_concurso']} | **Banca:** {banca_alvo} | **Cargo:** {cargo_alvo}")
            
            lista_materias = ["Aleatório"] + e['materias']
            c1, c2 = st.columns(2)
            with c1: mat_selecionada = st.selectbox("Escolha a Matéria", lista_materias)
            with c2: tema_selecionado = st.text_input("Tema específico (ou deixe Aleatório)", "Aleatório")
        else:
            st.warning("Carregue um edital na barra lateral para aplicar o filtro.")
            c1, c2, c3 = st.columns(3)
            with c1: banca_alvo = st.text_input("Banca", "Cebraspe")
            with c2: cargo_alvo = st.text_input("Cargo", "Delegado")
            with c3: mat_selecionada = st.text_input("Matéria", "Direito Penal")
            tema_selecionado = st.text_input("Tema específico", "Aleatório")

        c3, c4, c5 = st.columns([2, 2, 1])
        with c3: 
            tipo = st.selectbox("Origem do Material", [
                "🧠 Inédita IA", 
                "🌐 Questões Reais",
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
            
        usar_web = st.checkbox("🌐 Usar Pesquisa na Web (Maior precisão, consome tokens)", value=False)

        if st.button("Forjar Simulado", type="primary", use_container_width=True):
            mat_final = random.choice(e['materias']) if mat_selecionada == "Aleatório" and st.session_state.edital_ativo else mat_selecionada
            instrucao_tema = f"Sorteie um tema complexo em {mat_final}" if tema_selecionado.lower() == "aleatório" else tema_selecionado

            if "Revisão" in tipo:
                st.info("A resgatar histórico do banco local (Custo: $0.00)...")
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
                with st.spinner(f"Conectando ao motor {motor_escolhido.split(' ')[0]} e dissecando alternativas..."):
                    
                    contexto_da_web = "PESQUISA WEB DESATIVADA PELO USUÁRIO. USE APENAS SUA MEMÓRIA."
                    
                    if usar_web:
                        query_edital = f'"{banca_alvo}" "{cargo_alvo}" concurso edital'
                        if "Inédita" in tipo:
                            query_questao = f"jurisprudencia atualizada {mat_final} {tema_selecionado}"
                            contexto_da_web = pesquisar_na_web(query_questao, focar_em_bancos_de_questoes=False)
                        else:
                            query_questao = f'"{banca_alvo}" "{cargo_alvo}" "{mat_final}" "{tema_selecionado}"'
                            contexto_da_web = pesquisar_na_web(query_questao, focar_em_bancos_de_questoes=True)

                    if "Inédita" in tipo:
                        instrucao_ia = f"Crie questões INÉDITAS mimetizando o nível da banca {banca_alvo} para {cargo_alvo}."
                        if formato_alvo == "Múltipla Escolha (A a E)": regras_json_alt = '"alternativas": {"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."}'
                        elif formato_alvo == "Múltipla Escolha (A a D)": regras_json_alt = '"alternativas": {"A": "...", "B": "...", "C": "...", "D": "..."}'
                        else: regras_json_alt = '"alternativas": {}'
                        instrucao_formato = f"FORMATO IMPERATIVO: Respeite o formato '{formato_alvo}'."
                        instrucao_fonte = 'Preencha com "Inédita IA - Estilo [Banca]"'
                    else:
                        instrucao_ia = f"TRANSCREVA questões REAIS da banca {banca_alvo} para o cargo de {cargo_alvo} baseando-se na sua memória interna ou web."
                        regras_json_alt = '"alternativas": {"A": "...", "B": "..."} // Use o formato original da prova.'
                        instrucao_formato = "MANTENHA a formatação original da prova real."
                        instrucao_fonte = 'MANDATÓRIO: Se souber a origem, escreva "[Banca] - [Ano] - [Órgão] - [Cargo]". Se não, "Banco Histórico [Banca] - Origem Exata Desconhecida". NÃO INVENTE ANO.'

                    prompt = f"""
                    Atue sob o Protocolo de Rigor Máximo Brasileiro.
                    CONTEXTO WEB: {contexto_da_web}
                    MISSÃO: Entregue {qtd} questão(ões). Cargo: {cargo_alvo} | Banca: {banca_alvo} | Matéria: {mat_final} | Tema: {instrucao_tema}
                    DIRETRIZES:
                    1. {instrucao_ia}
                    2. {instrucao_formato}
                    3. BASE JURÍDICA: Gabarito fundamentado no ordenamento brasileiro.
                    4. ANATOMIA DO ERRO: No campo 'comentarios', você DEVE explicar breve e objetivamente por que CADA alternativa está errada ou certa.
                    5. {instrucao_fonte}
                    
                    JSON EXATO:
                    {{
                      "questoes": [
                        {{
                          "enunciado": "Texto da questão",
                          {regras_json_alt},
                          "gabarito": "Letra ou Certo/Errado",
                          "explicacao": "Fundamentação legal geral da questão.",
                          "comentarios": {{"A": "Por que está certa/errada", "B": "Por que está certa/errada"}},
                          "fonte": "Instrução de fonte validada"
                        }}
                      ]
                    }}
                    """

                    try:
                        # ROTEAMENTO DE MOTOR DE IA
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
                                max_tokens=3000
                            )
                        
                        dados_json = json.loads(resposta.choices[0].message.content.replace("```json", "").replace("```", "").strip())
                        lista_questoes = dados_json.get("questoes", [])
                        if not lista_questoes and isinstance(dados_json, list): lista_questoes = dados_json
                        
                        novas_ids = []
                        for dados in lista_questoes:
                            enunciado = dados.get("enunciado", "N/A")
                            gabarito = dados.get("gabarito", "N/A")
                            fonte = dados.get("fonte", "Fonte Pendente")
                            alts_dict = dados.get("alternativas", {})
                            
                            if "Inédita" in tipo:
                                if "Certo" in formato_alvo: alts_dict = {} 
                                elif "A a D" in formato_alvo: alts_dict = {k: v for k, v in alts_dict.items() if k in ["A", "B", "C", "D"]}
                            alternativas = json.dumps(alts_dict)

                            explicacao_texto = dados.get("explicacao", "N/A")
                            comentarios_dict = dados.get("comentarios", {})
                            explicacao_final = json.dumps({"geral": explicacao_texto, "detalhes": comentarios_dict})

                            c.execute("""
                            INSERT INTO questoes (banca, cargo, materia, tema, enunciado, alternativas, gabarito, explicacao, tipo, fonte)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (banca_alvo, cargo_alvo, mat_final, tema_selecionado, enunciado, alternativas, gabarito, explicacao_final, tipo, fonte))
                            novas_ids.append(c.lastrowid)
                        
                        conn.commit()
                        st.session_state.bateria_atual = novas_ids
                        st.rerun()
                        
                    except Exception as e:
                        if "rate_limit_exceeded" in str(e).lower() or "429" in str(e):
                            st.error("⚠️ **O limite diário do Groq foi atingido!** Por favor, vá à barra lateral e mude a chave seletora para o motor **DeepSeek** para continuar gerando o seu simulado.")
                        else:
                            st.error(f"Erro na geração: {e}")

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
                    if "Inédita" in q_fonte and "Reais" in tipo:
                        st.error(f"⚠️ A inteligência artificial não localizou uma prova original. A questão foi forjada no estilo da banca.")
                    
                    st.caption(f"**Item {i+1}** | 📚 {q_mat} | 🏷️ **Origem:** {q_fonte}")
                    st.markdown(f"#### {q_enun}")
                    
                    opcoes = ["Selecionar..."] + ([f"{letra}) {texto}" for letra, texto in alts.items()] if alts else ["Certo", "Errado"])

                    if q_id in respondidas:
                        status = respondidas[q_id]
                        st.markdown("<br><b>Análise Detalhada das Alternativas:</b>", unsafe_allow_html=True)
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
