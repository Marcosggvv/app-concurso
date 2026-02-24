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
    </style>
""", unsafe_allow_html=True)

# ================= MAPEAMENTO DE DIFICULDADE POR CARGO =================
PERFIL_CARGO_DIFICULDADE = {
    "Juiz": {"nível": 5, "descrição": "Muito Difícil", "características": ["jurisprudência complexa", "precedentes conflitantes", "interpretação doutrinária", "casos reais polêmicos"]},
    "Procurador da República": {"nível": 5, "descrição": "Muito Difícil", "características": ["conhecimento aprofundado", "jurisprudência recente", "constitucionalismo", "ADIN/ADC"]},
    "Juiz de Direito": {"nível": 5, "descrição": "Muito Difícil", "características": ["jurisprudência consolidada", "súmulas e precedentes", "casos jurisprudenciais reais"]},
    "Delegado de Polícia": {"nível": 4, "descrição": "Difícil", "características": ["processual penal", "direitos humanos", "procedimentos investigativos", "jurisprudência aplicada"]},
    "Delegado da PF": {"nível": 4, "descrição": "Difícil", "características": ["criminalística", "direito penal econômico", "legislação federal"]},
    "Analista": {"nível": 3, "descrição": "Médio", "características": ["conceitos bem definidos", "legislação objetiva", "procedimentos padrão"]},
    "Assistente": {"nível": 2, "descrição": "Fácil a Médio", "características": ["conceitos básicos", "operações simples", "legislação clara"]},
    "Oficial": {"nível": 2, "descrição": "Fácil a Médio", "características": ["procedimentos operacionais", "legislação direta"]},
    "Policial": {"nível": 2, "descrição": "Fácil a Médio", "características": ["procedimentos práticos", "legislação funcional"]},
}

# ================= CHAVES DE IA =================
try:
    client_groq = Groq(api_key=st.secrets["GROQ_API_KEY"])
    client_deepseek = OpenAI(api_key=st.secrets["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
except Exception as e:
    st.error("Erro ao carregar as chaves de API. Verifique os Segredos no Streamlit.")

# ================= AGENTE DE BUSCA SNIPER OTIMIZADO =================
def pesquisar_na_web(query, focar_em_bancos_de_questoes=False, adicionar_jurisprudencia=False):
    """Busca otimizada com foco em jurisprudência se necessário."""
    try:
        ddgs = DDGS()
        
        if adicionar_jurisprudencia:
            # Para cargos de alta dificuldade, prioriza jurisprudência
            query_otimizada = f'{query} (site:stf.jus.br OR site:tjdft.jus.br OR site:stj.jus.br OR "jurisprudência" OR "precedente")'
            resultados = ddgs.text(query_otimizada, max_results=6)
        elif focar_em_bancos_de_questoes:
            query_otimizada = f'{query} (site:qconcursos.com OR site:tecconcursos.com.br OR site:questoesdeconcurso.com.br)'
            resultados = ddgs.text(query_otimizada, max_results=5)
        else:
            resultados = ddgs.text(query, max_results=4)
            
        contexto = "\n".join([f"- {r['body']}" for r in resultados])
        return contexto[:5000] if contexto else "Nenhum dado encontrado."
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
        explicacao TEXT, tipo TEXT, fonte TEXT,
        dificuldade INTEGER, tags TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS respostas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT, questao_id INTEGER, resposta_usuario TEXT,
        acertou INTEGER, data TEXT, tempo_resposta INTEGER
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS editais_salvos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT, nome_concurso TEXT, banca TEXT, cargo TEXT,
        dados_json TEXT, data_analise TEXT, nivel_dificuldade INTEGER
    )
    """)
    
    # Adicionar coluna dificuldade se não existir
    try:
        c.execute("ALTER TABLE questoes ADD COLUMN dificuldade INTEGER DEFAULT 3")
        c.execute("ALTER TABLE questoes ADD COLUMN tags TEXT DEFAULT '[]'")
        conn.commit()
    except:
        pass
    
    conn.commit()
    return conn

conn = iniciar_conexao()
c = conn.cursor()

# ================= INICIALIZAÇÃO DE MEMÓRIA =================
if "usuario_atual" not in st.session_state: st.session_state.usuario_atual = None
if "bateria_atual" not in st.session_state: st.session_state.bateria_atual = []
if "edital_ativo" not in st.session_state: st.session_state.edital_ativo = None

# ================= FUNÇÕES AUXILIARES DE DIFICULDADE =================
def obter_perfil_cargo(cargo_nome):
    """Retorna o perfil de dificuldade para um cargo."""
    for chave, valor in PERFIL_CARGO_DIFICULDADE.items():
        if chave.lower() in cargo_nome.lower() or cargo_nome.lower() in chave.lower():
            return valor
    return {"nível": 3, "descrição": "Médio", "características": ["Padrão"]}

def gerar_prompt_com_dificuldade(qtd, banca_alvo, cargo_alvo, mat_final, tema_selecionado, 
                                  tipo, formato_alvo, contexto_da_web, motor_escolhido):
    """Gera prompt com instruções detalhadas de dificuldade."""
    
    perfil = obter_perfil_cargo(cargo_alvo)
    nivel_dif = perfil["nível"]
    descricao_dif = perfil["descrição"]
    caracteristicas = ", ".join(perfil["características"])
    
    if "Inédita" in tipo:
        instrucao_ia = f"""
        Crie questões INÉDITAS que MIMETIZEM o padrão da banca {banca_alvo} para o cargo de {cargo_alvo}.
        
        NÍVEL DE DIFICULDADE: {descricao_dif} (Nível {nivel_dif}/5)
        CARACTERÍSTICAS ESPERADAS: {caracteristicas}
        
        Diretivas de Complexidade:
        - Para NÍVEL 4-5 (Juiz/Procurador): Use jurisprudência complexa, precedentes conflitantes, 
          interpretações doutrinárias. Inclua "pegadinhas" sutis baseadas em jurisprudência recente.
        - Para NÍVEL 3 (Analista): Use conceitos bem definidos, legislação objetiva, procedimentos padrão.
        - Para NÍVEL 1-2 (Polícia/Assistente): Use procedimentos diretos, legislação clara, conceitos básicos.
        
        CONTEXTO JURISPRUDENCIAL: {contexto_da_web if contexto_da_web != "PESQUISA WEB DESATIVADA" else "Use sua memória consolidada"}
        """
        
        if formato_alvo == "Múltipla Escolha (A a E)": 
            regras_json_alt = '"alternativas": {"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."}'
        elif formato_alvo == "Múltipla Escolha (A a D)": 
            regras_json_alt = '"alternativas": {"A": "...", "B": "...", "C": "...", "D": "..."}'
        else: 
            regras_json_alt = '"alternativas": {}'
            
        instrucao_formato = f"FORMATO: {formato_alvo}"
        instrucao_fonte = 'Preencha com "Inédita IA - Estilo [Banca] - Nível [' + descricao_dif + ']"'
    else:
        instrucao_ia = f"""
        TRANSCREVA questões REAIS da banca {banca_alvo} para o cargo de {cargo_alvo}.
        Cargo: {cargo_alvo} | Banca: {banca_alvo} | Nível Esperado: {descricao_dif}
        Busque questões que reflitam o nível realmente cobrado pela banca, não simplifique.
        """
        regras_json_alt = '"alternativas": {"A": "...", "B": "..."} // Use o formato original da prova.'
        instrucao_formato = "MANTENHA a formatação original da prova real."
        instrucao_fonte = f'MANDATÓRIO: "[Banca] - [Ano] - [Órgão] - [Cargo]". Se desconhecido: "Banco [Banca] - Nível {descricao_dif}"'

    prompt = f"""
    Atue sob o Protocolo de Rigor Máximo Brasileiro com foco em DIFICULDADE REALISTA.
    
    {instrucao_ia}
    
    MISSÃO: Entregue {qtd} questão(ões) com dificuldade consistente.
    Matéria: {mat_final} | Tema: {tema_selecionado}
    
    DIRETRIZES IMPERATIVAS:
    1. {instrucao_formato}
    2. BASE JURÍDICA: Gabarito fundamentado no ordenamento brasileiro e jurisprudência vigente.
    3. ANATOMIA DO ERRO: NO CAMPO 'comentarios', SEMPRE explique por que CADA alternativa está certa/errada.
       - Alternativas erradas devem ter explicações que as diferenciem sutilmente da correta.
       - Para NÍVEL 4-5: Inclua referência a jurisprudência ou súmulas.
    4. {instrucao_fonte}
    5. VALIDAÇÃO DE DIFICULDADE: Esta questão está realmente no nível {descricao_dif}? Se não, REESCREVA.
    
    JSON EXATO:
    {{
      "questoes": [
        {{
          "enunciado": "Texto claro e objetivo da questão",
          {regras_json_alt},
          "gabarito": "Letra ou Certo/Errado",
          "explicacao": "Fundamentação legal e jurisprudencial geral da questão.",
          "comentarios": {{"A": "Por que está certa/errada", "B": "Por que está certa/errada"}},
          "fonte": "Instrução de fonte validada",
          "dificuldade": {nivel_dif},
          "tags": ["jurisprudência", "conceitual"] // Tags relevantes
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
                st.session_state.edital_ativo = {
                    "nome_concurso": linha_selecionada['nome_concurso'],
                    "banca": linha_selecionada['banca'],
                    "cargo": linha_selecionada['cargo'],
                    "materias": json.loads(linha_selecionada['dados_json'])['materias'],
                    "nivel_dificuldade": perfil_cargo_detectado["nível"]
                }
                st.success(f"✅ Edital carregado! Nível: {perfil_cargo_detectado['descrição']}")
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
                    perfil = obter_perfil_cargo(cargo_novo)
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
                        c.execute("""
                        INSERT INTO editais_salvos (usuario, nome_concurso, banca, cargo, dados_json, data_analise, nivel_dificuldade)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (st.session_state.usuario_atual, nome_novo, banca_nova, cargo_novo, texto_json, str(datetime.now()), perfil["nível"]))
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
            nivel_dificuldade_auto = e.get('nivel_dificuldade', 3)
            perfil_cargo = obter_perfil_cargo(cargo_alvo)
            
            st.caption(f"🎯 **Foco Atual:** {e['nome_concurso']} | **Banca:** {banca_alvo} | **Cargo:** {cargo_alvo}")
            st.markdown(f"<span class='dificuldade-badge dif-{'dificil' if nivel_dificuldade_auto >= 4 else 'medio' if nivel_dificuldade_auto >= 3 else 'facil'}'>Nível: {perfil_cargo['descrição']}</span>", unsafe_allow_html=True)
            
            lista_materias = ["Aleatório"] + e['materias']
            c1, c2 = st.columns(2)
            with c1: mat_selecionada = st.selectbox("Escolha a Matéria", lista_materias)
            with c2: tema_selecionado = st.text_input("Tema específico (ou deixe Aleatório)", "Aleatório")
        else:
            st.warning("Carregue um edital na barra lateral para aplicar o filtro automático.")
            c1, c2, c3 = st.columns(3)
            with c1: banca_alvo = st.text_input("Banca", "Cebraspe")
            with c2: cargo_alvo = st.text_input("Cargo", "Delegado")
            with c3: mat_selecionada = st.text_input("Matéria", "Direito Penal")
            tema_selecionado = st.text_input("Tema específico", "Aleatório")
            nivel_dificuldade_auto = 3

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
            
        usar_web = st.checkbox("🌐 Usar Pesquisa na Web (Maior precisão)", value=False)

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
                        perfil = obter_perfil_cargo(cargo_alvo)
                        query_edital = f'"{banca_alvo}" "{cargo_alvo}" concurso edital'
                        
                        if "Inédita" in tipo:
                            if perfil["nível"] >= 4:
                                # Para cargos altos, busca jurisprudência
                                query_questao = f"jurisprudência {mat_final} {tema_selecionado} STF STJ"
                                contexto_da_web = pesquisar_na_web(query_questao, adicionar_jurisprudencia=True)
                            else:
                                query_questao = f"legislação {mat_final} {tema_selecionado}"
                                contexto_da_web = pesquisar_na_web(query_questao, focar_em_bancos_de_questoes=False)
                        else:
                            query_questao = f'"{banca_alvo}" "{cargo_alvo}" "{mat_final}" "{tema_selecionado}"'
                            contexto_da_web = pesquisar_na_web(query_questao, focar_em_bancos_de_questoes=True)

                    # Gera prompt com dificuldade
                    prompt = gerar_prompt_com_dificuldade(
                        qtd, banca_alvo, cargo_alvo, mat_final, instrucao_tema,
                        tipo, formato_alvo, contexto_da_web, motor_escolhido
                    )

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
                                max_tokens=4000
                            )
                        
                        dados_json = json.loads(resposta.choices[0].message.content.replace("```json", "").replace("```", "").strip())
                        lista_questoes = dados_json.get("questoes", [])
                        if not lista_questoes and isinstance(dados_json, list): lista_questoes = dados_json
                        
                        novas_ids = []
                        for dados in lista_questoes:
                            enunciado = dados.get("enunciado", "N/A")
                            gabarito = dados.get("gabarito", "N/A")
                            fonte = dados.get("fonte", "Fonte Pendente")
                            dificuldade = dados.get("dificuldade", nivel_dificuldade_auto)
                            tags = json.dumps(dados.get("tags", []))
                            alts_dict = dados.get("alternativas", {})
                            
                            if "Inédita" in tipo:
                                if "Certo" in formato_alvo: alts_dict = {} 
                                elif "A a D" in formato_alvo: alts_dict = {k: v for k, v in alts_dict.items() if k in ["A", "B", "C", "D"]}
                            alternativas = json.dumps(alts_dict)

                            explicacao_texto = dados.get("explicacao", "N/A")
                            comentarios_dict = dados.get("comentarios", {})
                            explicacao_final = json.dumps({"geral": explicacao_texto, "detalhes": comentarios_dict})

                            c.execute("""
                            INSERT INTO questoes (banca, cargo, materia, tema, enunciado, alternativas, gabarito, explicacao, tipo, fonte, dificuldade, tags)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (banca_alvo, cargo_alvo, mat_final, tema_selecionado, enunciado, alternativas, gabarito, explicacao_final, tipo, fonte, dificuldade, tags))
                            novas_ids.append(c.lastrowid)
                        
                        conn.commit()
                        st.session_state.bateria_atual = novas_ids
                        st.rerun()
                        
                    except Exception as e:
                        if "rate_limit_exceeded" in str(e).lower() or "429" in str(e):
                            st.error("⚠️ **O limite diário do Groq foi atingido!** Use o motor **DeepSeek** para continuar.")
                        else:
                            st.error(f"Erro na geração: {e}")

    # --- RESOLUÇÃO ---
    if st.session_state.bateria_atual:
        st.write("---")
        st.subheader("🎯 Caderno de Prova")
        
        df_respostas = pd.read_sql_query(f"SELECT questao_id, resposta_usuario, acertou FROM respostas WHERE usuario = '{st.session_state.usuario_atual}' AND questao_id IN ({','.join(map(str, st.session_state.bateria_atual))})", conn)
        respondidas = df_respostas.set_index('questao_id').to_dict('index')

        for i, q_id in enumerate(st.session_state.bateria_atual):
            c.execute("SELECT banca, cargo, materia, enunciado, alternativas, gabarito, explicacao, fonte, dificuldade, tags FROM questoes WHERE id = ?", (q_id,))
            dados = c.fetchone()
            
            if dados:
                q_banca, q_cargo, q_mat, q_enun, q_alt, q_gab, q_exp, q_fonte, q_dif, q_tags = dados
                alts = json.loads(q_alt) if q_alt else {}
                tags_list = json.loads(q_tags) if q_tags else []
                
                # Mapping de dificuldade para badge
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
                    if "Inédita" in q_fonte and "Reais" in tipo:
                        st.error(f"⚠️ A inteligência artificial não localizou uma prova original. A questão foi forjada no estilo da banca.")
                    
                    col_info, col_dif = st.columns([4, 1])
                    with col_info:
                        st.caption(f"**Item {i+1}** | 📚 {q_mat} | 🏷️ **Origem:** {q_fonte}")
                    with col_dif:
                        st.markdown(f"<span class='dificuldade-badge {dif_classe}'>{dif_label}</span>", unsafe_allow_html=True)
                    
                    if tags_list:
                        st.caption(f"Tags: {', '.join(tags_list)}")
                    
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

