import streamlit as st
import pandas as pd

st.set_page_config(page_title="Motor Quantitativo Multi-Fatorial B3", page_icon="📈", layout="wide")

st.title("🎯 Motor Quantitativo B3: Varredura Setorial & Indicadores Dinâmicos")
st.markdown("O motor varre o mercado, compara o ativo com a média do seu setor e exibe os indicadores na tabela sempre que a importância atribuída for superior a 5.")

# 1. PARÂMETROS MACRO
st.sidebar.header("1. Perfil e Parâmetros")
capital_total = st.sidebar.number_input("Capital Disponível (R$)", min_value=100.0, value=100000.0, step=1000.0)
perfil_risco = st.sidebar.selectbox("Perfil de Risco", ["Conservador", "Moderado", "Arrojado"])
horizonte_anos = st.sidebar.slider("Horizonte de Investimento (Anos)", min_value=1, max_value=30, value=5)

# 2. PESOS CUSTOMIZÁVEIS (A regra dos sliders > 5 controla o que aparece na tabela)
st.sidebar.header("2. Pesos e Critérios (0 a 10)")
st.sidebar.markdown("Se definir **acima de 5**, o indicador aparecerá detalhado na tabela final:")
peso_dy = st.sidebar.slider("Dividend Yield (DY)", 0, 10, 6)
peso_gov = st.sidebar.slider("Governança (Novo Mercado)", 0, 10, 6)
peso_roe = st.sidebar.slider("Eficiência (ROE)", 0, 10, 6)
peso_val = st.sidebar.slider("Valuation (P/L)", 0, 10, 4)
peso_sol = st.sidebar.slider("Solidez (Dívida/EBITDA)", 0, 10, 5)

# Normalização de pesos
soma = (peso_dy + peso_gov + peso_roe + peso_val + peso_sol) or 1
p_dy, p_gov, p_roe, p_val, p_sol = peso_dy/soma, peso_gov/soma, peso_roe/soma, peso_val/soma, peso_sol/soma

# 3. BASE DE DADOS AMPLIADA DA B3 COM MÉDIAS SETORIAIS
@st.cache_data
def carregar_base_b3():
    return pd.DataFrame([
        # Renda Fixa
        {
            "ticker": "CDB 100% CDI", "classe": "Renda Fixa", "setor": "Renda Fixa", "risco": "Baixo", "prazo_min": 0,
            "preco": 1.0, "dy": 0.11, "media_setor_dy": 0.10, "governanca": "FGC", "roe": 0.0, "media_setor_roe": 0.0,
            "pl": 0.0, "media_setor_pl": 0.0, "divida_ebitda": 0.0, "media_setor_divida": 0.0
        },
        {
            "ticker": "Tesouro IPCA+ 2029", "classe": "Renda Fixa", "setor": "Renda Fixa", "risco": "Baixo", "prazo_min": 2,
            "preco": 1000.0, "dy": 0.06, "media_setor_dy": 0.06, "governanca": "Soberano", "roe": 0.0, "media_setor_roe": 0.0,
            "pl": 0.0, "media_setor_pl": 0.0, "divida_ebitda": 0.0, "media_setor_divida": 0.0
        },
        # Ações - Energia
        {
            "ticker": "TAEE11 (Taesa)", "classe": "Ações", "setor": "Energia", "risco": "Baixo", "prazo_min": 3,
            "preco": 35.50, "dy": 0.102, "media_setor_dy": 0.075, "governanca": "Nível 2", "roe": 0.15, "media_setor_roe": 0.12,
            "pl": 7.5, "media_setor_pl": 9.0, "divida_ebitda": 2.2, "media_setor_divida": 2.5
        },
        {
            "ticker": "CPLE6 (Copel)", "classe": "Ações", "setor": "Energia", "risco": "Médio", "prazo_min": 3,
            "preco": 10.20, "dy": 0.085, "media_setor_dy": 0.075, "governanca": "Novo Mercado", "roe": 0.14, "media_setor_roe": 0.12,
            "pl": 6.8, "media_setor_pl": 9.0, "divida_ebitda": 1.8, "media_setor_divida": 2.5
        },
        # Ações - Bancos
        {
            "ticker": "BBAS3 (Banco do Brasil)", "classe": "Ações", "setor": "Bancos", "risco": "Médio", "prazo_min": 3,
            "preco": 27.40, "dy": 0.091, "media_setor_dy": 0.065, "governanca": "Novo Mercado", "roe": 0.21, "media_setor_roe": 0.18,
            "pl": 5.2, "media_setor_pl": 7.5, "divida_ebitda": 0.0, "media_setor_divida": 0.0
        },
        {
            "ticker": "ITUB4 (Itaú Unibanco)", "classe": "Ações", "setor": "Bancos", "risco": "Baixo", "prazo_min": 3,
            "preco": 33.10, "dy": 0.052, "media_setor_dy": 0.065, "governanca": "Nível 1", "roe": 0.20, "media_setor_roe": 0.18,
            "pl": 9.5, "media_setor_pl": 7.5, "divida_ebitda": 0.0, "media_setor_divida": 0.0
        },
        # Ações - Mineração e Siderurgia / Commodities
        {
            "ticker": "VALE3 (Vale)", "classe": "Ações", "setor": "Mineração", "risco": "Alto", "prazo_min": 4,
            "preco": 62.00, "dy": 0.080, "media_setor_dy": 0.070, "governanca": "Novo Mercado", "roe": 0.18, "media_setor_roe": 0.15,
            "pl": 6.8, "media_setor_pl": 8.0, "divida_ebitda": 0.8, "media_setor_divida": 1.2
        },
        {
            "ticker": "PETR4 (Petrobras)", "classe": "Ações", "setor": "Petróleo e Gás", "risco": "Alto", "prazo_min": 4,
            "preco": 38.50, "dy": 0.135, "media_setor_dy": 0.090, "governanca": "Nível 2", "roe": 0.25, "media_setor_roe": 0.16,
            "pl": 4.5, "media_setor_pl": 7.0, "divida_ebitda": 0.9, "media_setor_divida": 1.5
        },
        # FIIs
        {
            "ticker": "KNCR11 (FII Papel)", "classe": "FIIs", "setor": "Fundos Imobiliários", "risco": "Médio", "prazo_min": 2,
            "preco": 104.50, "dy": 0.122, "media_setor_dy": 0.100, "governanca": "Gestão Profissional", "roe": 0.0, "media_setor_roe": 0.0,
            "pl": 0.0, "media_setor_pl": 0.0, "divida_ebitda": 0.0, "media_setor_divida": 0.0
        },
        {
            "ticker": "HGLG11 (FII Logística)", "classe": "FIIs", "setor": "Fundos Imobiliários", "risco": "Médio", "prazo_min": 3,
            "preco": 162.00, "dy": 0.085, "media_setor_dy": 0.100, "governanca": "Gestão Profissional", "roe": 0.0, "media_setor_roe": 0.0,
            "pl": 0.0, "media_setor_pl": 0.0, "divida_ebitda": 0.0, "media_setor_divida": 0.0
        }
    ])

# 4. CÁLCULO DO SCORE MULTI-FATORIAL
def calcular_score(row):
    if row["classe"] == "Renda Fixa":
        return 8.5
    s_dy = min(row["dy"] * 50, 10)
    s_gov = 10.0 if "Novo Mercado" in row["governanca"] else (8.0 if "Nível" in row["governanca"] else 6.0)
    s_roe = min(row["roe"] * 25, 10)
    s_val = max(0, 10 - (row["pl"] / 3)) if row["pl"] > 0 else 5
    s_sol = max(0, 10 - (row["divida_ebitda"] * 2))
    
    return round((s_dy * p_dy) + (s_gov * p_gov) + (s_roe * p_roe) + (s_val * p_val) + (s_sol * p_sol), 2)

def obter_alocacao(perfil):
    if perfil == "Conservador":
        return {"Renda Fixa": 0.85, "Ações": 0.05, "FIIs": 0.10}
    elif perfil == "Moderado":
        return {"Renda Fixa": 0.50, "Ações": 0.30, "FIIs": 0.20}
    else:
        return {"Renda Fixa": 0.15, "Ações": 0.60, "FIIs": 0.25}

if st.button("Rodar Varredura e Otimização Inteligente", type="primary"):
    df = carregar_base_b3()
    df["Score"] = df.apply(calcular_score, axis=1)
    
    pesos = obter_alocacao(perfil_risco)
    carteira = []
    
    st.subheader(f"📊 Carteira Ideal para o Perfil {perfil_risco}")
    
    for classe, peso_alvo in pesos.items():
        valor_classe = capital_total * peso_alvo
        if valor_classe == 0:
            continue
            
        candidatos = df[(df["classe"] == classe) & (df["prazo_min"] <= horizonte_anos)].copy()
        if candidatos.empty:
            candidatos = df[df["classe"] == classe].head(1)
            
        candidatos = candidatos.sort_values(by="Score", ascending=False)
        selecionados = candidatos.head(2)
        
        valor_por_ativo = valor_classe / len(selecionados)
        
        for _, ativo in selecionados.iterrows():
            # Dicionário base obrigatório
            item = {
                "Classe": classe,
                "Ativo": ativo["ticker"],
                "Preço (R$)": f"R$ {ativo['preco']:.2f}",
                "Setor": ativo["setor"],
                "Alvo (%)": round((peso_alvo / len(selecionados)) * 100, 2),
                "Valor (R$)": round(valor_por_ativo, 2),
            }
            
            # ADICIONA DINAMICAMENTE OS INDICADORES SE O SLIDER FOR > 5
            if peso_dy > 5:
                item["DY Ativo"] = f"{ativo['dy']*100:.1f}%"
                item["Média Setor DY"] = f"{ativo['media_setor_dy']*100:.1f}%"
                
            if peso_gov > 5:
                item["Governança"] = ativo["governanca"]
                
            if peso_roe > 5:
                item["ROE Ativo"] = f"{ativo['roe']*100:.1f}%"
                item["Média Setor ROE"] = f"{ativo['media_setor_roe']*100:.1f}%"
                
            if peso_val > 5:
                item["P/L Ativo"] = f"{ativo['pl']:.1f}"
                item["Média Setor P/L"] = f"{ativo['media_setor_pl']:.1f}"
                
            if peso_sol > 5:
                item["Dívida/EBITDA"] = f"{ativo['divida_ebitda']:.1f}"
                item["Média Setor Dívida"] = f"{ativo['media_setor_divida']:.1f}"
                
            carteira.append(item)
            
    df_res = pd.DataFrame(carteira)
    st.dataframe(df_res, use_container_width=True)
    
    st.success("✅ Varredura concluída! Os indicadores exibidos na tabela refletem exatamente os critérios onde seu peso de importância foi configurado acima de 5.")
