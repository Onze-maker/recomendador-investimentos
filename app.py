
import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np

st.set_page_config(
    page_title="Motor Quantitativo B3",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ Motor Quantitativo B3")
st.caption(
    "Ranking dinâmico por indicadores fundamentalistas, "
    "com pesos ajustáveis e carteira recalculada automaticamente."
)

# =========================================================
# 1. PARÂMETROS
# =========================================================

st.sidebar.header("1. Perfil e parâmetros")

capital_total = st.sidebar.number_input(
    "Capital disponível (R$)",
    min_value=100.0,
    value=100000.0,
    step=1000.0
)

perfil_risco = st.sidebar.selectbox(
    "Perfil de risco",
    ["Conservador", "Moderado", "Arrojado"]
)

horizonte_anos = st.sidebar.slider(
    "Horizonte de investimento (anos)",
    1, 30, 5
)

st.sidebar.header("2. Pesos dos indicadores")
st.sidebar.caption(
    "Altere os pesos para recalcular o ranking e a carteira."
)

peso_dy = st.sidebar.slider("Dividend Yield", 0, 10, 5)
peso_roe = st.sidebar.slider("ROE", 0, 10, 5)
peso_val = st.sidebar.slider("Valuation / P/L", 0, 10, 5)
peso_sol = st.sidebar.slider("Solidez financeira", 0, 10, 5)

pesos = {
    "score_dy": peso_dy,
    "score_roe": peso_roe,
    "score_val": peso_val,
    "score_sol": peso_sol,
}

soma_pesos = sum(pesos.values())

# =========================================================
# 2. UNIVERSO DE ATIVOS
# =========================================================

ACOES_B3 = [
    "TAEE11.SA", "CPLE6.SA", "EGIE3.SA", "CMIG4.SA",
    "ENEV3.SA", "SBSP3.SA", "SAPR11.SA",
    "ITUB4.SA", "BBAS3.SA", "BBDC4.SA", "SANB11.SA",
    "BPAC11.SA", "PETR4.SA", "VALE3.SA", "CSNA3.SA",
    "PRIO3.SA", "SUZB3.SA", "KLBN11.SA", "WEGE3.SA",
    "RENT3.SA", "RADL3.SA", "LREN3.SA", "ABEV3.SA",
    "MGLU3.SA", "VAMO3.SA",
]

FIIS_B3 = [
    "MXRF11.SA", "KNCR11.SA", "CPTS11.SA", "HGLG11.SA",
    "XPML11.SA", "VISC11.SA", "IRDM11.SA", "BTLG11.SA",
]

UNIVERSO_B3 = ACOES_B3 + FIIS_B3

# =========================================================
# 3. COLETA DE DADOS
# O cache evita consultar o Yahoo a cada movimento de slider.
# =========================================================

@st.cache_data(ttl=3600, show_spinner=False)
def varrer_mercado_b3(tickers):
    registros = []

    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).info or {}

            preco = (
                info.get("currentPrice")
                or info.get("regularMarketPrice")
                or info.get("regularMarketPreviousClose")
            )

            if not preco or preco <= 0:
                continue

            dy = info.get("dividendYield")
            roe = info.get("returnOnEquity")
            pl = info.get("trailingPE")
            divida_pl = info.get("debtToEquity")
            beta = info.get("beta")

            dy = float(dy) if dy is not None else np.nan
            roe = float(roe) if roe is not None else np.nan
            pl = float(pl) if pl is not None else np.nan
            divida_pl = (
                float(divida_pl)
                if divida_pl is not None else np.nan
            )
            beta = float(beta) if beta is not None else np.nan

            classe = (
                "FIIs" if ticker in FIIS_B3 else "Ações"
            )

            # Beta ausente não é tratado como baixo risco.
            if pd.isna(beta):
                risco = "Não classificado"
            elif beta < 0.7:
                risco = "Baixo"
            elif beta <= 1.2:
                risco = "Médio"
            else:
                risco = "Alto"

            registros.append({
                "ticker": ticker.replace(".SA", ""),
                "classe": classe,
                "setor": info.get("sector") or (
                    "Fundos Imobiliários"
                    if classe == "FIIs" else "Não informado"
                ),
                "risco": risco,
                "preco": preco,
                "dy": dy,
                "roe": roe,
                "pl": pl if not pd.isna(pl) and pl > 0
                    else np.nan,
                "divida_pl": divida_pl,
                "beta": beta,
                "prazo_min": (
                    2 if classe == "FIIs"
                    else 5 if risco == "Alto"
                    else 3
                ),
            })

        except Exception:
            # Um ticker com falha não interrompe a varredura.
            continue

    colunas = [
        "ticker", "classe", "setor", "risco", "preco",
        "dy", "roe", "pl", "divida_pl", "beta", "prazo_min"
    ]

    return pd.DataFrame(registros, columns=colunas)


# =========================================================
# 4. NORMALIZAÇÃO DOS INDICADORES
# Compara os ativos do universo numa escala de 0 a 10.
# =========================================================

def calcular_scores(df):
    df = df.copy()

    # Quanto maior, melhor.
    df["score_dy"] = (
        df["dy"].rank(pct=True) * 10
    )

    df["score_roe"] = (
        df["roe"].rank(pct=True) * 10
    )

    # P/L positivo menor tende a receber nota maior.
    # P/L ausente ou negativo não é inventado.
    df["score_val"] = (
        1 - df["pl"].rank(pct=True)
    ) * 10

    # Menor dívida em relação ao patrimônio recebe nota maior.
    # Não confundir Dívida/PL com Dívida Líquida/EBITDA.
    df["score_sol"] = (
        1 - df["divida_pl"].rank(pct=True)
    ) * 10

    colunas_score = [
        "score_dy", "score_roe", "score_val", "score_sol"
    ]

    # Pesos zero são ignorados.
    # Indicadores ausentes não recebem uma nota fictícia:
    # o denominador considera apenas indicadores disponíveis.
    numerador = pd.Series(0.0, index=df.index)
    denominador = pd.Series(0.0, index=df.index)

    for coluna, peso in pesos.items():
        if peso == 0:
            continue

        disponivel = df[coluna].notna()
        numerador.loc[disponivel] += (
            df.loc[disponivel, coluna] * peso
        )
        denominador.loc[disponivel] += peso

    df["Score"] = (
        numerador.div(denominador.where(denominador > 0))
    )

    # Se todos os pesos forem zero, não existe preferência.
    if soma_pesos == 0:
        df["Score"] = np.nan

    return df


# =========================================================
# 5. ALOCAÇÃO POR PERFIL
# =========================================================

def obter_alocacao(perfil):
    alocacoes = {
        "Conservador": {
            "Renda Fixa": 0.85, "Ações": 0.05, "FIIs": 0.10
        },
        "Moderado": {
            "Renda Fixa": 0.50, "Ações": 0.30, "FIIs": 0.20
        },
        "Arrojado": {
            "Renda Fixa": 0.15, "Ações": 0.60, "FIIs": 0.25
        },
    }
    return alocacoes[perfil]


# =========================================================
# 6. ATUALIZAÇÃO DOS DADOS
# =========================================================

if st.sidebar.button("🔄 Atualizar dados de mercado"):
    varrer_mercado_b3.clear()
    st.rerun()

with st.spinner("Consultando os dados disponíveis no Yahoo Finance..."):
    df = varrer_mercado_b3(tuple(UNIVERSO_B3))

if df.empty:
    st.error(
        "Não foi possível obter cotações. "
        "Verifique sua conexão e tente atualizar os dados."
    )
    st.stop()

# =========================================================
# 7. SCORE DINÂMICO E FILTROS
# =========================================================

df = calcular_scores(df)

if perfil_risco == "Conservador":
    riscos_permitidos = ["Baixo"]
elif perfil_risco == "Moderado":
    riscos_permitidos = ["Baixo", "Médio"]
else:
    riscos_permitidos = ["Baixo", "Médio", "Alto"]

df_filtrado = df[
    df["risco"].isin(riscos_permitidos)
].copy()

# Sem pesos, não há ranking fundamentado nas preferências.
if soma_pesos == 0:
    st.warning(
        "Todos os pesos estão zerados. "
        "Ajuste ao menos um indicador para gerar o ranking."
    )
    st.stop()

# =========================================================
# 8. CONSTRUÇÃO DA CARTEIRA
# Recalculada automaticamente em cada interação.
# =========================================================

alocacao = obter_alocacao(perfil_risco)
carteira = []

for classe, peso_alvo in alocacao.items():
    valor_classe = capital_total * peso_alvo

    if valor_classe <= 0:
        continue

    if classe == "Renda Fixa":
        # Simulação ilustrativa, não uma cotação ao vivo.
        carteira.append({
            "Classe": "Renda Fixa",
            "Ativo": "Reserva de renda fixa (simulada)",
            "Setor": "Renda Fixa",
            "Risco": "Baixo",
            "Preço (R$)": np.nan,
            "Score": np.nan,
            "Alvo (%)": peso_alvo * 100,
            "Valor (R$)": valor_classe,
            "Observação": (
                "Escolha o produto e confirme taxa, "
                "prazo, liquidez e tributação."
            ),
        })
        continue

    candidatos = df_filtrado[
        (df_filtrado["classe"] == classe)
        & (df_filtrado["prazo_min"] <= horizonte_anos)
        & (df_filtrado["Score"].notna())
    ].copy()

    candidatos = candidatos.sort_values(
        "Score", ascending=False
    )

    selecionados = candidatos.head(2)

    if selecionados.empty:
        st.warning(
            f"Não há candidatos elegíveis para {classe} "
            "com os filtros atuais."
        )
        continue

    # Distribuição igualitária entre os selecionados.
    valor_por_ativo = valor_classe / len(selecionados)

    for _, ativo in selecionados.iterrows():
        carteira.append({
            "Classe": classe,
            "Ativo": ativo["ticker"],
            "Setor": ativo["setor"],
            "Risco": ativo["risco"],
            "Preço (R$)": round(ativo["preco"], 2),
            "Score": round(ativo["Score"], 2),
            "Alvo (%)": round(
                peso_alvo * 100 / len(selecionados), 2
            ),
            "Valor (R$)": round(valor_por_ativo, 2),
        })

# =========================================================
# 9. RESULTADOS
# =========================================================

st.subheader("📊 Carteira sugerida")

df_carteira = pd.DataFrame(carteira)

if df_carteira.empty:
    st.warning(
        "Nenhum ativo elegível para os parâmetros escolhidos."
    )
else:
    st.dataframe(df_carteira, use_container_width=True)

    total_alocado = df_carteira["Valor (R$)"].sum()
    col1, col2, col3 = st.columns(3)

    col1.metric("Capital disponível", f"R$ {capital_total:,.2f}")
    col2.metric("Capital alocado", f"R$ {total_alocado:,.2f}")
    col3.metric(
        "Saldo não alocado",
        f"R$ {capital_total - total_alocado:,.2f}"
    )

st.subheader("🏆 Ranking dos ativos")

colunas_ranking = [
    "ticker", "classe", "setor", "risco", "preco",
    "dy", "roe", "pl", "divida_pl", "Score"
]

ranking = df_filtrado.sort_values(
    "Score", ascending=False, na_position="last"
)

st.dataframe(
    ranking[colunas_ranking].rename(columns={
        "ticker": "Ativo",
        "classe": "Classe",
        "setor": "Setor",
        "risco": "Risco",
        "preco": "Preço (R$)",
        "dy": "Dividend Yield",
        "roe": "ROE",
        "pl": "P/L",
        "divida_pl": "Dívida/PL",
    }),
    use_container_width=True
)

st.caption(
    "Dados sujeitos à disponibilidade e aos atrasos do Yahoo Finance. "
    "Os indicadores ausentes são tratados como indisponíveis. "
    "Os scores são relativos ao universo consultado, não garantias "
    "de retorno. A renda fixa exibida é ilustrativa."
)
