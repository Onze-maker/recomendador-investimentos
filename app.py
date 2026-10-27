import streamlit as st
import pandas as pd

st.set_page_config(page_title="Motor de Recomendação", page_icon="📈", layout="centered")

st.title("🤖 Motor de Recomendação de Investimentos")
st.markdown("Insira seus parâmetros abaixo para gerar a carteira ideal com base no seu perfil.")

# 1. Widgets de Entrada do Usuário na Tela
capital_total = st.number_input("Capital Inicial Disponível (R$)", min_value=100.0, value=100000.0, step=1000.0)
perfil_risco = st.selectbox("Perfil de Risco", ["Conservador", "Moderado", "Arrojado"])
horizonte_anos = st.slider("Horizonte de Tempo (anos)", min_value=1, max_value=30, value=5)

# 2. Base de Dados de Exemplo
catalogo_ativos = pd.DataFrame([
    {"ticker": "Tesouro IPCA+ 2035", "classe": "Renda Fixa", "risco": "Baixo", "retorno_esperado": 0.10, "min_aporte": 30},
    {"ticker": "CDB 100% CDI Liquidez", "classe": "Renda Fixa", "risco": "Muito Baixo", "retorno_esperado": 0.11, "min_aporte": 1},
    {"ticker": "VALE3", "classe": "Ações", "risco": "Alto", "retorno_esperado": 0.15, "min_aporte": 60},
    {"ticker": "PETR4", "classe": "Ações", "risco": "Alto", "retorno_esperado": 0.16, "min_aporte": 35},
    {"ticker": "ITUB4", "classe": "Ações", "risco": "Médio", "retorno_esperado": 0.14, "min_aporte": 30},
    {"ticker": "KNCR11", "classe": "FIIs", "risco": "Médio", "retorno_esperado": 0.12, "min_aporte": 100},
    {"ticker": "HGLG11", "classe": "FIIs", "risco": "Médio", "retorno_esperado": 0.11, "min_aporte": 150}
])

def obter_alocacao_alvo(perfil):
    perfis = {
        "Conservador": {"Renda Fixa": 0.85, "Ações": 0.05, "FIIs": 0.10},
        "Moderado":    {"Renda Fixa": 0.50, "Ações": 0.30, "FIIs": 0.20},
        "Arrojado":    {"Renda Fixa": 0.15, "Ações": 0.60, "FIIs": 0.25}
    }
    return perfis.get(perfil, perfis["Moderado"])

# 3. Botão de Execução
if st.button("Gerar Carteira Recomendada", type="primary"):
    pesos_classes = obter_alocacao_alvo(perfil_risco)
    carteira_final = []
    
    for classe, peso in pesos_classes.items():
        valor_classe = capital_total * peso
        if valor_classe == 0: 
            continue
            
        ativos_disponiveis = catalogo_ativos[catalogo_ativos["classe"] == classe].copy()
        ativos_disponiveis["score"] = ativos_disponiveis["retorno_esperado"] / (1 + ativos_disponiveis["min_aporte"]/1000)
        ativos_disponiveis = ativos_disponiveis.sort_values(by="score", ascending=False)
        
        selecionados = ativos_disponiveis.head(2)
        valor_por_ativo = valor_classe / len(selecionados)
        
        for _, ativo in selecionados.iterrows():
            carteira_final.append({
                "Classe": classe,
                "Ativo": ativo["ticker"],
                "Alvo (%)": (peso / len(selecionados)) * 100,
                "Valor Sugerido (R$)": valor_por_ativo,
                "Retorno Esperado (%)": ativo["retorno_esperado"] * 100
            })
            
    df_carteira = pd.DataFrame(carteira_final)
    
    st.success("Carteira calculada com sucesso!")
    st.dataframe(df_carteira, use_container_width=True)
    
    # Gráfico visual automático
    st.subheader("Distribuição por Ativo")
    st.bar_chart(df_carteira.set_index("Ativo")["Valor Sugerido (R$)"])
