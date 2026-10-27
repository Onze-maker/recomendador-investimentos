import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Motor B3 Tempo Real", page_icon="⚡", layout="wide")

st.title("⚡ Motor Quantitativo B3: Varredura em Tempo Real")
st.markdown("O sistema conecta à B3 via API do Yahoo Finance em tempo real, extrai indicadores atualizados e seleciona os melhores ativos de acordo com seus pesos.")

# 1. PARÂMETROS MACRO
st.sidebar.header("1. Perfil e Parâmetros")
capital_total = st.sidebar.number_input("Capital Disponível (R$)", min_value=100.0, value=100000.0, step=1000.0)
perfil_risco = st.sidebar.selectbox("Perfil de Risco", ["Conservador", "Moderado", "Arrojado"])
horizonte_anos = st.sidebar.slider("Horizonte de Investimento (Anos)", min_value=1, max_value=30, value=5)

# 2. PESOS DE INDICADORES (SLIDERS)
st.sidebar.header("2. Pesos e Critérios (0 a 10)")
peso_dy = st.sidebar.slider("Dividend Yield (DY)", 0, 10, 5)
peso_roe = st.sidebar.slider("Eficiência (ROE)", 0, 10, 5)
peso_val = st.sidebar.slider("Valuation (P/L)", 0, 10, 5)
peso_sol = st.sidebar.slider("Solidez (Dívida/EBITDA)", 0, 10, 5)

soma_pesos = (peso_dy + peso_roe + peso_val + peso_sol) or 1

# 3. UNIVERSO DE TICKERS DA B3 PARA VARREDURA
TICKERS_B3 = [
    # Ações
    "BBAS3.SA", "ITUB4.SA", "BBDC4.SA", "SANB11.SA",
    "TAEE11.SA", "CPLE6.SA", "EGIE3.SA", "EQTL3.SA",
    "VALE3.SA", "PETR4.SA", "WEGE3.SA", "RENT3.SA",
    "ABEV3.SA", "VBBR3.SA", "RADL3.SA", "LREN3.SA",
    # FIIs
    "KNCR11.SA", "HGLG11.SA", "MXRF11.SA", "XPML11.SA", "BCSC11.SA"
]

@st.cache_data(ttl=3600)  # Cache de 1 hora para economizar chamadas de API
def baixar_dados_tempo_real(tickers):
    lista_dados = []
    
    for ticker in tickers:
        try:
            ativo = yf.Ticker(ticker)
            info = ativo.info
            
            # Identifica a classe
            quote_type = info.get("quoteType", "")
            classe = "FIIs" if quote_type == "EQUITY" and "11.SA" in ticker else "Ações"
            
            # Puxa indicadores fundamentalistas reais
            preco = info.get("currentPrice") or info.get("regularMarketPreviousClose") or 0.0
            dy = info.get("dividendYield", 0.0) or 0.0  # Vem em decimal (ex: 0.08)
            roe = info.get("returnOnEquity", 0.0) or 0.0
            pl = info.get("trailingPE", 0.0) or 0.0
            divida_ebitda = info.get("debtToEquity", 0.0) / 100 if info.get("debtToEquity") else 0.0
            beta = info.get("beta", 1.0) or 1.0
            
            # Classificação aproximada de risco com base no Beta/Volatilidade
            if beta < 0.7:
                risco = "Baixo"
            elif beta <= 1.2:
                risco = "Médio"
            else:
                risco = "Alto"
                
            lista_dados.append({
                "ticker": ticker.replace(".SA", ""),
                "classe": classe,
                "setor": info.get("sector", "Imobiliário/Outros" if classe == "FIIs" else "Geral"),
                "risco": risco,
                "preco": preco,
                "dy": dy,
                "roe": roe,
                "pl": pl,
                "divida_ebitda": divida_ebitda,
                "prazo_min": 2 if classe == "FIIs" else (3 if risco != "Alto" else 5)
            })
        except Exception:
            continue
            
    # Adiciona opções de Renda Fixa fixas de referência
    lista_dados.extend([
        {
            "ticker": "CDB 100% CDI", "classe": "Renda Fixa", "setor": "Renda Fixa", "risco": "Baixo",
            "preco": 1.0, "dy": 0.105, "roe": 0.0, "pl": 0.0, "divida_ebitda": 0.0, "prazo_min": 0
        },
        {
            "ticker": "Tesouro IPCA+ 2029", "classe": "Renda Fixa", "setor": "Renda Fixa", "risco": "Baixo",
            "preco": 1000.0, "dy": 0.065, "roe": 0.0, "pl": 0.0, "divida_ebitda": 0.0, "prazo_min": 2
        }
    ])
    
    return pd.DataFrame(lista_dados)

# 4. CÁLCULO DO SCORE DINÂMICO
def calcular_score_tempo_real(row):
    if row["classe"] == "Renda Fixa":
        return 7.0
    
    s_dy = min(row["dy"] * 60, 10)
    s_roe = min(row["roe"] * 30, 10)
    s_val = max(0, 10 - (row["pl"] / 3)) if row["pl"] > 0 else 5
    s_sol = max(0, 10 - (row["divida_ebitda"] * 2))
    
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

if st.button("Consultar Mercado em Tempo Real e Otimizar", type="primary"):
    with st.spinner("Buscando cotações e indicadores em tempo real na B3..."):
        df = baixar_dados_tempo_real(TICKERS_B3)
    
    # Filtro de Risco
    if perfil_risco == "Conservador":
        riscos_permitidos = ["Baixo"]
    elif perfil_risco == "Moderado":
        riscos_permitidos = ["Baixo", "Médio"]
    else:
        riscos_permitidos = ["Baixo", "Médio", "Alto"]
        
    df_filtrado = df[(df["risco"].isin(riscos_permitidos)) | (df["classe"] == "Renda Fixa")].copy()
    
    # Calcula a média setorial em tempo real para comparação
    medias_setoriais = df.groupby("setor")[["dy", "roe", "pl", "divida_ebitda"]].mean().reset_index()
    
    df_filtrado["Score"] = df_filtrado.apply(calcular_score_tempo_real, axis=1)
    
    pesos = obter_alocacao(perfil_risco)
    carteira = []
    
    for classe, peso_alvo in pesos.items():
        valor_classe = capital_total * peso_alvo
        if valor_classe == 0:
            continue
            
        candidatos = df_filtrado[(df_filtrado["classe"] == classe) & (df_filtrado["prazo_min"] <= horizonte_anos)].copy()
        if candidatos.empty:
            candidatos = df_filtrado[df_filtrado["classe"] == classe].head(1)
            
        candidatos = candidatos.sort_values(by="Score", ascending=False)
        selecionados = candidatos.head(2)
        
        valor_por_ativo = valor_classe / len(selecionados)
        
        for _, ativo in selecionados.iterrows():
            # Puxa a média do setor correspondente
            med_setor = medias_setoriais[medias_setoriais["setor"] == ativo["setor"]].iloc[0] if ativo["setor"] in medias_setoriais["setor"].values else None
            
            item = {
                "Classe": classe,
                "Ativo": ativo["ticker"],
                "Preço Atual (R$)": f"R$ {ativo['preco']:.2f}",
                "Setor": ativo["setor"],
                "Score Otimizado": ativo["Score"],
                "Alvo (%)": round((peso_alvo / len(selecionados)) * 100, 2),
                "Valor (R$)": round(valor_por_ativo, 2),
            }
            
            if peso_dy > 5:
                item["DY Real"] = f"{ativo['dy']*100:.1f}%"
                item["Média Setor DY"] = f"{med_setor['dy']*100:.1f}%" if med_setor is not None else "N/A"
                
            if peso_roe > 5:
                item["ROE Real"] = f"{ativo['roe']*100:.1f}%"
                item["Média Setor ROE"] = f"{med_setor['roe']*100:.1f}%" if med_setor is not None else "N/A"
                
            if peso_val > 5:
                item["P/L Real"] = f"{ativo['pl']:.1f}"
                item["Média Setor P/L"] = f"{med_setor['pl']:.1f}" if med_setor is not None else "N/A"
                
            if peso_sol > 5:
                item["Dívida/EBITDA"] = f"{ativo['divida_ebitda']:.1f}"
                item["Média Setor Dívida"] = f"{med_setor['divida_ebitda']:.1f}" if med_setor is not None else "N/A"
                
            carteira.append(item)
            
    df_res = pd.DataFrame(carteira)
    st.subheader(f"📊 Carteira Inteligente Gerada em Tempo Real ({perfil_risco})")
    st.dataframe(df_res, use_container_width=True)
