import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="Motor Quantitativo B3 - Avançado", page_icon="🧠", layout="wide")

st.title("🧠 Motor Quantitativo B3: Otimização Multi-Fatorial Avançada")
st.markdown("Este motor avalia criticamente o universo da B3, aplica filtros de risco, calcula scores ponderados pelos seus pesos e garante diversificação dinâmica na carteira.")

# 1. PARÂMETROS MACRO
st.sidebar.header("1. Perfil e Parâmetros")
capital_total = st.sidebar.number_input("Capital Disponível (R$)", min_value=100.0, value=100000.0, step=1000.0)
perfil_risco = st.sidebar.selectbox("Perfil de Risco", ["Conservador", "Moderado", "Arrojado"])
horizonte_anos = st.sidebar.slider("Horizonte de Investimento (Anos)", min_value=1, max_value=30, value=5)

# 2. PESOS DE INDICADORES (SLIDERS HIPERSENSÍVEIS)
st.sidebar.header("2. Pesos e Critérios de Decisão (0 a 10)")
st.sidebar.markdown("Alterar estes pesos reorganiza o ranking e troca os ativos da carteira:")
peso_dy = st.sidebar.slider("Dividend Yield (Foco em Renda)", 0, 10, 5)
peso_roe = st.sidebar.slider("Eficiência e Retorno (ROE)", 0, 10, 5)
peso_val = st.sidebar.slider("Valuation Atrativo (P/L baixo)", 0, 10, 5)
peso_sol = st.sidebar.slider("Solidez e Baixo Endividamento", 0, 10, 5)

soma_pesos = (peso_dy + peso_roe + peso_val + peso_sol) or 1

# 3. BASE AMPLIADA DE ATIVOS REAIS DA B3 (Garante diversidade para o motor alternar)
@st.cache_data
def carregar_universo_b3():
    return pd.DataFrame([
        # --- RENDA FIXA ---
        {"ticker": "CDB 100% CDI Liquidez", "classe": "Renda Fixa", "setor": "Renda Fixa", "risco": "Baixo", "prazo_min": 0, "preco": 1.0, "dy": 0.11, "roe": 0.0, "pl": 0.0, "divida_ebitda": 0.0},
        {"ticker": "Tesouro Selic 2029", "classe": "Renda Fixa", "setor": "Renda Fixa", "risco": "Baixo", "prazo_min": 0, "preco": 13500.0, "dy": 0.106, "roe": 0.0, "pl": 0.0, "divida_ebitda": 0.0},
        {"ticker": "Tesouro IPCA+ 2029", "classe": "Renda Fixa", "setor": "Renda Fixa", "risco": "Baixo", "prazo_min": 2, "preco": 1020.0, "dy": 0.065, "roe": 0.0, "pl": 0.0, "divida_ebitda": 0.0},
        {"ticker": "Tesouro Prefixado 2031", "classe": "Renda Fixa", "setor": "Renda Fixa", "risco": "Médio", "prazo_min": 3, "preco": 850.0, "dy": 0.115, "roe": 0.0, "pl": 0.0, "divida_ebitda": 0.0},

        # --- AÇÕES - ENERGIA E UTILIDADE PÚBLICA ---
        {"ticker": "TAEE11", "classe": "Ações", "setor": "Energia", "risco": "Baixo", "prazo_min": 3, "preco": 35.50, "dy": 0.102, "roe": 0.15, "pl": 7.5, "divida_ebitda": 2.2},
        {"ticker": "CPLE6", "classe": "Ações", "setor": "Energia", "risco": "Médio", "prazo_min": 3, "preco": 10.20, "dy": 0.085, "roe": 0.14, "pl": 6.8, "divida_ebitda": 1.8},
        {"ticker": "EGIE3", "classe": "Ações", "setor": "Energia", "risco": "Baixo", "prazo_min": 3, "preco": 42.10, "dy": 0.075, "roe": 0.22, "pl": 11.2, "divida_ebitda": 1.5},
        {"ticker": "CMIG4", "classe": "Ações", "setor": "Energia", "risco": "Médio", "prazo_min": 3, "preco": 11.80, "dy": 0.090, "roe": 0.13, "pl": 5.9, "divida_ebitda": 1.2},

        # --- AÇÕES - BANCOS E FINANCEIRO ---
        {"ticker": "ITUB4", "classe": "Ações", "setor": "Bancos", "risco": "Baixo", "prazo_min": 3, "preco": 33.10, "dy": 0.052, "roe": 0.20, "pl": 9.5, "divida_ebitda": 0.0},
        {"ticker": "BBAS3", "classe": "Ações", "setor": "Bancos", "risco": "Médio", "prazo_min": 3, "preco": 27.40, "dy": 0.091, "roe": 0.21, "pl": 5.2, "divida_ebitda": 0.0},
        {"ticker": "BBDC4", "classe": "Ações", "setor": "Bancos", "risco": "Médio", "prazo_min": 3, "preco": 13.50, "dy": 0.065, "roe": 0.14, "pl": 8.1, "divida_ebitda": 0.0},
        {"ticker": "SANB11", "classe": "Ações", "setor": "Bancos", "risco": "Médio", "prazo_min": 3, "preco": 28.00, "dy": 0.068, "roe": 0.12, "pl": 8.5, "divida_ebitda": 0.0},

        # --- AÇÕES - COMMODITIES E CICLICAS ---
        {"ticker": "VALE3", "classe": "Ações", "setor": "Mineração", "risco": "Alto", "prazo_min": 4, "preco": 62.00, "dy": 0.080, "roe": 0.18, "pl": 6.8, "divida_ebitda": 0.8},
        {"ticker": "PETR4", "classe": "Ações", "setor": "Petróleo e Gás", "risco": "Alto", "prazo_min": 4, "preco": 38.50, "dy": 0.135, "roe": 0.25, "pl": 4.5, "divida_ebitda": 0.9},
        {"ticker": "CSNA3", "classe": "Ações", "setor": "Siderurgia", "risco": "Alto", "prazo_min": 4, "preco": 12.00, "dy": 0.070, "roe": 0.08, "pl": 12.0, "divida_ebitda": 3.1},
        {"ticker": "PRIO3", "classe": "Ações", "setor": "Petróleo e Gás", "risco": "Alto", "prazo_min": 4, "preco": 45.00, "dy": 0.0, "roe": 0.26, "pl": 7.2, "divida_ebitda": 1.1},

        # --- AÇÕES - CRESCIMENTO E CONSUMO ---
        {"ticker": "WEGE3", "classe": "Ações", "setor": "Industrial", "risco": "Alto", "prazo_min": 5, "preco": 40.00, "dy": 0.025, "roe": 0.28, "pl": 28.0, "divida_ebitda": 0.2},
        {"ticker": "RENT3", "classe": "Ações", "setor": "Consumo", "risco": "Alto", "prazo_min": 4, "preco": 54.00, "dy": 0.020, "roe": 0.16, "pl": 18.5, "divida_ebitda": 2.4},
        {"ticker": "RADL3", "classe": "Ações", "setor": "Saúde", "risco": "Médio", "prazo_min": 4, "preco": 24.50, "dy": 0.015, "roe": 0.17, "pl": 26.0, "divida_ebitda": 1.4},

        # --- FUNDOS IMOBILIÁRIOS (FIIs) ---
        {"ticker": "KNCR11", "classe": "FIIs", "setor": "FII Papel", "risco": "Baixo", "prazo_min": 2, "preco": 104.50, "dy": 0.122, "roe": 0.0, "pl": 0.0, "divida_ebitda": 0.0},
        {"ticker": "MXRF11", "classe": "FIIs", "setor": "FII Papel", "risco": "Baixo", "prazo_min": 1, "preco": 10.10, "dy": 0.130, "roe": 0.0, "pl": 0.0, "divida_ebitda": 0.0},
        {"ticker": "CPTS11", "classe": "FIIs", "setor": "FII Papel", "risco": "Médio", "prazo_min": 2, "preco": 8.50, "dy": 0.125, "roe": 0.0, "pl": 0.0, "divida_ebitda": 0.0},
        {"ticker": "HGLG11", "classe": "FIIs", "setor": "FII Tijolo", "risco": "Médio", "prazo_min": 3, "preco": 162.00, "dy": 0.085, "roe": 0.0, "pl": 0.0, "divida_ebitda": 0.0},
        {"ticker": "XPML11", "classe": "FIIs", "setor": "FII Tijolo", "risco": "Médio", "prazo_min": 3, "preco": 115.00, "dy": 0.092, "roe": 0.0, "pl": 0.0, "divida_ebitda": 0.0},
        {"ticker": "VISC11", "classe": "FIIs", "setor": "FII Tijolo", "risco": "Médio", "prazo_min": 3, "preco": 118.00, "dy": 0.088, "roe": 0.0, "pl": 0.0, "divida_ebitda": 0.0}
    ])

# 4. MOTOR DE CÁLCULO DINÂMICO MULTI-FATORIAL
def calcular_score(row):
    if row["classe"] == "Renda Fixa":
        return 7.0
    
    # Normalização inteligente dos indicadores
    s_dy = min(row["dy"] * 60, 10)
    s_roe = min(row["roe"] * 30, 10)
    s_val = max(0, 10 - (row["pl"] / 3)) if row["pl"] > 0 else 5
    s_sol = max(0, 10 - (row["divida_ebitda"] * 2.5))
    
    score_ponderado = (
        (s_dy * peso_dy) + 
        (s_roe * peso_roe) + 
        (s_val * peso_val) + 
        (s_sol * peso_sol)
    ) / soma_pesos
    
    return round(score_ponderado, 2)

def obter_alocacao(perfil):
    if perfil == "Conservador":
        return {"Renda Fixa": 0.85, "Ações": 0.05, "FIIs": 0.10}
    elif perfil == "Moderado":
        return {"Renda Fixa": 0.50, "Ações": 0.30, "FIIs": 0.20}
    else:
        return {"Renda Fixa": 0.15, "Ações": 0.60, "FIIs": 0.25}

if st.button("Executar Otimização e Varredura Avançada", type="primary"):
    df = carregar_universo_b3()
    
    # Filtro de Risco por Perfil
    if perfil_risco == "Conservador":
        riscos_permitidos = ["Baixo"]
    elif perfil_risco == "Moderado":
        riscos_permitidos = ["Baixo", "Médio"]
    else:
        riscos_permitidos = ["Baixo", "Médio", "Alto"]
        
    df_filtrado = df[(df["risco"].isin(riscos_permitidos)) | (df["classe"] == "Renda Fixa")].copy()
    
    # Calcula as médias setoriais reais para comparação na tabela
    medias_setor = df.groupby("setor")[["dy", "roe", "pl", "divida_ebitda"]].mean().reset_index()
    
    df_filtrado["Score"] = df_filtrado.apply(calcular_score, axis=1)
    
    pesos = obter_alocacao(perfil_risco)
    carteira = []
    
    st.subheader(f"📊 Carteira Inteligente Reorganizada ({perfil_risco})")
    
    for classe, peso_alvo in pesos.items():
        valor_classe = capital_total * peso_alvo
        if valor_classe == 0:
            continue
            
        candidatos = df_filtrado[(df_filtrado["classe"] == classe) & (df_filtrado["prazo_min"] <= horizonte_anos)].copy()
        if candidatos.empty:
            candidatos = df_filtrado[df_filtrado["classe"] == classe].head(1)
            
        # Ordena pelo score atualizado pelos sliders
        candidatos = candidatos.sort_values(by="Score", ascending=False)
        
        # Pega os top 2 da classe
        selecionados = candidatos.head(2)
        
        valor_por_ativo = valor_classe / len(selecionados)
        
        for _, ativo in selecionados.iterrows():
            med = medias_setor[medias_setor["setor"] == ativo["setor"]].iloc[0] if ativo["setor"] in medias_setor["setor"].values else None
            
            item = {
                "Classe": classe,
                "Ativo": ativo["ticker"],
                "Risco": ativo["risco"],
                "Preço (R$)": f"R$ {ativo['preco']:.2f}",
                "Setor": ativo["setor"],
                "Score": ativo["Score"],
                "Alvo (%)": round((peso_alvo / len(selecionados)) * 100, 2),
                "Valor (R$)": round(valor_por_ativo, 2),
            }
            
            # Adiciona os indicadores dinamicamente se o slider for > 0 (ou configurado)
            if peso_dy > 0 and ativo["classe"] != "Renda Fixa":
                item["DY Ativo"] = f"{ativo['dy']*100:.1f}%"
                item["Média Setor DY"] = f"{med['dy']*100:.1f}%" if med is not None else "N/A"
                
            if peso_roe > 0 and ativo["classe"] != "Renda Fixa":
                item["ROE Ativo"] = f"{ativo['roe']*100:.1f}%"
                item["Média Setor ROE"] = f"{med['roe']*100:.1f}%" if med is not None else "N/A"
                
            if peso_val > 0 and ativo["classe"] != "Renda Fixa":
                item["P/L Ativo"] = f"{ativo['pl']:.1f}"
                item["Média Setor P/L"] = f"{med['pl']:.1f}" if med is not None else "N/A"
                
            if peso_sol > 0 and ativo["classe"] != "Renda Fixa":
                item["Dívida/EBITDA"] = f"{ativo['divida_ebitda']:.1f}"
                item["Média Setor Dívida"] = f"{med['divida_ebitda']:.1f}" if med is not None else "N/A"
                
            carteira.append(item)
            
    df_res = pd.DataFrame(carteira)
    st.dataframe(df_res, use_container_width=True)
    
    st.success("✅ O motor agora possui amplitude real de ativos por setor (FIIs de papel vs tijolo, bancos variados, elétricas diferentes) e a alteração dos pesos altera imediatamente a composição da carteira.")
