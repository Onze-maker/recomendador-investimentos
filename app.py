
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(
    page_title="Motor Quantitativo B3",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ Motor Quantitativo B3")
st.caption(
    "Seleção dinâmica por indicadores, perfil de risco e horizonte de investimento."
)

# =========================================================
# 1. PARÂMETROS DO USUÁRIO
# =========================================================

st.sidebar.header("1. Parâmetros")

capital = st.sidebar.number_input(
    "Capital disponível (R$)",
    min_value=100.0,
    value=100000.0,
    step=1000.0
)

perfil = st.sidebar.selectbox(
    "Perfil de risco",
    ["Conservador", "Moderado", "Arrojado"]
)

horizonte = st.sidebar.slider(
    "Horizonte de investimento (anos)",
    min_value=1,
    max_value=30,
    value=5
)

st.sidebar.header("2. Pesos dos indicadores")
st.sidebar.caption(
    "Os indicadores com peso acima de 5 serão exibidos "
    "com comparação entre o ativo e a média do setor."
)

peso_dy = st.sidebar.slider("Dividend Yield", 0, 10, 5)
peso_roe = st.sidebar.slider("ROE", 0, 10, 5)
peso_pl = st.sidebar.slider("Valuation / P/L", 0, 10, 5)
peso_sol = st.sidebar.slider("Solidez / Dívida", 0, 10, 5)

PESOS = {
    "DY": peso_dy,
    "ROE": peso_roe,
    "PL": peso_pl,
    "SOL": peso_sol,
}

# =========================================================
# 2. UNIVERSO DE ATIVOS
# =========================================================

ACOES = [
    "TAEE11.SA", "CPLE6.SA", "EGIE3.SA", "CMIG4.SA",
    "ENEV3.SA", "SBSP3.SA", "SAPR11.SA",
    "ITUB4.SA", "BBAS3.SA", "BBDC4.SA", "SANB11.SA",
    "BPAC11.SA", "PETR4.SA", "VALE3.SA", "CSNA3.SA",
    "PRIO3.SA", "SUZB3.SA", "KLBN11.SA", "WEGE3.SA",
    "RENT3.SA", "RADL3.SA", "LREN3.SA", "ABEV3.SA",
    "MGLU3.SA", "VAMO3.SA",
]

FIIS = [
    "MXRF11.SA", "KNCR11.SA", "CPTS11.SA", "HGLG11.SA",
    "XPML11.SA", "VISC11.SA", "IRDM11.SA", "BTLG11.SA",
]

UNIVERSO = ACOES + FIIS

# =========================================================
# 3. COLETA DE DADOS DE MERCADO
# =========================================================

@st.cache_data(ttl=3600, show_spinner=False)
def coletar_dados(tickers):
    registros = []

    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).info or {}

            preco = (
                info.get("currentPrice")
                or info.get("regularMarketPrice")
                or info.get("regularMarketPreviousClose")
            )

            if preco is None or preco <= 0:
                continue

            def numero(campo):
                valor = info.get(campo)
                if valor is None:
                    return np.nan
                try:
                    valor = float(valor)
                    return valor if np.isfinite(valor) else np.nan
                except (ValueError, TypeError):
                    return np.nan

            classe = "FIIs" if ticker in FIIS else "Ações"

            beta = numero("beta")
            divida_pl = numero("debtToEquity")

            if pd.isna(beta):
                risco = "Desconhecido"
            elif beta < 0.7:
                risco = "Baixo"
            elif beta <= 1.2:
                risco = "Médio"
            else:
                risco = "Alto"

            # Prazo mínimo indicativo para esta estratégia.
            if classe == "FIIs":
                prazo_min = 2
            elif risco == "Alto":
                prazo_min = 5
            else:
                prazo_min = 3

            registros.append({
                "Ativo": ticker.replace(".SA", ""),
                "Classe": classe,
                "Setor": (
                    info.get("sector")
                    or ("Fundos Imobiliários" if classe == "FIIs"
                        else "Setor não informado")
                ),
                "Preço": float(preco),
                "DY": numero("dividendYield"),
                "ROE": numero("returnOnEquity"),
                "PL": numero("trailingPE"),
                "SOL": divida_pl,
                "Beta": beta,
                "Risco": risco,
                "Prazo mínimo": prazo_min,
            })

        except Exception:
            continue

    colunas = [
        "Ativo", "Classe", "Setor", "Preço", "DY", "ROE",
        "PL", "SOL", "Beta", "Risco", "Prazo mínimo"
    ]

    return pd.DataFrame(registros, columns=colunas)


if st.sidebar.button("🔄 Atualizar dados de mercado"):
    coletar_dados.clear()
    st.rerun()

with st.spinner("Consultando indicadores disponíveis..."):
    df = coletar_dados(tuple(UNIVERSO))

if df.empty:
    st.error(
        "Não foi possível carregar os dados. "
        "Verifique a conexão e tente atualizar."
    )
    st.stop()

# =========================================================
# 4. MÉDIAS SETORIAIS
# Calculadas antes dos filtros de risco e prazo.
# =========================================================

indicadores = ["DY", "ROE", "PL", "SOL"]

medias = (
    df.groupby(["Classe", "Setor"], dropna=False)[indicadores]
    .mean()
    .reset_index()
)

medias = medias.rename(columns={
    "DY": "Média setor DY",
    "ROE": "Média setor ROE",
    "PL": "Média setor P/L",
    "SOL": "Média setor Dívida/PL",
})

# =========================================================
# 5. SCORE FUNDAMENTALISTA
# Comparação relativa dentro de cada classe de ativo.
# =========================================================

df["Score DY"] = (
    df.groupby("Classe")["DY"].rank(pct=True) * 10
)

df["Score ROE"] = (
    df.groupby("Classe")["ROE"].rank(pct=True) * 10
)

# P/L menor é preferível; P/L negativo ou ausente não é usado.
pl_valido = df["PL"].where(df["PL"] > 0)

df["Score P/L"] = (
    1 - pl_valido.groupby(df["Classe"]).rank(pct=True)
) * 10

# Menor dívida sobre patrimônio é preferível.
df["Score Solidez"] = (
    1 - df.groupby("Classe")["SOL"].rank(pct=True)
) * 10

COLUNAS_SCORE = {
    "DY": "Score DY",
    "ROE": "Score ROE",
    "PL": "Score P/L",
    "SOL": "Score Solidez",
}

soma_pesos = sum(PESOS.values())

if soma_pesos == 0:
    st.warning("Defina peso maior que zero em pelo menos um indicador.")
    st.stop()

numerador = pd.Series(0.0, index=df.index)
denominador = pd.Series(0.0, index=df.index)

for indicador, peso in PESOS.items():
    if peso == 0:
        continue

    coluna = COLUNAS_SCORE[indicador]
    disponivel = df[coluna].notna()

    numerador.loc[disponivel] += (
        df.loc[disponivel, coluna] * peso
    )
    denominador.loc[disponivel] += peso

df["Score fundamentalista"] = numerador.div(
    denominador.where(denominador > 0)
)

# =========================================================
# 6. PERFIL DE RISCO E HORIZONTE
# Ambos afetam a pontuação e a elegibilidade.
# =========================================================

limites_beta = {
    "Conservador": 0.9,
    "Moderado": 1.2,
    "Arrojado": 2.0,
}

multiplicador_perfil = {
    "Conservador": 2.0,
    "Moderado": 1.0,
    "Arrojado": 0.35,
}[perfil]

if horizonte <= 2:
    multiplicador_prazo = 2.0
elif horizonte <= 5:
    multiplicador_prazo = 1.3
elif horizonte <= 10:
    multiplicador_prazo = 1.0
else:
    multiplicador_prazo = 0.7

beta_positivo = df["Beta"].clip(lower=0)

df["Penalidade risco"] = (
    (beta_positivo - 0.7).clip(lower=0)
    * multiplicador_perfil
    * multiplicador_prazo
).clip(upper=5)

df.loc[df["Beta"].isna(), "Penalidade risco"] = min(
    5.0,
    1.5 * multiplicador_perfil * multiplicador_prazo
)

# Horizonte curto: maior importância da estabilidade e da renda.
# Horizonte longo: maior importância da eficiência e da solidez.
df["Ajuste horizonte"] = 0.0

if horizonte <= 2:
    df["Ajuste horizonte"] = (
        df["Score Solidez"].fillna(5) * 0.15
        + df["Score DY"].fillna(5) * 0.05
        - 1.0
    )
elif horizonte >= 10:
    df["Ajuste horizonte"] = (
        df["Score ROE"].fillna(5) * 0.10
        + df["Score Solidez"].fillna(5) * 0.10
        - 1.0
    )

df["Score final"] = (
    df["Score fundamentalista"]
    + df["Ajuste horizonte"]
    - df["Penalidade risco"]
).clip(lower=0, upper=10)

df.loc[
    df["Score fundamentalista"].isna(),
    "Score final"
] = np.nan

# =========================================================
# 7. ELEGIBILIDADE
# =========================================================

df["Elegível"] = (
    (df["Prazo mínimo"] <= horizonte)
    & df["Score final"].notna()
)

# Conservador e moderado exigem beta conhecido e dentro do limite.
# Para o arrojado, beta desconhecido é permitido com penalidade,
# mas continua sendo um dado ausente que exige cautela.
if perfil == "Arrojado":
    beta_ok = (
        df["Beta"].isna()
        | (df["Beta"] <= limites_beta[perfil])
    )
else:
    beta_ok = (
        df["Beta"].notna()
        & (df["Beta"] <= limites_beta[perfil])
    )

df["Elegível"] = df["Elegível"] & beta_ok

# =========================================================
# 8. ALOCAÇÃO POR PERFIL
# =========================================================

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

alocacao = alocacoes[perfil]

# =========================================================
# 9. MONTAGEM DA CARTEIRA
# =========================================================

carteira = []

for classe, fracao in alocacao.items():
    valor_classe = capital * fracao

    if valor_classe <= 0:
        continue

    if classe == "Renda Fixa":
        carteira.append({
            "Classe": "Renda Fixa",
            "Ativo": "Alocação ilustrativa em renda fixa",
            "Setor": "Renda Fixa",
            "Risco": "Depende do produto",
            "Preço (R$)": np.nan,
            "Score": np.nan,
            "Alvo (%)": round(fracao * 100, 2),
            "Valor (R$)": round(valor_classe, 2),
        })
        continue

    candidatos = df[
        (df["Classe"] == classe)
        & df["Elegível"]
    ].sort_values("Score final", ascending=False)

    selecionados = candidatos.head(2)

    if selecionados.empty:
        st.warning(
            f"Não há ativos elegíveis para {classe}. "
            "A parcela correspondente ficará não alocada."
        )
        continue

    valor_por_ativo = valor_classe / len(selecionados)

    for _, ativo in selecionados.iterrows():
        item = {
            "Classe": classe,
            "Ativo": ativo["Ativo"],
            "Setor": ativo["Setor"],
            "Risco": ativo["Risco"],
            "Preço (R$)": round(ativo["Preço"], 2),
            "Score": round(ativo["Score final"], 2),
            "Alvo (%)": round(
                fracao * 100 / len(selecionados), 2
            ),
            "Valor (R$)": round(valor_por_ativo, 2),
        }

        # Exibir ativo e média do setor sempre que peso > 5.
        # Percentuais para DY e ROE; múltiplo para P/L;
        # relação percentual para Dívida/PL.
        for indicador, peso in PESOS.items():
            if peso <= 5:
                continue

            media_setor = medias[
                (medias["Classe"] == ativo["Classe"])
                & (medias["Setor"] == ativo["Setor"])
            ]

            media = (
                media_setor.iloc[0]
                if not media_setor.empty else None
            )

            valor = ativo[indicador]

            if indicador == "DY":
                item["DY ativo (%)"] = (
                    round(valor * 100, 2)
                    if pd.notna(valor) else "N/D"
                )
                item["Média setor DY (%)"] = (
                    round(media["Média setor DY"] * 100, 2)
                    if media is not None
                    and pd.notna(media["Média setor DY"])
                    else "N/D"
                )

            elif indicador == "ROE":
                item["ROE ativo (%)"] = (
                    round(valor * 100, 2)
                    if pd.notna(valor) else "N/D"
                )
                item["Média setor ROE (%)"] = (
                    round(media["Média setor ROE"] * 100, 2)
                    if media is not None
                    and pd.notna(media["Média setor ROE"])
                    else "N/D"
                )

            elif indicador == "PL":
                item["P/L ativo"] = (
                    round(valor, 2)
                    if pd.notna(valor) else "N/D"
                )
                item["Média setor P/L"] = (
                    round(media["Média setor P/L"], 2)
                    if media is not None
                    and pd.notna(media["Média setor P/L"])
                    else "N/D"
                )

            elif indicador == "SOL":
                item["Dívida/PL ativo (%)"] = (
                    round(valor, 2)
                    if pd.notna(valor) else "N/D"
                )
                item["Média setor Dívida/PL (%)"] = (
                    round(media["Média setor Dívida/PL"], 2)
                    if media is not None
                    and pd.notna(media["Média setor Dívida/PL"])
                    else "N/D"
                )

        carteira.append(item)

df_carteira = pd.DataFrame(carteira)

# =========================================================
# 10. RESULTADOS
# =========================================================

st.subheader("📊 Carteira dinâmica")
st.caption(
    f"Perfil: {perfil} | Horizonte: {horizonte} anos | "
    f"Pesos DY/ROE/P-L/Solidez: "
    f"{peso_dy}/{peso_roe}/{peso_pl}/{peso_sol}"
)

if df_carteira.empty:
    st.warning("Nenhum ativo selecionado.")
else:
    st.dataframe(
        df_carteira,
        use_container_width=True,
        hide_index=True
    )

total_alocado = (
    df_carteira["Valor (R$)"].sum()
    if not df_carteira.empty else 0
)

saldo = capital - total_alocado

c1, c2, c3 = st.columns(3)
c1.metric("Capital disponível", f"R$ {capital:,.2f}")
c2.metric("Capital alocado", f"R$ {total_alocado:,.2f}")
c3.metric("Saldo não alocado", f"R$ {saldo:,.2f}")

st.subheader("🏆 Ranking completo")

colunas = [
    "Ativo", "Classe", "Setor", "Risco", "Preço",
    "DY", "ROE", "PL", "SOL", "Beta",
    "Score fundamentalista", "Penalidade risco",
    "Ajuste horizonte", "Score final", "Elegível"
]

ranking = df.sort_values(
    "Score final",
    ascending=False,
    na_position="last"
)

st.dataframe(
    ranking[colunas].rename(columns={
        "Preço": "Preço (R$)",
        "DY": "DY (decimal)",
        "ROE": "ROE (decimal)",
        "PL": "P/L",
        "SOL": "Dívida/PL (%)",
    }),
    use_container_width=True,
    hide_index=True
)

st.caption(
    "Fonte: Yahoo Finance. Os dados podem estar atrasados ou ausentes. "
    "Os scores e prazos são critérios heurísticos, não previsões "
    "de retorno. A renda fixa é ilustrativa e não representa "
    "uma cotação ou oferta de investimento. As médias setoriais "
    "usam os ativos disponíveis neste universo, antes dos filtros "
    "de elegibilidade."
)
