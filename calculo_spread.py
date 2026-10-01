import pandas as pd
import numpy as np

from relatorio import gerar_relatorio_html, exportar_excel


# ============================================================
# ESCALA DE RATING
# ============================================================
# As agências (Fitch, S&P, Moody's) aparecem no formato
# "AGÊNCIA | NOTA". Todas as notas da base já estão na escala
# nacional no padrão S&P/Fitch (AAA, AA+, ...), inclusive as da
# Moody's, então basta extrair a nota e agrupar em faixas.

ORDEM_NOTAS = ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-",
               "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-",
               "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC", "C", "D"]

ORDEM_FAIXAS = ["AAA", "AA", "A", "BBB", "Especulativo (<=BB)"]


def extrair_nota(rating_bruto):
    """
    Extrai a nota de um texto no formato "AGÊNCIA | NOTA".
    Retorna NaN para valores vazios ou notas fora da escala
    (ex.: "Retirado").
    """
    if pd.isna(rating_bruto):
        return np.nan

    nota = str(rating_bruto).split("|")[-1].strip().upper()

    return nota if nota in ORDEM_NOTAS else np.nan


def faixa_rating(nota):
    """
    Agrupa a nota em faixas: AAA, AA, A, BBB e Especulativo.
    """
    if pd.isna(nota):
        return np.nan

    base = nota.rstrip("+-")

    if base in ["AAA", "AA", "A", "BBB"]:
        return base

    return "Especulativo (<=BB)"


def preparar_rating(debentures_rating):
    """
    Padroniza a tabela de rating: uma linha por Código CETIP,
    com a nota e a faixa de rating.

    Usa o Rating 1 quando ele é uma nota válida; caso contrário,
    usa o Rating 2 (ex.: Rating 1 = "Retirado").
    """
    rating = debentures_rating.copy()
    rating.columns = rating.columns.str.strip()

    # Linhas de cabeçalho/rodapé da planilha vêm sem código
    rating = rating.dropna(subset=["Código CETIP"])

    #extrair a nota de cada rating (Rating 1 e Rating 2)
    nota_1 = rating["Rating 1"].map(extrair_nota)
    nota_2 = rating["Rating 2"].map(extrair_nota)
    # Se Rating 1 for inválido, usar Rating 2
    # Entendo que o rating 1 é o mais recente, então se ele for inválido, usamos o rating 2
    rating["Nota"] = nota_1.fillna(nota_2)
    rating["Agencia"] = (
        rating["Rating 1"].where(nota_1.notna(), rating["Rating 2"])
        .str.split("|").str[0].str.strip()
        .str.replace("MOODYS", "MOODY'S")
    )
    # Garantir que a nota seja categórica ordenada (para poder ordenar por faixa de rating)
    rating["Faixa Rating"] = rating["Nota"].map(faixa_rating)

    rating = (
        rating
        .dropna(subset=["Nota"])
        .drop_duplicates(subset=["Código CETIP"])
        .rename(columns={"Código CETIP": "Código"})
    )
    # Garantir que as colunas de nota e faixa de rating sejam categóricas ordenadas
    rating["Nota"] = pd.Categorical(rating["Nota"], ORDEM_NOTAS, ordered=True)
    rating["Faixa Rating"] = pd.Categorical(rating["Faixa Rating"], ORDEM_FAIXAS, ordered=True)

    return rating[["Código", "Agencia", "Nota", "Faixa Rating"]]


# ============================================================
# FUNÇÃO PARA INTERPOLAR A CURVA NTN-B
# ============================================================

def interpolar_ntnb(curva_ntnb, duration_debenture):
    """
    Interpola a taxa de uma NTN-B para uma ou mais durations.

    Parâmetros
    ----------
    curva_ntnb : pd.DataFrame
        DataFrame contendo as NTN-Bs disponíveis para UMA data.
        Deve possuir as colunas:
            - Duration (em anos)
            - Taxa Indicativa

    duration_debenture : float ou array
        Duration (em anos) das debêntures para as quais queremos
        encontrar a taxa equivalente na curva de NTN-B.

    Retorno
    -------
    np.ndarray
        Taxas NTN-B interpoladas. NaN quando a duration está fora
        do intervalo da curva (não fazemos extrapolação).
    """

    # ------------------------------------------------------------
    # 1. Selecionar apenas as informações necessárias para a curva
    # ------------------------------------------------------------
    curva = curva_ntnb[
        ["Duration", "Taxa Indicativa"]
    ].dropna().copy()
    
    # garantir que duration_debenture seja um array numpy de números decimais com pelo menos uma dimensão
    # np.asarray(..., dtype=float) converte a entrada em array NumPy de float. A entrada pode ser uma lista, uma Series do pandas, um array ou um número solto.
    # np.atleast_1d(...) pega um número solto, que vira um array de dimensão 0, e o transforma num array com um elemento. Por exemplo, 5.2 vira array([5.2]). Se a entrada já for um array, nada muda.
    duration_debenture = np.atleast_1d(np.asarray(duration_debenture, dtype=float))

    # ------------------------------------------------------------
    # 2. Verificar se existem observações suficientes
    # ------------------------------------------------------------
    # Para fazer uma interpolação linear precisamos de, no mínimo,
    # dois pontos diferentes da curva.
    if len(curva) < 2:
        return np.full(len(duration_debenture), np.nan)

    # ------------------------------------------------------------
    # 3. Garantir que não existam duas taxas para a mesma duration
    # ------------------------------------------------------------
    # Pode acontecer de existirem mais de uma NTN-B com a mesma
    # duration. Nesse caso, utilizamos a média das taxas para criar
    # um único ponto da curva.
    curva = (
        curva
        .groupby("Duration", as_index=False)["Taxa Indicativa"]
        .mean()
        .sort_values("Duration")
    )

    # ------------------------------------------------------------
    # 4. Criar os vetores utilizados na interpolação
    # ------------------------------------------------------------
    x = curva["Duration"].to_numpy()
    y = curva["Taxa Indicativa"].to_numpy()

    # ------------------------------------------------------------
    # 5. Interpolar e descartar o que estiver fora da curva
    # ------------------------------------------------------------
    # Uma extrapolação pode produzir uma taxa artificialmente
    # estimada fora da região em que temos dados de mercado.
    taxa_interpolada = np.interp(duration_debenture, x, y)

    fora_da_curva = (duration_debenture < x.min()) | (duration_debenture > x.max())
    taxa_interpolada[fora_da_curva] = np.nan

    return taxa_interpolada


def analisar_spread_debentures_ntnb(
    debentures_rating,
    debentures_caracteristicas,
    debentures_historico,
    ntnb_historico,
    ntnb_caracteristicas,
    duration_minima_ntnb=None):
    """
    Calcula o spread histórico de debêntures IPCA+ em relação à curva de NTN-B,
    utilizando duration como critério de casamento.

    Observações importantes
    -----------------------
    - debentures_rating deve vir já tratado por preparar_rating
      (colunas Código, Agencia, Nota, Faixa Rating).
    - A duration das debêntures vem em dias úteis e a das NTN-Bs em anos;
      a das debêntures é convertida para anos (/252).
    - As taxas vêm em decimal (0,08 = 8%), logo 1 bp = 0,0001.
    - duration_minima_ntnb (anos): se informado, exclui NTN-Bs curtas da
      curva (a taxa real de títulos muito curtos é distorcida pelo
      carrego do IPCA do mês).

    Retorna um dicionário com:
        - detalhe: observação por debênture/data
        - historico: série agregada dos spreads (grau de investimento)
        - historico_rating: mediana do spread por data e faixa de rating
        - historico_incentivada: mediana do spread por data e Lei 12.431
        - rating: estatísticas de spread por faixa de rating
        - ntnb_curva: curva NTN-B utilizada nos cálculos
        - controle_observações: contagem de observações em cada etapa
    """

    # ============================================================
    # 1. CÓPIAS E PADRONIZAÇÃO
    # ============================================================

    deb_caract = debentures_caracteristicas.copy()
    deb_hist = debentures_historico.copy()
    ntnb_hist = ntnb_historico.copy()
    ntnb_caract = ntnb_caracteristicas.copy()

    # Padronização de nomes de colunas
    for df in [deb_caract, deb_hist, ntnb_hist, ntnb_caract]:
        df.columns = df.columns.str.strip()

    # Datas
    deb_hist["Data"] = pd.to_datetime(deb_hist["Data"])
    ntnb_hist["Data"] = pd.to_datetime(ntnb_hist["Data"])
    deb_caract["Data de vencimento"] = pd.to_datetime(deb_caract["Data de vencimento"])
    ntnb_caract["Data de vencimento"] = pd.to_datetime(ntnb_caract["Data de vencimento"])

    controle_observacoes = {"observacoes_iniciais": len(deb_hist)}

    # ============================================================
    # 2. JUNTAR CARACTERÍSTICAS + HISTÓRICO + RATING
    # ============================================================

    deb = pd.merge(deb_hist,
        deb_caract[["Código", "Emissor", "Remuneração", "Data de vencimento", "Lei 12.431"]],
        on="Código", how="inner")

    # Rating já padronizado por preparar_rating (uma linha por código,
    # não duplica o histórico)
    deb = pd.merge(deb, debentures_rating, on="Código", how="left")

    controle_observacoes["apos_merges"] = len(deb)

    # Duration da debênture: dias úteis -> anos, mesma unidade da NTN-B
    deb["Duration (anos)"] = deb["Duration"] / 252

    # ============================================================
    # 3. PREPARAR CURVA DE NTN-B
    # ============================================================

    ntnb = pd.merge(ntnb_hist,
        ntnb_caract[["Código ISIN", "Data de vencimento"]].drop_duplicates("Código ISIN"),
        left_on="Código",
        right_on="Código ISIN",
        how="left"
    )

    # Remove observações sem duration/taxa
    ntnb = ntnb.dropna(subset=["Data", "Duration", "Taxa Indicativa"]).copy()
    
    #A NTN-B mai/27, com 5,49%, é bem mais baixa que o resto da curva e puxa para cima o spread dos papéis mais curtos.
    # Vale testar com o filtro ligado.
    if duration_minima_ntnb is not None:
        ntnb = ntnb[ntnb["Duration"] >= duration_minima_ntnb]

    ntnb = ntnb.sort_values(["Data", "Duration"])

    # ============================================================
    # 4. CALCULAR TAXA NTN-B E SPREAD
    # ============================================================
    # A curva é montada uma vez por data e todas as debêntures
    # daquele dia são interpoladas de uma só vez.

    #criacão de um dicionário com as curvas de NTN-B por data, para facilitar a interpolação
    # {data1: df1, data2: df2, ...}.
    curvas = dict(tuple(ntnb.groupby("Data")))

    deb["Taxa NTN-B"] = np.nan
    for data, idx in deb.groupby("Data").groups.items():
        if data not in curvas:
            continue
        deb.loc[idx, "Taxa NTN-B"] = interpolar_ntnb(
            curvas[data], deb.loc[idx, "Duration (anos)"].to_numpy())

    # Spread em pontos percentuais e em basis points (taxas em decimal)
    deb["Spread"] = (deb["Taxa Indicativa"] - deb["Taxa NTN-B"]) * 100
    deb["Spread (bps)"] = deb["Spread"] * 100

    # ============================================================
    # 5. LIMPEZA
    # ============================================================

    #retirar observações sem taxa ou duration (não é possível calcular spread)
    controle_observacoes["sem_taxa_ou_duration"] = int(deb[["Taxa Indicativa", "Duration"]].isna().any(axis=1).sum())
    #retirar observações fora da curva de NTN-B (não é possível calcular spread)
    controle_observacoes["fora_da_curva_ntnb"] = int(
        (deb["Taxa NTN-B"].isna() & deb[["Taxa Indicativa", "Duration"]].notna().all(axis=1)).sum())

    resultado = deb.dropna(subset=["Taxa NTN-B", "Spread (bps)"]).copy()
    resultado = resultado.sort_values(["Data", "Código"])

    controle_observacoes["observacoes_finais"] = len(resultado)

    # Grau de investimento separa os papéis em stress (C, D, CCC...),
    # que dominariam média e desvio padrão da amostra.
    resultado["Grau de Investimento"] = resultado["Faixa Rating"].isin(["AAA", "AA", "A", "BBB"])

    grau_inv = resultado[resultado["Grau de Investimento"]]

    estatisticas = dict(
        Spread_Medio_bps=("Spread (bps)", "mean"),
        Spread_Mediano_bps=("Spread (bps)", "median"),
        Spread_P25_bps=("Spread (bps)", lambda s: s.quantile(0.25)),
        Spread_P75_bps=("Spread (bps)", lambda s: s.quantile(0.75)),
        Desvio_Padrao_bps=("Spread (bps)", "std"),
        Numero_Debentures=("Código", "nunique")
    )

    # ============================================================
    # 6. ESTATÍSTICAS HISTÓRICAS (GRAU DE INVESTIMENTO)
    # ============================================================
    # A composição da amostra muda ao longo do tempo; por isso a
    # mediana e o número de debêntures são reportados junto da média.

    historico = (
        grau_inv
        .groupby("Data")
        .agg(**estatisticas)
        .reset_index()
        .sort_values("Data")
    )

    # ============================================================
    # 7. EVOLUÇÃO POR FAIXA DE RATING E POR LEI 12.431
    # ============================================================

    historico_rating = (
        resultado
        .dropna(subset=["Faixa Rating"])
        .groupby(["Data", "Faixa Rating"], observed=True)
        .agg(Spread_Mediano_bps=("Spread (bps)", "median"),
             Numero_Debentures=("Código", "nunique"))
        .reset_index()
    )

    # Incentivadas são isentas de IR para PF, enquanto a NTN-B é
    # tributada: o spread delas fica comprimido (pode ser negativo).
    historico_incentivada = (
        grau_inv
        .dropna(subset=["Lei 12.431"])
        .groupby(["Data", "Lei 12.431"])
        .agg(Spread_Mediano_bps=("Spread (bps)", "median"),
             Numero_Debentures=("Código", "nunique"))
        .reset_index()
    )

    # ============================================================
    # 8. ESTATÍSTICAS POR FAIXA DE RATING
    # ============================================================

    rating_stats = (
        resultado
        .dropna(subset=["Faixa Rating"])
        .groupby("Faixa Rating", observed=True)
        .agg(**estatisticas, Numero_Observacoes=("Código", "count"))
        .reset_index()
    )

    # ============================================================
    # 9. RETORNO
    # ============================================================

    return {
        "detalhe": resultado,
        "historico": historico,
        "historico_rating": historico_rating,
        "historico_incentivada": historico_incentivada,
        "rating": rating_stats,
        "ntnb_curva": ntnb,
        "controle_observações": controle_observacoes
    }


if __name__ == "__main__":
    # Carregando o arquivo de debentures com ratings
    # vamos utilizar somente as debentures que tem algum tipo de rating válido
    debentures_rating = pd.read_excel('Dados_debentures.xlsx', sheet_name='Rating')
    debentures_rating = preparar_rating(debentures_rating)
    lista_debentures = debentures_rating['Código'].to_list()

    # carregando o arquivo de debentures com suas caracteristicas
    debentures_caracteristicas = pd.read_excel('Dados_debentures.xlsx', sheet_name='debentures_IPCA')
    debentures_caracteristicas = debentures_caracteristicas[debentures_caracteristicas['Código'].isin(lista_debentures)]

    # carregando a serie historica das debentures
    # filtrando somente as debentures que tem rating
    debentures_historico = pd.read_excel('serie_hist_quantum.xlsx', sheet_name='Debentures')
    debentures_historico = debentures_historico[debentures_historico['Código'].isin(lista_debentures)]

    # carregando a serie historica das NTN-Bs
    ntnb_historico = pd.read_excel('serie_hist_quantum.xlsx', sheet_name='NTN-B')

    # carregando as caracteristicas das NTN-Bs
    ntnb_caracteristicas = pd.read_excel('Dados_TPF.xlsx', sheet_name='NTN-B')

    resultado = analisar_spread_debentures_ntnb(
        debentures_rating=debentures_rating,
        debentures_caracteristicas=debentures_caracteristicas,
        debentures_historico=debentures_historico,
        ntnb_historico=ntnb_historico,
        ntnb_caracteristicas=ntnb_caracteristicas
    )

    # Resultados em relatório HTML (gráficos interativos) e Excel (tabelas)
    print("Relatório gerado:", gerar_relatorio_html(resultado, "relatorio_spread.html"))
    print("Excel gerado:", exportar_excel(resultado, "resultado_spread.xlsx"))
