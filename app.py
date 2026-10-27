
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

# ============================================================
# CONFIGURAÇÃO
# ============================================================
st.set_page_config(
    page_title="B3 | Screener e Alocação",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Screener B3 — análise, curadoria e alocação")
st.caption(
    "Ferramenta quantitativa de triagem. Não constitui recomendação individual "
    "nem garantia de rentabilidade."
)

ACOES = [
    "ABEV3.SA", "BBAS3.SA", "BBDC4.SA", "BBSE3.SA", "B3SA3.SA",
    "BPAC11.SA", "CMIG4.SA", "CPFE3.SA", "CPLE6.SA", "CSAN3.SA",
    "EGIE3.SA", "ITSA4.SA", "ITUB4.SA", "KLBN11.SA", "PETR4.SA",
    "PRIO3.SA", "RADL3.SA", "RENT3.SA", "SANB11.SA", "SUZB3.SA",
    "TAEE11.SA", "TIMS3.SA", "VALE3.SA", "VIVT3.SA", "VAMO3.SA",
]

FIIS = [
    "HGLG11.SA", "KNRI11.SA", "MXRF11.SA", "VISC11.SA",
    "XPLG11.SA", "XPML11.SA", "CPTS11.SA", "BTLG11.SA",
]

PERFIS = {
    "Conservador": {"Ações": 0.05, "FIIs": 0.05, "Renda fixa": 0.90},
    "Moderado":    {"Ações": 0.30, "FIIs": 0.20, "Renda fixa": 0.50},
    "Arrojado":    {"Ações": 0.60, "FIIs": 0.25, "Renda fixa": 0.15},
}

# Pesos de referência para as categorias de ativos.
# A elegibilidade pode alterar a alocação efetiva.
PESOS_INDICADORES = {
    "DY": 3.0,
    "ROE": 3.0,
    "PL": 2.0,
    "SOL": 2.0,
}

CACHE_TTL = 3600


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================
def numero_seguro(valor):
    try:
        valor = float(valor)
        return valor if np.isfinite(valor) else np.nan
    except (TypeError, ValueError):
        return np.nan


def obter_info(ticker):
    """Consulta dados públicos via yfinance; alguns campos podem faltar."""
    try:
        ativo = yf.Ticker(ticker)
        info = ativo.info or {}

        nome = info.get("shortName") or ticker.replace(".SA", "")
        setor = info.get("sector") or info.get("industry") or "Não informado"

        dy = numero_seguro(info.get("dividendYield"))
        roe = numero_seguro(info.get("returnOnEquity"))
        pl = numero_seguro(info.get("trailingPE"))
        beta = numero_seguro(info.get("beta"))
        divida_pl = numero_seguro(info.get("debtToEquity"))
        margem = numero_seguro(info.get("profitMargins"))
        preco = numero_seguro(info.get("currentPrice"))

        # Alguns provedores retornam DY/ROE em fração; converter para %.
        dy_pct = dy * 100 if pd.notna(dy) and abs(dy) <= 2 else dy
        roe_pct = roe * 100 if pd.notna(roe) and abs(roe) <= 2 else roe
        margem_pct = (
            margem * 100 if pd.notna(margem) and abs(margem) <= 2 else margem
        )

        # debtToEquity do Yahoo costuma vir em pontos percentuais.
        # Valores negativos podem representar patrimônio líquido negativo
        # ou situações contábeis que exigem investigação.
        return {
            "Ticker": ticker,
            "Ativo": nome,
            "Setor": setor,
            "DY": dy_pct,
            "ROE": roe_pct,
            "PL": pl,
            "SOL": divida_pl,
            "Beta": beta,
            "Margem líquida": margem_pct,
            "Preço": preco,
            "Dados obtidos": datetime.now().strftime("%d/%m/%Y %H:%M"),
        }
    except Exception as erro:
        return {
            "Ticker": ticker,
            "Ativo": ticker.replace(".SA", ""),
            "Setor": "Não informado",
            "DY": np.nan,
            "ROE": np.nan,
            "PL": np.nan,
            "SOL": np.nan,
            "Beta": np.nan,
            "Margem líquida": np.nan,
            "Preço": np.nan,
            "Dados obtidos": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "Erro": str(erro)[:180],
        }


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def carregar_universo(tickers):
    registros = [obter_info(ticker) for ticker in tickers]
    return pd.DataFrame(registros)


def normalizar_indicadores(df):
    """Transforma indicadores em notas percentílicas de 0 a 10."""
    df = df.copy()

    # Limites de plausibilidade. Não são limites universais de qualidade.
    df["DY"] = df["DY"].where(df["DY"].between(0, 100))
    df["ROE"] = df["ROE"].where(df["ROE"].between(-100, 200))
    df["PL"] = df["PL"].where(df["PL"] > 0)
    df["SOL"] = df["SOL"].where(df["SOL"].between(0, 2000))

    for indicador in ["DY", "ROE", "PL", "SOL"]:
        coluna_nota = f"Nota {indicador}"
        df[coluna_nota] = np.nan

        for _, indices in df.groupby("Classe").groups.items():
            serie = df.loc[indices, indicador]
            validos = serie.dropna()

            if len(validos) < 3:
                continue

            # Reduz a influência de valores extremos na comparação.
            p05 = validos.quantile(0.05)
            p95 = validos.quantile(0.95)
            serie_limitada = serie.clip(lower=p05, upper=p95)
            ranks = serie_limitada.rank(pct=True)

            # Menor P/L positivo e menor dívida/PL recebem nota maior.
            if indicador in ["PL", "SOL"]:
                ranks = 1 - ranks

            df.loc[indices, coluna_nota] = ranks * 10

    return df


def pontuar(df, pesos):
    df = df.copy()
    colunas = [f"Nota {k}" for k in pesos]
    peso_total = sum(pesos.values())

    df["Cobertura"] = 0.0
    df["Score"] = np.nan

    for indice, linha in df.iterrows():
        soma_pesos_presentes = sum(
            pesos[k] for k in pesos
            if pd.notna(linha.get(f"Nota {k}", np.nan))
        )
        df.loc[indice, "Cobertura"] = (
            soma_pesos_presentes / peso_total if peso_total else 0
        )

        # Evita dar nota alta a um ativo com poucos dados.
        if soma_pesos_presentes >= 0.60 * peso_total:
            numerador = sum(
                linha[f"Nota {k}"] * pesos[k]
                for k in pesos
                if pd.notna(linha.get(f"Nota {k}", np.nan))
            )
            df.loc[indice, "Score"] = numerador / soma_pesos_presentes

    return df


def elegibilidade(linha, perfil, horizonte):
    motivos = []
    classe = linha["Classe"]

    # Regras prudenciais de triagem, não leis universais de investimento.
    if horizonte <= 2 and classe in ["Ações", "FIIs"]:
        motivos.append("Prazo curto para renda variável")
    elif horizonte <= 4 and classe == "Ações":
        motivos.append("Prazo exige atenção à volatilidade")

    beta = linha.get("Beta", np.nan)
    if perfil == "Conservador":
        if pd.isna(beta):
            motivos.append("Beta indisponível")
        elif beta > 1.0:
            motivos.append("Beta acima de 1")
    elif perfil == "Moderado":
        if pd.notna(beta) and beta > 1.5:
            motivos.append("Beta elevado")

    if pd.isna(linha.get("Score", np.nan)):
        motivos.append("Dados insuficientes para pontuação")

    if linha.get("Cobertura", 0) < 0.60:
        motivos.append("Cobertura de indicadores abaixo de 60%")

    return len(motivos) == 0, motivos


def gerar_alertas(linha, pares):
    alertas = []
    ticker = linha["Ticker"]
    classe = linha["Classe"]

    dy = linha.get("DY", np.nan)
    roe = linha.get("ROE", np.nan)
    pl = linha.get("PL", np.nan)
    sol = linha.get("SOL", np.nan)
    beta = linha.get("Beta", np.nan)
    cobertura = linha.get("Cobertura", 0)

    if pd.isna(dy):
        alertas.append(("Dados", "Dividend yield indisponível ou fora da faixa de validação."))
    elif dy > 15:
        alertas.append(("Investigar", f"DY de {dy:.1f}% é muito elevado. Verifique distribuições extraordinárias, queda do preço e sustentabilidade dos pagamentos."))
    elif dy > 10:
        alertas.append(("Atenção", f"DY de {dy:.1f}% merece comparação com o histórico e os pares."))

    if classe == "Ações":
        if pd.isna(roe):
            alertas.append(("Dados", "ROE indisponível; a avaliação da rentabilidade fica incompleta."))
        elif roe < 0:
            alertas.append(("Risco", f"ROE negativo ({roe:.1f}%). Investigue prejuízos e efeitos contábeis."))

        if pd.isna(pl):
            alertas.append(("Dados", "P/L positivo não disponível. Pode haver prejuízo, ausência de dados ou lucro não comparável."))
        elif pl < 5:
            alertas.append(("Investigar", f"P/L de {pl:.1f} é baixo; não significa necessariamente que a ação esteja barata."))
        elif pl > 35:
            alertas.append(("Atenção", f"P/L de {pl:.1f} é elevado. Compare crescimento, setor e qualidade dos lucros."))

    if pd.isna(sol):
        alertas.append(("Dados", "Dívida/PL indisponível."))
    elif sol > 200:
        alertas.append(("Risco", f"Dívida/PL de {sol:.0f}%: investigue alavancagem e capacidade de pagamento."))
    elif sol < 0:
        alertas.append(("Investigar", "Dívida/PL negativo pode refletir patrimônio líquido negativo; a métrica não deve ser interpretada como dívida baixa."))

    if pd.isna(beta):
        alertas.append(("Dados", "Beta indisponível; o risco de mercado não foi avaliado por essa métrica."))
    elif beta > 1.5:
        alertas.append(("Risco", f"Beta de {beta:.2f} indica sensibilidade histórica elevada ao mercado."))

    if cobertura < 0.60:
        alertas.append(("Dados", f"Cobertura de indicadores de apenas {cobertura:.0%}; pontuação não confiável para comparação."))

    if len(pares) < 3:
        alertas.append(("Comparabilidade", "Há poucos pares no grupo; a classificação relativa pode ser instável."))

    if not alertas:
        alertas.append(("Observação", "Nenhum alerta automático foi disparado. Isso não elimina riscos nem substitui análise dos demonstrativos."))

    return alertas


def alocar_categoria(df, capital_categoria, limite_ativo=0.40):
    """
    Aloca proporcionalmente ao score, com limite por ativo.
    O valor não alocado permanece explícito se o limite impedir distribuir tudo.
    """
    if df.empty or capital_categoria <= 0:
        return pd.DataFrame(), capital_categoria

    candidatos = df.dropna(subset=["Score"]).sort_values("Score", ascending=False).copy()
    if candidatos.empty:
        return pd.DataFrame(), capital_categoria

    candidatos = candidatos.head(5).copy()
    scores = candidatos["Score"].clip(lower=0.1)
    pesos = scores / scores.sum()

    # Limite por ativo: redistribuição iterativa do saldo disponível.
    alocacoes = pd.Series(0.0, index=candidatos.index)
    restante = capital_categoria
    ativos_livres = list(candidatos.index)
    limite = capital_categoria * limite_ativo

    for _ in range(len(candidatos) + 1):
        if restante <= 0.01 or not ativos_livres:
            break

        scores_livres = scores.loc[ativos_livres]
        proporcoes = scores_livres / scores_livres.sum()
        distribuicao = proporcoes * restante
        excedentes = distribuicao[distribuicao + alocacoes.loc[distribuicao.index] > limite]

        if excedentes.empty:
            alocacoes.loc[distribuicao.index] += distribuicao
            restante = 0.0
            break

        for idx in excedentes.index:
            espaco = max(0, limite - alocacoes.loc[idx])
            alocacoes.loc[idx] += espaco
            restante -= espaco
            if idx in ativos_livres:
                ativos_livres.remove(idx)

    candidatos["Alocação (R$)"] = alocacoes
    candidatos["Peso no capital total (%)"] = np.nan
    return candidatos, max(0, restante)


# ============================================================
# CONTROLES
# ============================================================
st.sidebar.header("Parâmetros da análise")

perfil = st.sidebar.selectbox(
    "Perfil de risco",
    ["Conservador", "Moderado", "Arrojado"],
    index=1,
)

horizonte = st.sidebar.selectbox(
    "Horizonte de investimento",
    [1, 2, 3, 5, 10, 15],
    index=3,
    format_func=lambda x: f"{x} ano(s)",
)

capital = st.sidebar.number_input(
    "Capital disponível (R$)",
    min_value=100.0,
    value=100000.0,
    step=1000.0,
    help="Capital total que você deseja simular para alocação.",
)

st.sidebar.subheader("Pesos dos indicadores")
pesos = {
    "DY": st.sidebar.slider("Dividend yield (DY)", 0, 10, 3),
    "ROE": st.sidebar.slider("Retorno sobre patrimônio (ROE)", 0, 10, 3),
    "PL": st.sidebar.slider("Preço/Lucro (P/L)", 0, 10, 2),
    "SOL": st.sidebar.slider("Dívida/PL (SOL)", 0, 10, 2),
}
pesos = {k: float(v) for k, v in pesos.items()}

if sum(pesos.values()) == 0:
    st.sidebar.warning("Selecione pelo menos um peso maior que zero.")
    st.stop()

if st.sidebar.button("🔄 Atualizar dados de mercado"):
    carregar_universo.clear()

# ============================================================
# COLETA E ANÁLISE
# ============================================================
with st.spinner("Consultando os dados disponíveis..."):
    dados_acoes = carregar_universo(tuple(ACOES))
    dados_fiis = carregar_universo(tuple(FIIS))

dados_acoes["Classe"] = "Ações"
dados_fiis["Classe"] = "FIIs"
df = pd.concat([dados_acoes, dados_fiis], ignore_index=True)

df = normalizar_indicadores(df)
df = pontuar(df, pesos)

resultados_elegibilidade = df.apply(
    lambda linha: elegibilidade(linha, perfil, horizonte),
    axis=1,
)
df["Elegível"] = [resultado[0] for resultado in resultados_elegibilidade]
df["Motivos de exclusão"] = [
    "; ".join(resultado[1]) for resultado in resultados_elegibilidade
]

# Referência de renda fixa apenas ilustrativa: não representa uma oferta.
renda_fixa = pd.DataFrame([{
    "Ticker": "RF-ILUSTRATIVA",
    "Ativo": "Renda fixa — pesquisar produto compatível",
    "Classe": "Renda fixa",
    "Setor": "Não aplicável",
    "Score": np.nan,
    "DY": np.nan,
    "ROE": np.nan,
    "PL": np.nan,
    "SOL": np.nan,
    "Beta": np.nan,
    "Preço": np.nan,
    "Cobertura": np.nan,
    "Elegível": True,
    "Motivos de exclusão": "",
}])

# ============================================================
# VISÃO GERAL
# ============================================================
st.subheader("Resumo da análise")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Capital simulado", f"R$ {capital:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
c2.metric("Ativos analisados", len(df))
c3.metric("Elegíveis", int(df["Elegível"].sum()))
c4.metric("Perfil", perfil)

st.info(
    f"Perfil selecionado: **{perfil}**. Horizonte: **{horizonte} ano(s)**. "
    "A distribuição-base é uma hipótese configurável do modelo, não uma regra universal. "
    "A adequação depende também de reserva de emergência, dívidas, objetivos, liquidez "
    "e tolerância real a perdas."
)

# ============================================================
# RANKING
# ============================================================
st.subheader("Ranking quantitativo")

tab1, tab2, tab3 = st.tabs(["Ações", "FIIs", "Todos os ativos"])

colunas_exibicao = [
    "Ticker", "Ativo", "Setor", "Score", "DY", "ROE", "PL",
    "SOL", "Beta", "Cobertura", "Elegível", "Motivos de exclusão",
]

def mostrar_ranking(container, classe=None):
    base = df if classe is None else df[df["Classe"] == classe]
    base = base.sort_values("Score", ascending=False, na_position="last")
    container.dataframe(
        base[[c for c in colunas_exibicao if c in base.columns]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Score": st.column_config.NumberColumn("Score (0–10)", format="%.2f"),
            "DY": st.column_config.NumberColumn("DY (%)", format="%.2f"),
            "ROE": st.column_config.NumberColumn("ROE (%)", format="%.2f"),
            "PL": st.column_config.NumberColumn("P/L", format="%.2f"),
            "SOL": st.column_config.NumberColumn("Dívida/PL (%)", format="%.1f"),
            "Beta": st.column_config.NumberColumn("Beta", format="%.2f"),
            "Cobertura": st.column_config.ProgressColumn(
                "Cobertura dos dados", min_value=0, max_value=1, format="%.0%%"
            ),
        },
    )

mostrar_ranking(tab1, "Ações")
mostrar_ranking(tab2, "FIIs")
mostrar_ranking(tab3)

st.caption(
    "DY, ROE e dívida/PL são apresentados em percentual quando disponíveis. "
    "P/L considera apenas valores positivos na pontuação. Dados de mercado podem "
    "estar ausentes, atrasados ou inconsistentes; confirme-os em fontes oficiais."
)

# ============================================================
# CURADORIA CONCEITUAL
# ============================================================
st.subheader("📚 Como interpretar os indicadores")

with st.expander("Fundamentação e limites do modelo", expanded=True):
    st.markdown("""
**Dividend yield (DY)**  
Relação entre dividendos/distribuições e preço. Um valor alto pode ser atraente,
mas também pode refletir uma queda do preço ou pagamentos extraordinários. Em FIIs,
a distribuição passada não garante distribuição futura.

**ROE — retorno sobre patrimônio líquido**  
Indica o lucro contábil em relação ao patrimônio. Compare empresas do mesmo setor:
alavancagem, patrimônio reduzido e eventos não recorrentes podem distorcer o indicador.

**P/L — preço sobre lucro**  
Relaciona o preço da ação ao lucro por ação. P/L baixo não é sinônimo de ação barata;
pode refletir expectativas ruins ou lucro temporariamente elevado. P/L negativo não é
comparável da mesma forma e não recebe nota convencional neste modelo.

**Dívida/PL**  
Ajuda a avaliar a estrutura de capital, mas não tem interpretação idêntica em todos
os setores. Bancos, seguradoras, empresas industriais e FIIs exigem métricas próprias.
Valores ausentes ou negativos precisam de investigação, e não de uma conclusão automática.

**Beta**  
Estima a sensibilidade histórica aos movimentos do mercado. Não captura todos os riscos,
não é uma previsão e pode variar conforme janela e índice de referência.

**Score e ranking**  
As notas são percentis relativos ao universo disponível, não notas absolutas de qualidade.
O resultado depende dos pesos escolhidos, dos dados disponíveis e dos ativos comparados.
A pontuação não estima retorno futuro e não substitui leitura de balanços, fluxo de caixa,
governança, liquidez, preço atual e adequação ao objetivo do investidor.
""")

# ============================================================
# ALERTAS AUTOMÁTICOS
# ============================================================
st.subheader("🚨 Alertas e pontos fora do padrão")

st.caption(
    "Os alertas são sinais para investigação. Não são ordens automáticas de compra ou venda."
)

alertas_totais = []
for _, linha in df.iterrows():
    classe = linha["Classe"]
    pares = df[(df["Classe"] == classe) & (df["Ticker"] != linha["Ticker"])]
    alertas = gerar_alertas(linha, pares)

    for severidade, mensagem in alertas:
        alertas_totais.append({
            "Ticker": linha["Ticker"],
            "Ativo": linha["Ativo"],
            "Classe": classe,
            "Tipo": severidade,
            "Observação": mensagem,
        })

alertas_df = pd.DataFrame(alertas_totais)

filtro_alertas = st.multiselect(
    "Filtrar alertas por tipo",
    ["Risco", "Investigar", "Atenção", "Dados", "Comparabilidade", "Observação"],
    default=["Risco", "Investigar", "Atenção", "Dados"],
)

alertas_filtrados = alertas_df[alertas_df["Tipo"].isin(filtro_alertas)]
if alertas_filtrados.empty:
    st.success("Nenhum alerta corresponde aos filtros selecionados.")
else:
    st.dataframe(alertas_filtrados, use_container_width=True, hide_index=True)

st.markdown("**Observações gerais da análise**")
st.markdown("""
- Ativo com score alto não é necessariamente o mais seguro ou o mais barato.
- Um ativo pode liderar o ranking por ter bons indicadores relativos, mesmo que o setor
  inteiro esteja em condições desfavoráveis.
- A falta de dados não equivale a risco baixo. Campos ausentes devem ser verificados.
- O universo analisado é limitado e não representa todas as ações e todos os FIIs da B3.
- Comparações setoriais precisam de amostras adequadas e indicadores compatíveis.
- Antes de investir, verifique fatos relevantes, demonstrações financeiras, liquidez,
  custos, tributação e as regras do produto escolhido.
""")

# ============================================================
# ALOCAÇÃO DE CAPITAL
# ============================================================
st.subheader("💰 Simulação de alocação do capital")

distribuicao_base = PERFIS[perfil]
alocacao_base = {
    classe: capital * percentual
    for classe, percentual in distribuicao_base.items()
}

st.markdown("**Distribuição-base definida pelo perfil**")
base_df = pd.DataFrame([
    {
        "Categoria": categoria,
        "Percentual-base": percentual * 100,
        "Valor-base (R$)": alocacao_base[categoria],
    }
    for categoria, percentual in distribuicao_base.items()
])
st.dataframe(
    base_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Percentual-base": st.column_config.NumberColumn(format="%.1f%%"),
        "Valor-base (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
    },
)

st.caption(
    "As proporções são parâmetros didáticos do aplicativo, não uma carteira recomendada "
    "universalmente. Ajuste-as à sua situação financeira e aos seus objetivos."
)

# Só entram na simulação os ativos elegíveis e com score calculado.
alocacoes = []
saldo_nao_alocado = 0.0
resumo_categoria = []

for classe in ["Ações", "FIIs"]:
    capital_categoria = alocacao_base[classe]
    candidatos = df[
        (df["Classe"] == classe)
        & (df["Elegível"])
        & df["Score"].notna()
    ].sort_values("Score", ascending=False)

    carteira_classe, saldo = alocar_categoria(
        candidatos,
        capital_categoria,
        limite_ativo=0.40,
    )
    saldo_nao_alocado += saldo

    if not carteira_classe.empty:
        carteira_classe["Categoria"] = classe
        carteira_classe["Peso no capital total (%)"] = (
            carteira_classe["Alocação (R$)"] / capital * 100
        )
        alocacoes.append(carteira_classe)

    resumo_categoria.append({
        "Categoria": classe,
        "Capital-base (R$)": capital_categoria,
        "Capital alocado (R$)": (
            carteira_classe["Alocação (R$)"].sum()
            if not carteira_classe.empty else 0.0
        ),
        "Saldo não alocado (R$)": saldo,
        "Ativos elegíveis": len(candidatos),
    })

# Renda fixa não é selecionada por ticker pelo screener.
# O valor fica identificado como reserva para pesquisar produtos adequados.
resumo_categoria.append({
    "Categoria": "Renda fixa",
    "Capital-base (R$)": alocacao_base["Renda fixa"],
    "Capital alocado (R$)": 0.0,
    "Saldo não alocado (R$)": alocacao_base["Renda fixa"],
    "Ativos elegíveis": 0,
})
saldo_nao_alocado += alocacao_base["Renda fixa"]

resumo_df = pd.DataFrame(resumo_categoria)
st.markdown("**Resultado por categoria**")
st.dataframe(
    resumo_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Capital-base (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
        "Capital alocado (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
        "Saldo não alocado (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
    },
)

if alocacoes:
    carteira = pd.concat(alocacoes, ignore_index=True)
    carteira = carteira[carteira["Alocação (R$)"] > 0].copy()

    st.markdown("**Carteira simulada por ativo**")
    st.dataframe(
        carteira[[
            "Categoria", "Ticker", "Ativo", "Score",
            "Alocação (R$)", "Peso no capital total (%)",
        ]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Score": st.column_config.NumberColumn(format="%.2f"),
            "Alocação (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Peso no capital total (%)": st.column_config.NumberColumn(format="%.2f%%"),
        },
    )

    csv = carteira.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ Baixar simulação em CSV",
        data=csv,
        file_name="simulacao_carteira.csv",
        mime="text/csv",
    )
else:
    st.warning(
        "Nenhum ativo de renda variável passou pelos filtros atuais. "
        "O modelo não vai forçar uma alocação. Revise os filtros, os dados e o horizonte."
    )

st.metric(
    "Capital não alocado / reservado para decisão manual",
    f"R$ {saldo_nao_alocado:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
)

if resumo_df["Ativos elegíveis"].sum() == 0:
    st.warning(
        "Não há ativos elegíveis para ações ou FIIs. Considere manter o capital reservado "
        "enquanto investiga os dados, em vez de flexibilizar os critérios sem justificativa."
    )

# ============================================================
# COMPARAÇÃO SETORIAL
# ============================================================
st.subheader("🏭 Comparação setorial")

indicador_setor = st.selectbox(
    "Indicador para comparar setores",
    ["DY", "ROE", "PL", "SOL"],
)

setorial = df.dropna(subset=[indicador_setor]).copy()
if not setorial.empty:
    estatisticas = (
        setorial.groupby(["Classe", "Setor"])[indicador_setor]
        .agg(["mean", "median", "count"])
        .reset_index()
        .rename(columns={
            "mean": "Média",
            "median": "Mediana",
            "count": "N ativos",
        })
    )
    st.dataframe(estatisticas, use_container_width=True, hide_index=True)
    st.caption(
        "A média inclui os ativos disponíveis no universo consultado e pode incluir o "
        "próprio ativo comparado. Setores com poucos componentes ou métricas não comparáveis "
        "devem ser interpretados com cautela."
    )
else:
    st.info("Não há dados suficientes para construir a comparação setorial.")

# ============================================================
# LIMITAÇÕES E PRÓXIMOS PASSOS
# ============================================================
with st.expander("⚠️ Limitações importantes antes de usar a simulação"):
    st.markdown("""
1. **Dados:** o Yahoo Finance pode apresentar campos ausentes, defasados ou inconsistentes.
   Confira os números nos documentos e canais oficiais das empresas e fundos.
2. **Universo limitado:** esta lista é apenas uma amostra de ações e FIIs negociados na B3.
3. **Modelo heurístico:** pesos, filtros e limites de concentração são escolhas de projeto,
   não parâmetros estatisticamente validados.
4. **Risco:** beta não substitui análise de volatilidade, liquidez, drawdown, correlação,
   concentração, crédito ou risco de negócio.
5. **Renda fixa:** compare emissor, prazo, liquidez, tributação, cobertura do FGC quando aplicável
   e condições de resgate. O app não consulta ofertas atuais de renda fixa.
6. **Custos e execução:** a simulação não considera corretagem, spread, impostos, lotes,
   preços de execução nem o arredondamento de quantidades negociáveis.
7. **Adequação pessoal:** antes de investir, considere reserva de emergência, dívidas,
   necessidade de liquidez, objetivos e capacidade de suportar perdas.
""")

st.caption(
    f"Última atualização da tela: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} "
    "| Fonte de dados de mercado: yfinance | Cache: 1 hora"
)
