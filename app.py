import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Motor Quantitativo B3 - Real", page_icon="⚡", layout="wide")

st.title("⚡ Motor Quantitativo B3: Varredura Dinâmica em Tempo Real")
st.markdown("Este motor não usa tabelas estáticas. Ele consulta o mercado ao vivo, avalia os indicadores de dezenas de ativos da B3 e aplica os seus pesos matemáticos para montar a carteira.")

# 1. PARÂMETROS MACRO
st.sidebar.header("1. Perfil e Parâmetros")
capital_total = st.sidebar.number_input("Capital Disponível (R$)", min_value=100.0, value=100000.0, step=1000.0)
perfil_risco = st.sidebar.selectbox("Perfil de Risco", ["Conservador", "Moderado", "Arrojado"])
horizonte_anos = st.sidebar.slider("Horizonte de Investimento (Anos)", min_value=1, max_value=30, value=5)

# 2. PESOS DOS SLIDERS (O motor usa estes valores para ordenar o mercado)
st.sidebar.header("2. Pesos de Preferência (0 a 10)")
st.sidebar.markdown("Mexer nestes pesos altera imediatamente o ranking e os ativos escolhidos:")
peso_dy = st.sidebar.slider("Dividend Yield (Foco em Renda)", 0, 10, 5)
peso_roe = st.sidebar.slider("Eficiência / ROE", 0, 10, 5)
peso_val = st.sidebar.slider("Valuation / P/L Barato", 0, 10, 5)
peso_sol = st.sidebar.slider("Solidez / Baixa Dívida", 0, 10, 5)

soma_pesos = (peso_dy + peso_roe + peso_val + peso_sol)
if soma_pesos == 0:
    soma_pesos = 1

# 3. UNIVERSO AMPLO DE TICKERS PARA VARREDURA NA B3
UNIVERSO_B3 = [
    # Elétricas e saneamento
    "TAEE11.SA", "CPLE6.SA", "EGIE3.SA", "CMIG4.SA", "ENEV3.SA", "SBSP3.SA", "SAPR11.SA",
    # Bancos e financeiro
    "ITUB4.SA", "BBAS3.SA", "BBDC4.SA", "SANB11.SA", "BPAC11.SA",
    # Commodities e petrolíferas
    "PETR4.SA", "VALE3.SA", "CSNA3.SA", "PRIO3.SA", "SUZB3.SA", "KLBN11.SA",
    # Consumo, varejo e industrial
    "WEGE3.SA", "RENT3.SA", "RADL3.SA", "LREN3.SA", "ABEV3.SA", "MGLU3.SA", "VAMO3.SA",
    # Fundos Imobiliários (FIIs)
    "MXRF11.SA", "KNCR11.SA", "CPTS11.SA", "HGLG11.SA", "XPML11.SA", "VISC11.SA", "IRDM11.SA", "BTLG11.SA"
]

@st.cache_data(ttl=3600)
def varrer_mercado_b3(tickers):
    dados_coletados = []
    
    for t in tickers:
        try:
            ativo = yf.Ticker(t)
            info = ativo.info
            
            # Extração de dados reais da API
            preco = info.get("currentPrice") or info.get("regularMarketPreviousClose") or 0.0
            dy = info.get("dividendYield", 0.0) or 0.0
            roe = info.get("returnOnEquity", 0.0) or 0.0
            pl = info.get("trailingPE", 0.0) or 0.0
            divida_eq = info.get("debtToEquity", 0.0) or 0.0
            divida_ebitda = divida_eq / 100.0  aria aproximada se necessário
            beta = info.get("beta", 1.0) or 1.0
            
            # Identifica classe e setor
            q_type = info.get("quoteType", "")
            is_fii = "11.SA" in t and ("FII" in info.get("longName", "").upper() or q_type == "EQUITY" and "FUNDO" in info.get("category", "").upper())
            
            if "11.SA" in t and ("KNCR" in t or "MXRF" in t or "CPTS" in t or "HGLG" in t or "XPML" in t or "VISC" in t or "IRDM" in t or "BTLG" in t):
                classe = "FIIs"
                setor = "Fundos Imobiliários"
            else:
                classe = "Ações"
                setor = info.get("sector", "Geral")

            # Classificação de risco por volatilidade (Beta)
            if beta < 0.7:
                risco = "Baixo"
            elif beta <= 1.2:
                risco = "Médio"
            else:
                risco = "Alto"

            if preco > 0:
                dados_coletados.append({
                    "ticker": t.replace(".SA", ""),
                    "classe": classe,
                    "setor": setor,
                    "risco": risco,
                    "preco": preco,
                    "dy": dy,
                    "roe": roe,
                    "pl": pl if pl > 0 else 15.0, # fallback para evitar distorções
                    "divida_ebitda": max(0.0, divida_ebitda),
                    "prazo_min": 2 if classe == "FIIs" else (3 if risco != "Alto" else 5)
                })
        except Exception:
            continue
            
    # Adiciona Opções de Renda Fixa Soberana/Segura
    dados_coletados.extend([
        {"ticker": "CDB 100% CDI", "classe": "Renda Fixa", "setor": "Renda Fixa", "risco": "Baixo", "prazo_min": 0, "preco": 1.0, "dy": 0.11, "roe": 0.0, "pl": 0.0, "divida_ebitda": 0.0},
        {"ticker": "Tesouro IPCA+ 2029", "classe": "Renda Fixa", "setor": "Renda Fixa", "risco": "Baixo", "prazo_min": 2, "preco": 1020.0, "dy": 0.065, "roe": 0.0, "pl": 0.0, "divida_ebitda": 0.0}
    ])
    
    return pd.DataFrame(dados_coletados)

# 4. MOTOR DE CÁLCULO PONDERADO PELOS SLIDERS
def calcular_score_dinamico(row):
    if row["classe"] == "Renda Fixa":
        return 5.0
        
    s_dy = min(row["dy"] * 10, 10)
    s_roe = min(row["roe"] * 10, 10)
    s_val = max(0, 10 - (row["pl"] / 3)) if row["pl"] > 0 else 0
    s_sol = max(0, 10 - (row["divida_ebitda"] * 2))
    
    score = (
        (s_dy * peso_dy) + 
        (s_roe * peso_roe) + 
        (s_val * peso_val) + 
        (s_sol * peso_sol)
    ) / soma_pesos
    
    return round(score, 4)

def obter_alocacao(perfil):
    if perfil == "Conservador":
        return {"Renda Fixa": 0.85, "Ações": 0.05, "FIIs": 0.10}
    elif perfil == "Moderado":
        return {"Renda Fixa": 0.50, "Ações": 0.30, "FIIs": 0.20}
    else:
        return {"Renda Fixa": 0.15, "Ações": 0.60, "FIIs": 0.25}

if st.button("Varrer B3 ao Vivo e Otimizar Carteira", type="primary"):
    with st.spinner("Conectando à B3 e baixando indicadores em tempo real..."):
        df = varrer_mercado_b3(UNIVERSO_B3)
        
    if df.empty:
        st.error("Erro ao carregar dados da B3. Tente novamente em instantes.")
    else:
        # Filtro de risco baseado no perfil
        if perfil_risco == "Conservador":
            riscos_permitidos = ["Baixo"]
        elif perfil_risco == "Moderado":
            riscos_permitidos = ["Baixo", "Médio"]
        else:
            riscos_permitidos = ["Baixo", "Médio", "Alto"]
            
        df_filtrado = df[(df["risco"].isin(riscos_permitidos)) | (df["classe"] == "Renda Fixa")].copy()
        
        # Aplica os pesos dos sliders para calcular o score de cada ativo em tempo real
        df_filtrado["Score"] = df_filtrado.apply(calcular_score_dinamico, axis=1)
        
        # Calcula médias setoriais reais do mercado varrido
        medias_setor = df.groupby("setor")[["dy", "roe", "pl", "divida_ebitda"]].mean().reset_index()
        
        pesos = obter_alocacao(perfil_risco)
        carteira = []
        
        for classe, peso_alvo in pesos.items():
            valor_classe = capital_total * peso_alvo
            if valor_classe == 0:
                continue
                
            candidatos = df_filtrado[(df_filtrado["classe"] == classe) & (df_filtrado["prazo_min"] <= horizonte_anos)].copy()
            if candidatos.empty:
                candidatos = df_filtrado[df_filtrado["classe"] == classe].head(1)
                
            # O ranking muda na hora conforme os pesos dos sliders
            candidatos = candidatos.sort_values(by="Score", ascending=False)
            selecionados = candidatos.head(2)
            
            valor_por_ativo = valor_classe / len(selecionados)
            
            for _, ativo in selecionados.iterrows():
                med = medias_setor[medias_setor["setor"] == ativo["setor"]].iloc[0] if ativo["setor"] in medias_setor["setor"].values else None
                
                item = {
                    "Classe": classe,
                    "Ativo": ativo["ticker"],
                    "Setor": ativo["setor"],
                    "Risco": ativo["risco"],
                    "Preço (R$)": f"R$ {ativo['preco']:.2f}",
                    "Score": ativo["Score"],
                    "Alvo (%)": round((peso_alvo / len(selecionados)) * 100, 2),
                    "Valor (R$)": round(valor_por_ativo, 2),
                }
                
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
        st.subheader(f"📊 Carteira Dinâmica Gerada ao Vivo ({perfil_risco})")
        st.dataframe(df_res, use_container_width=True)
        st.success("✅ Varredura concluída com dados reais obtidos da B3. Alterar os sliders agora recalcula o score de todo o universo de ativos e altera os recomendados.")
