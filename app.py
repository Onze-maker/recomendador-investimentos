
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="Motor Quantitativo B3", page_icon="⚡", layout="wide")
st.title("⚡ Motor Quantitativo B3")
st.caption("Ranking heurístico com pesos, perfil, horizonte e comparação setorial.")

# ---------------------------------------------------------
# 1. PARÂMETROS
# ---------------------------------------------------------
st.sidebar.header("Parâmetros")
capital = st.sidebar.number_input("Capital disponível (R$)", 100.0, value=100000.0, step=1000.0)
perfil = st.sidebar.selectbox("Perfil", ["Conservador", "Moderado", "Arrojado"])
horizonte = st.sidebar.slider("Horizonte (anos)", 1, 30, 5)

st.sidebar.header("Pesos (0 a 10)")
pesos = {
    "DY": st.sidebar.slider("Dividend Yield", 0, 10, 5),
    "ROE": st.sidebar.slider("ROE", 0, 10, 5),
    "PL": st.sidebar.slider("Valuation / P/L", 0, 10, 5),
    "SOL": st.sidebar.slider("Solidez / Dívida/PL", 0, 10, 5),
}
if sum(pesos.values()) == 0:
    st.warning("Defina peso maior que zero em pelo menos um indicador.")
    st.stop()

# ---------------------------------------------------------
# 2. UNIVERSO
# ---------------------------------------------------------
ACOES = [
    "TAEE11.SA", "CPLE6.SA", "EGIE3.SA", "CMIG4.SA", "ENEV3.SA",
    "SBSP3.SA", "SAPR11.SA", "ITUB4.SA", "BBAS3.SA", "BBDC4.SA",
    "SANB11.SA", "BPAC11.SA", "PETR4.SA", "VALE3.SA", "CSNA3.SA",
    "PRIO3.SA", "SUZB3.SA", "KLBN11.SA", "WEGE3.SA", "RENT3.SA",
    "RADL3.SA", "LREN3.SA", "ABEV3.SA", "MGLU3.SA", "VAMO3.SA",
]
FIIS = [
    "MXRF11.SA", "KNCR11.SA", "CPTS11.SA", "HGLG11.SA",
    "XPML11.SA", "VISC11.SA", "IRDM11.SA", "BTLG11.SA",
]
UNIVERSO = ACOES + FIIS

@st.cache_data(ttl=3600, show_spinner=False)
def coletar(tickers):
    linhas = []
    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).info or {}
            preco = info.get("currentPrice") or info.get("regularMarketPrice")
            if preco is None or not np.isfinite(float(preco)) or float(preco) <= 0:
                continue

            def num(campo):
                try:
                    x = info.get(campo)
                    return float(x) if x is not None and np.isfinite(float(x)) else np.nan
                except (ValueError, TypeError):
                    return np.nan

            classe = "FIIs" if ticker in FIIS else "Ações"
            beta = num("beta")
            risco = (
                "Desconhecido" if pd.isna(beta)
                else "Baixo" if beta < 0.7
                else "Médio" if beta <= 1.2
                else "Alto"
            )
            linhas.append({
                "Ativo": ticker.replace(".SA", ""),
                "Classe": classe,
                "Setor": info.get("sector") or (
                    "FIIs - setor não informado" if classe == "FIIs"
                    else "Setor não informado"
                ),
                "Preço": float(preco),
                "DY": num("dividendYield"),
                "ROE": num("returnOnEquity"),
                "PL": num("trailingPE"),
                "SOL": num("debtToEquity"),
                "Beta": beta,
                "Risco": risco,
                "Prazo mínimo": 2 if classe == "FIIs" else 5 if risco == "Alto" else 3,
            })
        except Exception:
            continue
    return pd.DataFrame(linhas)

if st.sidebar.button("Atualizar dados de mercado"):
    coletar.clear()
    st.rerun()

with st.spinner("Consultando dados disponíveis..."):
    df = coletar(tuple(UNIVERSO))

if df.empty:
    st.error("Não foi possível obter dados. Tente atualizar mais tarde.")
    st.stop()

# ---------------------------------------------------------
# 3. VALIDAÇÃO E NORMALIZAÇÃO ROBUSTA
# ---------------------------------------------------------
# Valores inválidos não devem ser convertidos em boas pontuações.
df["DY"] = df["DY"].where(df["DY"].between(0, 1))
df["ROE"] = df["ROE"].where(df["ROE"].between(-1, 2))
df["PL"] = df["PL"].where(df["PL"] > 0)
# debtToEquity costuma ser expresso em pontos percentuais.
df["SOL"] = df["SOL"].where(df["SOL"].between(0, 1000))
df["Beta"] = df["Beta"].where(df["Beta"].between(-2, 5))

# A classificação é relativa à classe, não compara diretamente
# métricas de ações com métricas de FIIs.
colunas_score = {
    "DY": "Score DY",
    "ROE": "Score ROE",
    "PL": "Score P/L",
    "SOL": "Score Solidez",
}

for indicador, coluna in colunas_score.items():
    df[coluna] = np.nan
    for classe, indices in df.groupby("Classe").groups.items():
        serie = df.loc[indices, indicador].copy()
        validos = serie.dropna()
        if len(validos) < 3:
            # Amostra insuficiente para uma classificação relativa útil.
            continue

        # Winsorização: limita a influência de extremos no ranking.
        minimo = validos.quantile(0.05)
        maximo = validos.quantile(0.95)
        serie = serie.clip(minimo, maximo)

        ranks = serie.rank(pct=True)
        if indicador in ("PL", "SOL"):
            ranks = 1 - ranks

        df.loc[indices, coluna] = ranks * 10

# ---------------------------------------------------------
# 4. SCORE FUNDAMENTALISTA E COBERTURA
# ---------------------------------------------------------
total_peso = sum(pesos.values())
numerador = pd.Series(0.0, index=df.index)
peso_disponivel = pd.Series(0.0, index=df.index)

for indicador, peso in pesos.items():
    if peso == 0:
        continue
    coluna = colunas_score[indicador]
    ok = df[coluna].notna()
    numerador.loc[ok] += df.loc[ok, coluna] * peso
    peso_disponivel.loc[ok] += peso

df["Cobertura (%)"] = peso_disponivel / total_peso * 100
df["Score fundamentalista"] = numerador.div(
    peso_disponivel.where(peso_disponivel > 0)
)

# Exige pelo menos 60% do peso escolhido com dados disponíveis.
df.loc[df["Cobertura (%)"] < 60, "Score fundamentalista"] = np.nan

# ---------------------------------------------------------
# 5. PERFIL + HORIZONTE NO SCORE
# ---------------------------------------------------------
multiplicador_perfil = {
    "Conservador": 2.0, "Moderado": 1.0, "Arrojado": 0.35
}[perfil]

multiplicador_prazo = (
    2.0 if horizonte <= 2 else
    1.3 if horizonte <= 5 else
    1.0 if horizonte <= 10 else 0.7
)

df["Penalidade risco"] = (
    (df["Beta"].clip(lower=0) - 0.7).clip(lower=0)
    * multiplicador_perfil * multiplicador_prazo
).clip(upper=5)

df.loc[df["Beta"].isna(), "Penalidade risco"] = min(
    5.0, 1.5 * multiplicador_perfil * multiplicador_prazo
)

df["Ajuste horizonte"] = 0.0
if horizonte <= 2:
    df["Ajuste horizonte"] = (
        df["Score Solidez"].fillna(5) * 0.15
        + df["Score DY"].fillna(5) * 0.05 - 1
    )
elif horizonte >= 10:
    df["Ajuste horizonte"] = (
        df["Score ROE"].fillna(5) * 0.10
        + df["Score Solidez"].fillna(5) * 0.10 - 1
    )

df["Score final"] = (
    df["Score fundamentalista"] + df["Ajuste horizonte"]
    - df["Penalidade risco"]
).clip(0, 10)

# ---------------------------------------------------------
# 6. ELEGIBILIDADE EXPLÍCITA
# ---------------------------------------------------------
limite_beta = {
    "Conservador": 0.9, "Moderado": 1.2, "Arrojado": 2.0
}[perfil]

df["Motivo exclusão"] = ""

df.loc[df["Score fundamentalista"].isna(), "Motivo exclusão"] = (
    "Dados insuficientes para score"
)
df.loc[
    df["Motivo exclusão"].eq("") & (df["Prazo mínimo"] > horizonte),
    "Motivo exclusão"
] = "Prazo mínimo superior ao horizonte"

if perfil == "Arrojado":
    beta_ok = df["Beta"].isna() | (df["Beta"] <= limite_beta)
else:
    beta_ok = df["Beta"].notna() & (df["Beta"] <= limite_beta)

df.loc[
    df["Motivo exclusão"].eq("") & ~beta_ok,
    "Motivo exclusão"
] = "Beta fora do limite do perfil ou ausente"

df["Elegível"] = df["Motivo exclusão"].eq("")

# ---------------------------------------------------------
# 7. MÉDIAS SETORIAIS
# Médias válidas, com contagem própria por indicador.
# P/L só considera P/L positivo.
# ---------------------------------------------------------
medias = df[["Classe", "Setor"]].drop_duplicates().copy()

for indicador in ("DY", "ROE", "PL", "SOL"):
    temp = df[["Classe", "Setor", indicador]].copy()
    if indicador == "PL":
        temp[indicador] = temp[indicador].where(temp[indicador] > 0)

    agg = temp.groupby(["Classe", "Setor"])[indicador].agg(
        ["mean", "count"]
    ).reset_index()
    agg = agg.rename(columns={
        "mean": f"Média {indicador}",
        "count": f"N {indicador}",
    })
    medias = medias.merge(agg, on=["Classe", "Setor"], how="left")

# ---------------------------------------------------------
# 8. ALOCAÇÃO
# ---------------------------------------------------------
alocacoes = {
    "Conservador": {"Renda Fixa": 0.85, "Ações": 0.05, "FIIs": 0.10},
    "Moderado": {"Renda Fixa": 0.50, "Ações": 0.30, "FIIs": 0.20},
    "Arrojado": {"Renda Fixa": 0.15, "Ações": 0.60, "FIIs": 0.25},
}
carteira = []

for classe, fracao in alocacoes[perfil].items():
    verba = capital * fracao
    if verba <= 0:
        continue

    if classe == "Renda Fixa":
        carteira.append({
            "Classe": classe,
            "Ativo": "Renda fixa (simulação, não cotação)",
            "Setor": "Renda Fixa",
            "Score": np.nan,
            "Alvo (%)": round(fracao * 100, 2),
            "Valor (R$)": round(verba, 2),
            "Observação": "Produto, taxa, prazo e liquidez não verificados",
        })
        continue

    candidatos = df[
        (df["Classe"] == classe) & df["Elegível"]
    ].sort_values("Score final", ascending=False).head(2).copy()

    if candidatos.empty:
        st.warning(
            f"{classe}: nenhum ativo elegível. "
            "A parcela ficará não alocada; veja os motivos no ranking."
        )
        continue

    # Distribui proporcionalmente ao score positivo.
    # Piso pequeno impede divisão por zero sem dar peso excessivo
    # a scores baixos.
    forcar = candidatos["Score final"].clip(lower=0.1)
    fracoes = forcar / forcar.sum()

    for (idx, ativo), proporcao in zip(candidatos.iterrows(), fracoes):
        item = {
            "Classe": classe,
            "Ativo": ativo["Ativo"],
            "Setor": ativo["Setor"],
            "Score": round(ativo["Score final"], 2),
            "Cobertura (%)": round(ativo["Cobertura (%)"], 1),
            "Alvo (%)": round(fracao * proporcao * 100, 2),
            "Valor (R$)": round(verba * proporcao, 2),
        }

        # Peso acima de 5: mostrar ativo, média e N setorial.
        for indicador, peso in pesos.items():
            if peso <= 5:
                continue

            linha = medias[
                (medias["Classe"] == ativo["Classe"])
                & (medias["Setor"] == ativo["Setor"])
            ]
            media = linha.iloc[0] if not linha.empty else None
            valor = ativo[indicador]

            if indicador in ("DY", "ROE"):
                item[f"{indicador} ativo (%)"] = (
                    round(valor * 100, 2) if pd.notna(valor) else "N/D"
                )
                item[f"Média setor {indicador} (%)"] = (
                    round(media[f"Média {indicador}"] * 100, 2)
                    if media is not None and pd.notna(media[f"Média {indicador}"])
                    else "N/D"
                )
                item[f"N setor {indicador}"] = (
                    int(media[f"N {indicador}"]) if media is not None else 0
                )
            elif indicador == "PL":
                item["P/L ativo"] = round(valor, 2) if pd.notna(valor) else "N/D"
                item["Média setor P/L"] = (
                    round(media["Média PL"], 2)
                    if media is not None and pd.notna(media["Média PL"])
                    else "N/D"
                )
                item["N setor P/L"] = int(media["N PL"]) if media is not None else 0
            elif indicador == "SOL":
                item["Dívida/PL ativo (%)"] = (
                    round(valor, 2) if pd.notna(valor) else "N/D"
                )
                item["Média setor Dívida/PL (%)"] = (
                    round(media["Média SOL"], 2)
                    if media is not None and pd.notna(media["Média SOL"])
                    else "N/D"
                )
                item["N setor Dívida/PL"] = int(media["N SOL"]) if media is not None else 0

        carteira.append(item)

# ---------------------------------------------------------
# 9. RESULTADOS
# ---------------------------------------------------------
st.subheader("Carteira sugerida")
st.caption(
    f"Perfil: {perfil} | Horizonte: {horizonte} anos | "
    f"Pesos DY/ROE/P-L/Solidez: "
    f"{pesos['DY']}/{pesos['ROE']}/{pesos['PL']}/{pesos['SOL']}"
)

resultado = pd.DataFrame(carteira)
if resultado.empty:
    st.info("Nenhum ativo selecionado.")
else:
    st.dataframe(resultado, use_container_width=True, hide_index=True)

alocado = resultado["Valor (R$)"].sum() if not resultado.empty else 0
c1, c2, c3 = st.columns(3)
c1.metric("Capital disponível", f"R$ {capital:,.2f}")
c2.metric("Capital alocado", f"R$ {alocado:,.2f}")
c3.metric("Saldo não alocado", f"R$ {capital - alocado:,.2f}")

st.subheader("Ranking e diagnóstico")
colunas = [
    "Ativo", "Classe", "Setor", "Risco", "Preço", "DY", "ROE",
    "PL", "SOL", "Beta", "Cobertura (%)", "Score fundamentalista",
    "Penalidade risco", "Ajuste horizonte", "Score final",
    "Elegível", "Motivo exclusão"
]
st.dataframe(
    df.sort_values("Score final", ascending=False, na_position="last")[colunas],
    use_container_width=True,
    hide_index=True
)

st.caption(
    "Dados do Yahoo Finance podem estar ausentes ou atrasados. "
    "As médias setoriais usam apenas o universo consultado e exibem "
    "a quantidade de observações válidas. A renda fixa é ilustrativa. "
    "Scores heurísticos não são previsão nem garantia de retorno."
)
