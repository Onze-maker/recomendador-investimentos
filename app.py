import streamlit as st
import pandas as pd

st.set_page_config(page_title="Motor de Recomendação Personalizado B3", page_icon="⚙️", layout="wide")

st.title("⚙️ O 'Santo Graal': Motor Quantitativo Multi-Fatorial com Governança e Pesos Customizados")
st.markdown("Personalize a importância de cada indicador de acordo com a sua estratégia de investimento e deixe o motor otimizar a carteira ideal.")

# 1. ENTRADAS DO USUÁRIO (PERFIL E CAPITAL)
st.sidebar.header("1. Perfil e Parâmetros Macro")
capital_total = st.sidebar.number_input("Capital Disponível (R$)", min_value=100.0, value=100000.0, step=1000.0)
perfil_risco = st.sidebar.selectbox("Perfil de Risco", ["Conservador", "Moderado", "Arrojado"])
horizonte_anos = st.sidebar.slider("Horizonte de Investimento (Anos)", min_value=1, max_value=30, value=5)

# 2. PESOS CUSTOMIZÁVEIS PELO USUÁRIO (O usuário escolte o que importa mais para ele)
st.sidebar.header("2. Pesos de Importância (Atributos)")
st.sidebar.markdown("Defina de 0 a 10 o quanto você valoriza cada critério:")
peso_dy = st.sidebar.slider("Dividend Yield (Foco em Renda)", 0, 10, 8)
peso_gov = st.sidebar.slider("Governança (Ex: Novo Mercado)", 0, 10, 9)
peso_roe = st.sidebar.slider("Lucratividade e Eficiência (ROE)", 0, 10, 8)
peso_val = st.sidebar.slider("Preço Atrativo (Valuation P/L)", 0, 10, 6)
peso_sol = st.sidebar.slider("Solidez e Baixo Endividamento", 0, 10, 7)

# Normaliza os pesos para somarem 100%
soma_pesos = peso_dy + peso_gov + peso_roe + peso_val + peso_sol
if soma_pesos == 0:
    soma_pesos = 1 # Evita divisão por zero

p_dy = peso_dy / soma_pesos
p_gov = peso_gov / soma_pesos
p_roe = peso_roe / soma_pesos
p_val = peso_val / soma_pesos
p_sol = peso_sol / soma_pesos

# 3. BASE DE DADOS AMPLIADA DA B3 (Com Governança)
@st.cache_data
def carregar_base():
    return pd.DataFrame([
        # Renda Fixa
        {
            "ticker": "CDB 100% CDI Liquidez", "classe": "Renda Fixa", "risco": "Baixo", "prazo_min": 0,
            "dy": 0.11, "governanca_nivel": "N/A (Garantia FGC)", "roe": 0.0, "pl": 0.0, "pvp": 1.0, "divida_ebitda": 0.0, "patrimonio_bi": 50.0, "liquidez_diaria_mi": 1000.0
        },
        {
            "ticker": "Tesouro IPCA+ 2029", "classe": "Renda Fixa", "risco": "Baixo", "prazo_min": 2,
            "dy": 0.06, "governanca_nivel": "Soberano (Tesouro Nacional)", "roe": 0.0, "pl": 0.0, "pvp": 1.0, "divida_ebitda": 0.0, "patrimonio_bi": 1000.0, "liquidez_diaria_mi": 5000.0
        },
        # Ações
        {
            "ticker": "BBAS3 (Banco do Brasil)", "classe": "Ações", "risco": "Médio", "prazo_min": 3,
            "dy": 0.09, "governanca_nivel": "Novo Mercado", "roe": 0.21, "pl": 5.2, "pvp": 0.75, "divida_ebitda": 0.0, "patrimonio_bi": 160.0, "liquidez_diaria_mi": 150.0
        },
        {
            "ticker": "ITUB4 (Itaú Unibanco)", "classe": "Ações", "risco": "Médio", "prazo_min": 3,
            "dy": 0.05, "governanca_nivel": "Nível 1", "roe": 0.20, "pl": 9.5, "pvp": 1.6, "divida_ebitda": 0.0, "patrimonio_bi": 300.0, "liquidez_diaria_mi": 350.0
        },
        {
            "ticker": "VALE3 (Vale)", "classe": "Ações", "risco": "Alto", "prazo_min": 4,
            "dy": 0.08, "governanca_nivel": "Novo Mercado", "roe": 0.18, "pl": 6.8, "pvp": 1.2, "divida_ebitda": 0.8, "patrimonio_bi": 250.0, "liquidez_diaria_mi": 600.0
        },
        {
            "ticker": "TAEE3 (Taesa)", "classe": "Ações", "risco": "Baixo", "prazo_min": 3,
            "dy": 0.10, "governanca_nivel": "Nível 2", "roe": 0.15, "pl": 7.5, "pvp": 1.4, "divida_ebitda": 2.2, "patrimonio_bi": 12.0, "liquidez_diaria_mi": 25.0
        },
        {
            "ticker": "WEGE3 (Weg)", "classe": "Ações", "risco": "Alto", "prazo_min": 5,
            "dy": 0.025, "governanca_nivel": "Novo Mercado", "roe": 0.28, "pl": 28.0, "pvp": 5.5, "divida_ebitda": 0.2, "patrimonio_bi": 45.0, "liquidez_diaria_mi": 200.0
        },
        # FIIs
        {
            "ticker": "KNCR11 (FII Papel)", "classe": "FIIs", "risco": "Médio", "prazo_min": 2,
            "dy": 0.12, "governanca_nivel": "Gestão Profissional / Anbima", "roe": 0.0, "pl": 0.0, "pvp": 1.02, "divida_ebitda": 0.0, "patrimonio_bi": 6.0, "liquidez_diaria_mi": 15.0
        },
        {
            "ticker": "HGLG11 (FII Tijolo Logística)", "classe": "FIIs", "risco": "Médio", "prazo_min": 3,
            "dy": 0.085, "governanca_nivel": "Gestão Profissional / Anbima", "roe": 0.0, "pl": 0.0, "pvp": 1.0, "divida_ebitda": 0.0, "patrimonio_bi": 5.2, "liquidez_diaria_mi": 12.0
        }
    ])

# MOTOR DE CÁLCULO PONDERADO PELOS PESOS DO USUÁRIO
def calcular_score_personalizado(row):
    if row["classe"] == "Renda Fixa":
        return 9.0 # Nota base sólida para Renda Fixa segura
    
    # Pontuação por critério (0 a 10)
    s_dy = min(row["dy"] * 50, 10)
    
    # Governança: Novo Mercado ganha nota máxima, Nível 2 ganha 8, Nível 1 ganha 6
    if "Novo Mercado" in row["governanca_nivel"]:
        s_gov = 10.0
    elif "Nível 2" in row["governanca_nivel"]:
        s_gov = 8.0
    elif "Nível 1" in row["governanca_nivel"]:
        s_gov = 6.0
    else:
        s_gov = 5.0
        
    s_roe = min(row["roe"] * 25, 10)
    s_val = max(0, 10 - (row["pl"] / 3)) if row["pl"] > 0 else 5
    s_sol = max(0, 10 - (row["divida_ebitda"] * 2))
    
    # Aplica os pesos dinâmicos definidos pelo usuário na barra lateral
    score_final = (s_dy * p_dy) + (s_gov * p_gov) + (s_roe * p_roe) + (s_val * p_val) + (s_sol * p_sol)
    return round(score_final, 2)

def obter_alocacao(perfil):
    if perfil == "Conservador":
        return {"Renda Fixa": 0.85, "Ações": 0.05, "FIIs": 0.10}
    elif perfil == "Moderado":
        return {"Renda Fixa": 0.50, "Ações": 0.30, "FIIs": 0.20}
    else:
        return {"Renda Fixa": 0.15, "Ações": 0.60, "FIIs": 0.25}

if st.button("Calcular Carteira Otimizada por Preferências", type="primary"):
    df = carregar_base()
    df["Score_Personalizado"] = df.apply(calcular_score_personalizado, axis=1)
    
    pesos_alocacao = obter_alocacao(perfil_risco)
    carteira = []
    
    st.subheader(f"🎯 Carteira Gerada para o Perfil {perfil_risco} (Pesos Ajustados)")
    
    for classe, peso_alvo in pesos_alocacao.items():
        valor_classe = capital_total * peso_alvo
        if valor_classe == 0:
            continue
            
        candidatos = df[(df["classe"] == classe) & (df["prazo_min"] <= horizonte_anos)].copy()
        if candidatos.empty:
            candidatos = df[df["classe"] == classe].head(1)
            
        candidatos = candidatos.sort_values(by="Score_Personalizado", ascending=False)
        selecionados = candidatos.head(2)
        
        valor_por_ativo = valor_classe / len(selecionados)
        
        for _, ativo in selecionados.iterrows():
            carteira.append({
                "Classe": classe,
                "Ativo": ativo["ticker"],
                "Governança": ativo["governanca_nivel"],
                "Alvo (%)": round((peso_alvo / len(selecionados)) * 100, 2),
                "Valor (R$)": round(valor_por_ativo, 2),
                "Score Final": ativo["Score_Personalizado"],
                "DY (%)": round(ativo["dy"] * 100, 2)
            })
            
    df_res = pd.DataFrame(carteira)
    st.dataframe(df_res, use_container_width=True)
    
    # 4. PAINEL DE INSIGHTS E ALERTAS COMPORTAMENTAIS (Requisito do usuário)
    st.markdown("---")
    st.subheader("💡 Alertas e Cuidados Especializados com Base nas Suas Escolhas")
    
    if horizonte_anos >= 5 and peso_dy >= 6:
        st.warning("⚠️ **Atenção à Marcação a Mercado em Renda Fixa de Longo Prazo:** Como você escolheu um horizonte longo e priorizou ativos atrelados à inflação (como Tesouro IPCA+), lembre-se de que esses títulos sofrem variação de preço diária se você precisar resgatar antes do vencimento. O ideal é **levar até o vencimento** para garantir a taxa contratada.")
        
    if peso_dy >= 8:
        st.info("ℹ️ **Cuidado com 'Dividend Traps':** Você deu alto peso ao Dividend Yield. Lembre-se de verificar se empresas que pagam muitos dividendos não estão sacrificando o crescimento futuro ou aumentando o endividamento.")
        
    if peso_gov >= 8:
        st.success("✅ **Excelente Foco em Governança:** Priorizar ativos do *Novo Mercado* blinda sua carteira contra abusos de controladores, garantindo 100% de tag along e relatórios financeiros transparentes.")
