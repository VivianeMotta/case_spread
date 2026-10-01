import html

import pandas as pd
import plotly.graph_objects as go

# ============================================================
# CORES
# ============================================================
# Cada cor tem uma versão para o modo claro e outra para o modo
# escuro. As faixas de rating são ordenadas (menor -> maior risco),
# então usam uma rampa de um só tom (azul claro -> azul escuro).

TEMA = {
    "claro": {
        "fundo_pagina": "#f9f9f7", "fundo_grafico": "#fcfcfb",
        "texto": "#0b0b0b", "texto_secundario": "#52514e", "texto_suave": "#898781",
        "grade": "#e1e0d9", "eixo": "#c3c2b7",
    },
    "escuro": {
        "fundo_pagina": "#0d0d0d", "fundo_grafico": "#1a1a19",
        "texto": "#ffffff", "texto_secundario": "#c3c2b7", "texto_suave": "#898781",
        "grade": "#2c2c2a", "eixo": "#383835",
    },
}

# [claro, escuro]
COR_FAIXA = {
    "AAA": ["#86b6ef", "#184f95"],
    "AA": ["#3987e5", "#2a78d6"],
    "A": ["#1c5cab", "#6da7ec"],
    "Especulativo (<=BB)": ["#0d366b", "#b7d3f6"],
}
SIMBOLO_FAIXA = {"AAA": "circle", "AA": "square", "A": "diamond", "Especulativo (<=BB)": "triangle-up"}

COR_PRINCIPAL = ["#2a78d6", "#3987e5"]
COR_FAIXA_P25_P75 = ["rgba(42,120,214,0.15)", "rgba(57,135,229,0.22)"]
COR_LEI = {"SIM": ["#2a78d6", "#3987e5"], "NÃO": ["#eb6834", "#d95926"]}

# BBB tem um único papel na amostra: fica só na tabela, não nos gráficos
FAIXAS_GRAFICO = ["AAA", "AA", "A", "Especulativo (<=BB)"]


# ============================================================
# FUNÇÕES AUXILIARES DOS GRÁFICOS
# ============================================================

def _layout_base(titulo_y):
    """
    Layout comum a todos os gráficos (cores do modo claro; o modo
    escuro é aplicado pelo JavaScript da página).
    """
    t = TEMA["claro"]
    eixo = dict(gridcolor=t["grade"], linecolor=t["eixo"], zerolinecolor=t["eixo"],
                tickfont=dict(color=t["texto_suave"]), title_font=dict(color=t["texto_secundario"]))
    return dict(
        paper_bgcolor=t["fundo_grafico"], plot_bgcolor=t["fundo_grafico"],
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif', size=13,
                  color=t["texto_secundario"]),
        separators=",.",
        margin=dict(l=64, r=150, t=16, b=48),
        height=380,
        hoverlabel=dict(bgcolor=t["fundo_grafico"], bordercolor=t["eixo"],
                        font=dict(color=t["texto"])),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                    font=dict(color=t["texto_secundario"])),
        xaxis=dict(**eixo, showgrid=False),
        yaxis=dict(**eixo, title=titulo_y, zeroline=True, zerolinewidth=1),
    )


def _rotulos_finais(fig, rotulos, faixa_y):
    """
    Rótulos diretos no fim de cada linha, para identificar a série sem
    depender só da cor. Rótulos muito próximos são afastados
    verticalmente para não se sobreporem.

    rotulos : lista de (x, y, texto)
    faixa_y : amplitude do eixo y, usada para definir o espaço mínimo
    """
    espaco_minimo = faixa_y * 0.07
    rotulos = sorted(rotulos, key=lambda r: r[1])

    posicoes = []
    for _, y, _ in rotulos:
        if posicoes and y - posicoes[-1] < espaco_minimo:
            y = posicoes[-1] + espaco_minimo
        posicoes.append(y)

    for (x, _, texto), y in zip(rotulos, posicoes):
        fig.add_annotation(x=x, y=y, text=texto, showarrow=False, xanchor="left",
                           xshift=8, font=dict(color=TEMA["claro"]["texto_secundario"], size=12))


def _cores(par):
    """
    Guarda as cores claro/escuro no trace (usado pelo JavaScript).
    """
    return par[0], par


# ============================================================
# GRÁFICOS
# ============================================================

def grafico_historico(historico):
    """
    Mediana diária do spread (grau de investimento) com a faixa P25-P75.
    """
    fig = go.Figure()
    cor_banda, par_banda = _cores(COR_FAIXA_P25_P75)
    cor_linha, par_linha = _cores(COR_PRINCIPAL)

    fig.add_trace(go.Scatter(
        x=historico["Data"], y=historico["Spread_P75_bps"], mode="lines",
        line=dict(width=0), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(
        x=historico["Data"], y=historico["Spread_P25_bps"], mode="lines",
        line=dict(width=0), fill="tonexty", fillcolor=cor_banda,
        name="P25–P75", hoverinfo="skip", meta={"fillcolor": par_banda}))
    fig.add_trace(go.Scatter(
        x=historico["Data"], y=historico["Spread_Mediano_bps"], mode="lines",
        line=dict(width=2, color=cor_linha), name="Mediana",
        customdata=historico[["Spread_P25_bps", "Spread_P75_bps", "Numero_Debentures"]],
        hovertemplate=("%{x|%d/%m/%Y}<br>Mediana: <b>%{y:.0f} bps</b>"
                       "<br>P25–P75: %{customdata[0]:.0f} a %{customdata[1]:.0f} bps"
                       "<br>Debêntures: %{customdata[2]}<extra></extra>"),
        meta={"line.color": par_linha}))

    fig.update_layout(**_layout_base("Spread sobre NTN-B (bps)"))
    fig.update_layout(margin=dict(r=24), hovermode="x")
    fig.update_xaxes(tickformat="%m/%Y")
    return fig


def grafico_historico_rating(historico_rating):
    """
    Mediana diária do spread por faixa de rating.
    """
    fig = go.Figure()
    dados = historico_rating[historico_rating["Faixa Rating"].isin(FAIXAS_GRAFICO)]
    rotulos = []

    for faixa in FAIXAS_GRAFICO:
        serie = dados[dados["Faixa Rating"] == faixa].sort_values("Data")
        if serie.empty:
            continue
        cor, par = _cores(COR_FAIXA[faixa])
        fig.add_trace(go.Scatter(
            x=serie["Data"], y=serie["Spread_Mediano_bps"], mode="lines",
            line=dict(width=2, color=cor), name=faixa,
            customdata=serie[["Numero_Debentures"]],
            hovertemplate=(f"{faixa}: <b>%{{y:.0f}} bps</b>"
                           " (%{customdata[0]} papéis)<extra></extra>"),
            meta={"line.color": par}))
        ultimo = serie.iloc[-1]
        rotulos.append((ultimo["Data"], ultimo["Spread_Mediano_bps"],
                        f"{faixa}  {ultimo['Spread_Mediano_bps']:.0f}"))

    y = dados["Spread_Mediano_bps"]
    _rotulos_finais(fig, rotulos, y.max() - y.min())

    fig.update_layout(**_layout_base("Mediana do spread (bps)"))
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(tickformat="%m/%Y", range=[dados["Data"].min(), dados["Data"].max()])
    return fig


def grafico_dispersao_rating(ultimo_dia):
    """
    Distribuição do spread por faixa de rating na última data
    (cada ponto é uma debênture).
    """
    fig = go.Figure()

    for faixa in FAIXAS_GRAFICO:
        dados = ultimo_dia[ultimo_dia["Faixa Rating"] == faixa]
        if dados.empty:
            continue
        cor, par = _cores(COR_FAIXA[faixa])
        fig.add_trace(go.Box(
            y=dados["Spread (bps)"], name=faixa, boxpoints="all", jitter=0.45, pointpos=0,
            marker=dict(color=cor, size=6, opacity=0.7), line=dict(color=cor, width=2),
            fillcolor="rgba(0,0,0,0)",
            customdata=dados[["Código", "Emissor", "Nota"]],
            hovertemplate=("<b>%{customdata[0]}</b> (%{customdata[2]})<br>%{customdata[1]}"
                           "<br>Spread: %{y:.0f} bps<extra></extra>"),
            meta={"marker.color": par, "line.color": par}))

    fig.update_layout(**_layout_base("Spread sobre NTN-B (bps)"))
    fig.update_layout(showlegend=False, margin=dict(r=24), height=420)
    return fig


def grafico_spread_duration(ultimo_dia):
    """
    Spread contra duration na última data, só grau de investimento
    (os especulativos ficam fora para não achatar a escala).
    """
    fig = go.Figure()

    for faixa in ["AAA", "AA", "A"]:
        dados = ultimo_dia[ultimo_dia["Faixa Rating"] == faixa]
        if dados.empty:
            continue
        cor, par = _cores(COR_FAIXA[faixa])
        fig.add_trace(go.Scatter(
            x=dados["Duration (anos)"], y=dados["Spread (bps)"], mode="markers", name=faixa,
            marker=dict(color=cor, size=8, symbol=SIMBOLO_FAIXA[faixa],
                        line=dict(width=1, color=TEMA["claro"]["fundo_grafico"])),
            customdata=dados[["Código", "Emissor", "Nota"]],
            hovertemplate=("<b>%{customdata[0]}</b> (%{customdata[2]})<br>%{customdata[1]}"
                           "<br>Duration: %{x:.1f} anos<br>Spread: %{y:.0f} bps<extra></extra>"),
            meta={"marker.color": par}))

    fig.update_layout(**_layout_base("Spread sobre NTN-B (bps)"))
    fig.update_layout(margin=dict(r=24), height=420)
    fig.update_xaxes(title="Duration (anos)", showgrid=True)
    return fig


def grafico_incentivadas(historico_incentivada):
    """
    Mediana do spread de incentivadas (Lei 12.431) contra não incentivadas.
    """
    fig = go.Figure()
    nomes = {"SIM": "Incentivadas", "NÃO": "Não incentivadas"}
    rotulos = []

    for lei in ["SIM", "NÃO"]:
        serie = historico_incentivada[historico_incentivada["Lei 12.431"] == lei].sort_values("Data")
        if serie.empty:
            continue
        cor, par = _cores(COR_LEI[lei])
        fig.add_trace(go.Scatter(
            x=serie["Data"], y=serie["Spread_Mediano_bps"], mode="lines",
            line=dict(width=2, color=cor), name=nomes[lei],
            customdata=serie[["Numero_Debentures"]],
            hovertemplate=(f"{nomes[lei]}: <b>%{{y:.0f}} bps</b>"
                           " (%{customdata[0]} papéis)<extra></extra>"),
            meta={"line.color": par}))
        ultimo = serie.iloc[-1]
        rotulos.append((ultimo["Data"], ultimo["Spread_Mediano_bps"],
                        f"{nomes[lei]}  {ultimo['Spread_Mediano_bps']:.0f}"))

    y = historico_incentivada["Spread_Mediano_bps"]
    _rotulos_finais(fig, rotulos, y.max() - y.min())

    fig.update_layout(**_layout_base("Mediana do spread (bps)"))
    fig.update_layout(hovermode="x unified", margin=dict(r=190))
    fig.update_xaxes(tickformat="%m/%Y",
                     range=[historico_incentivada["Data"].min(), historico_incentivada["Data"].max()])
    return fig


# ============================================================
# TABELAS E INDICADORES
# ============================================================

def _numero(valor, casas=0):
    """
    Formata número no padrão brasileiro (1.234,5).
    """
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def tabela_rating(rating):
    """
    Tabela HTML com as estatísticas por faixa de rating.
    """
    colunas = [
        ("Faixa Rating", "Faixa", None),
        ("Spread_Mediano_bps", "Mediana", 0),
        ("Spread_Medio_bps", "Média", 0),
        ("Spread_P25_bps", "P25", 0),
        ("Spread_P75_bps", "P75", 0),
        ("Desvio_Padrao_bps", "Desvio padrão", 0),
        ("Numero_Debentures", "Debêntures", 0),
        ("Numero_Observacoes", "Observações", 0),
    ]
    cabecalho = "".join(f"<th>{rotulo}</th>" for _, rotulo, _ in colunas)
    linhas = ""
    for _, linha in rating.iterrows():
        celulas = ""
        for coluna, _, casas in colunas:
            valor = linha[coluna]
            celulas += f"<td>{html.escape(str(valor))}</td>" if casas is None else f"<td>{_numero(valor, casas)}</td>"
        linhas += f"<tr>{celulas}</tr>"
    return f"<table><thead><tr>{cabecalho}</tr></thead><tbody>{linhas}</tbody></table>"


def tabela_controle(controle):
    """
    Tabela HTML com a contagem de observações em cada etapa.
    """
    rotulos = {
        "observacoes_iniciais": "Observações iniciais",
        "apos_merges": "Após juntar características e rating",
        "sem_taxa_ou_duration": "Descartadas: sem taxa ou duration",
        "fora_da_curva_ntnb": "Descartadas: duration fora da curva de NTN-B",
        "observacoes_finais": "Observações usadas",
    }
    linhas = "".join(
        f"<tr><td>{rotulos.get(chave, chave)}</td><td>{_numero(valor)}</td></tr>"
        for chave, valor in controle.items())
    return f"<table class='estreita'><tbody>{linhas}</tbody></table>"


def _indicador(rotulo, valor, detalhe=""):
    return (f"<div class='indicador'><div class='rotulo'>{rotulo}</div>"
            f"<div class='valor'>{valor}</div><div class='detalhe'>{detalhe}</div></div>")


# ============================================================
# RELATÓRIO HTML
# ============================================================

CSS = """
:root { color-scheme: light;
  --fundo-pagina: #f9f9f7; --fundo-cartao: #fcfcfb; --texto: #0b0b0b;
  --texto-secundario: #52514e; --texto-suave: #898781; --borda: rgba(11,11,11,0.10); --grade: #e1e0d9; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { color-scheme: dark;
  --fundo-pagina: #0d0d0d; --fundo-cartao: #1a1a19; --texto: #ffffff;
  --texto-secundario: #c3c2b7; --texto-suave: #898781; --borda: rgba(255,255,255,0.10); --grade: #2c2c2a; } }
:root[data-theme="dark"] { color-scheme: dark;
  --fundo-pagina: #0d0d0d; --fundo-cartao: #1a1a19; --texto: #ffffff;
  --texto-secundario: #c3c2b7; --texto-suave: #898781; --borda: rgba(255,255,255,0.10); --grade: #2c2c2a; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--fundo-pagina); color: var(--texto);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif; line-height: 1.5; }
main { max-width: 1100px; margin: 0 auto; padding: 32px 16px 64px; }
h1 { font-size: 26px; margin: 0 0 4px; }
h2 { font-size: 18px; margin: 0 0 4px; }
.subtitulo { color: var(--texto-secundario); margin: 0 0 24px; }
.cartao { background: var(--fundo-cartao); border: 1px solid var(--borda); border-radius: 12px;
  padding: 20px; margin-bottom: 20px; }
.legenda { color: var(--texto-secundario); font-size: 14px; margin: 0 0 12px; }
.indicadores { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 20px; }
.indicador { background: var(--fundo-cartao); border: 1px solid var(--borda); border-radius: 12px; padding: 16px; }
.indicador .rotulo { color: var(--texto-secundario); font-size: 13px; }
.indicador .valor { font-size: 28px; font-weight: 600; margin: 4px 0; }
.indicador .detalhe { color: var(--texto-suave); font-size: 13px; }
.leitura li { margin-bottom: 6px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; font-variant-numeric: tabular-nums; }
table.estreita { max-width: 560px; }
th, td { padding: 8px 10px; border-bottom: 1px solid var(--grade); text-align: right; }
th:first-child, td:first-child { text-align: left; }
th { color: var(--texto-secundario); font-weight: 600; }
.tabela-rolagem { overflow-x: auto; }
.notas { color: var(--texto-secundario); font-size: 14px; }
"""

# Aplica o tema escuro aos gráficos Plotly quando o sistema está no
# modo escuro. Cada trace guarda em "meta" o par [claro, escuro].
JS_TEMA = """
<script>
const TEMA = %s;
function temaEscuro() {
  const forcado = document.documentElement.dataset.theme;
  if (forcado) return forcado === "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}
function aplicarTema() {
  const i = temaEscuro() ? 1 : 0;
  const t = temaEscuro() ? TEMA.escuro : TEMA.claro;
  document.querySelectorAll(".plotly-graph-div").forEach(gd => {
    if (!gd.data) return;
    gd.data.forEach((trace, n) => {
      if (!trace.meta) return;
      const mudanca = {};
      for (const [atributo, par] of Object.entries(trace.meta)) mudanca[atributo] = [par[i]];
      if (trace.type === "scatter" && trace.mode === "markers") mudanca["marker.line.color"] = [t.fundo_grafico];
      Plotly.restyle(gd, mudanca, [n]);
    });
    const eixo = {gridcolor: t.grade, linecolor: t.eixo, zerolinecolor: t.eixo};
    const layout = {
      paper_bgcolor: t.fundo_grafico, plot_bgcolor: t.fundo_grafico,
      "font.color": t.texto_secundario, "legend.font.color": t.texto_secundario,
      "hoverlabel.bgcolor": t.fundo_grafico, "hoverlabel.bordercolor": t.eixo,
      "hoverlabel.font.color": t.texto,
    };
    for (const nome of ["xaxis", "yaxis"]) {
      for (const [k, v] of Object.entries(eixo)) layout[nome + "." + k] = v;
      layout[nome + ".tickfont.color"] = t.texto_suave;
      layout[nome + ".title.font.color"] = t.texto_secundario;
    }
    (gd.layout.annotations || []).forEach((_, k) => { layout["annotations[" + k + "].font.color"] = t.texto_secundario; });
    Plotly.relayout(gd, layout);
  });
}
window.addEventListener("load", aplicarTema);
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", aplicarTema);
</script>
"""


def gerar_relatorio_html(resultado, caminho="relatorio_spread.html"):
    """
    Gera um relatório HTML autocontido (abre offline, sem Python)
    com indicadores, gráficos interativos e tabelas.
    """
    detalhe = resultado["detalhe"]
    historico = resultado["historico"]
    historico_rating = resultado["historico_rating"]
    historico_incentivada = resultado["historico_incentivada"]
    rating = resultado["rating"]
    controle = resultado["controle_observações"]

    primeira_data = detalhe["Data"].min()
    ultima_data = detalhe["Data"].max()
    ultimo_dia = detalhe[detalhe["Data"] == ultima_data]

    # ------------------------------------------------------------
    # Indicadores do topo
    # ------------------------------------------------------------
    mediana_inicio = historico["Spread_Mediano_bps"].iloc[0]
    mediana_fim = historico["Spread_Mediano_bps"].iloc[-1]
    variacao = mediana_fim - mediana_inicio
    percentual_usado = controle["observacoes_finais"] / controle["observacoes_iniciais"]

    indicadores = "".join([
        _indicador("Período", f"{primeira_data:%m}–{ultima_data:%m/%Y}"
                   if primeira_data.year == ultima_data.year
                   else f"{primeira_data:%m/%y}–{ultima_data:%m/%y}",
                   f"{detalhe['Data'].nunique()} datas"),
        _indicador("Debêntures analisadas", _numero(detalhe["Código"].nunique()),
                   f"{_numero(ultimo_dia['Código'].nunique())} na última data"),
        _indicador("Observações usadas", _numero(controle["observacoes_finais"]),
                   f"{percentual_usado:.0%} do total".replace(".", ",")),
        _indicador("Mediana atual (grau de investimento)", f"{_numero(mediana_fim)} bps",
                   f"{'+' if variacao >= 0 else '−'}{_numero(abs(variacao))} bps desde {primeira_data:%m/%Y}"),
    ])

    # ------------------------------------------------------------
    # Principais leituras (calculadas a partir dos dados)
    # ------------------------------------------------------------
    mediana_faixa = (
        ultimo_dia[ultimo_dia["Faixa Rating"].isin(FAIXAS_GRAFICO)]
        .groupby("Faixa Rating", observed=True)["Spread (bps)"].median())
    texto_faixas = " → ".join(f"{faixa} {_numero(valor)}" for faixa, valor in mediana_faixa.items())

    inc_ultimo = historico_incentivada[historico_incentivada["Data"] == ultima_data].set_index("Lei 12.431")
    leituras = [f"Na última data, a mediana do spread por faixa de rating é: {texto_faixas} bps."]
    if {"SIM", "NÃO"} <= set(inc_ultimo.index):
        sim = inc_ultimo.loc["SIM", "Spread_Mediano_bps"]
        nao = inc_ultimo.loc["NÃO", "Spread_Mediano_bps"]
        leituras.append(
            f"Incentivadas (Lei 12.431) têm mediana de {_numero(sim)} bps, contra {_numero(nao)} bps "
            f"das não incentivadas: uma diferença de {_numero(nao - sim)} bps que reflete a isenção de IR, "
            f"e não risco de crédito.")
    leituras.append(
        f"Desde {primeira_data:%m/%Y}, a mediana do grau de investimento variou "
        f"{'+' if variacao >= 0 else '−'}{_numero(abs(variacao))} bps.")

    # Movimento recente: últimos 10 pregões, decompondo em taxa da
    # debênture e taxa da NTN-B para mostrar de onde veio a variação
    datas = historico["Data"].sort_values().unique()
    if len(datas) > 10:
        data_ref = datas[-11]
        grau_inv = detalhe[detalhe["Grau de Investimento"]]
        antes = grau_inv[grau_inv["Data"] == data_ref]
        depois = grau_inv[grau_inv["Data"] == ultima_data]
        var_spread = (depois["Spread (bps)"].median() - antes["Spread (bps)"].median())
        var_deb = (depois["Taxa Indicativa"].median() - antes["Taxa Indicativa"].median()) * 10000
        var_ntnb = (depois["Taxa NTN-B"].median() - antes["Taxa NTN-B"].median()) * 10000
        leituras.append(
            f"Nos últimos 10 pregões, a mediana do spread variou "
            f"{'+' if var_spread >= 0 else '−'}{_numero(abs(var_spread))} bps: a taxa mediana das "
            f"debêntures mudou {'+' if var_deb >= 0 else '−'}{_numero(abs(var_deb))} bps e a da NTN-B "
            f"equivalente {'+' if var_ntnb >= 0 else '−'}{_numero(abs(var_ntnb))} bps.")
    lista_leituras = "".join(f"<li>{html.escape(texto)}</li>" for texto in leituras)

    # ------------------------------------------------------------
    # Gráficos (o primeiro embute a biblioteca Plotly.js)
    # ------------------------------------------------------------
    figuras = [
        grafico_historico(historico),
        grafico_historico_rating(historico_rating),
        grafico_dispersao_rating(ultimo_dia),
        grafico_spread_duration(ultimo_dia),
        grafico_incentivadas(historico_incentivada),
    ]
    config = {"displaylogo": False, "responsive": True}
    divs = [
        fig.to_html(full_html=False, include_plotlyjs=(i == 0), config=config)
        for i, fig in enumerate(figuras)
    ]

    data_txt = f"{ultima_data:%d/%m/%Y}"
    n_bbb = int(rating.loc[rating["Faixa Rating"] == "BBB", "Numero_Debentures"].sum())

    pagina = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Spread Debêntures IPCA+</title>
<style>{CSS}</style>
</head>
<body>
<main>
  <h1>Spread de debêntures IPCA+ sobre NTN-B</h1>
  <p class="subtitulo">Casamento por duration com a curva de NTN-B interpolada, de {primeira_data:%d/%m/%Y} a {data_txt}.</p>

  <div class="indicadores">{indicadores}</div>

  <section class="cartao leitura">
    <h2>Principais leituras</h2>
    <ul>{lista_leituras}</ul>
  </section>

  <section class="cartao">
    <h2>Evolução histórica do spread</h2>
    <p class="legenda">Mediana diária do spread das debêntures de grau de investimento. A faixa sombreada vai do percentil 25 ao 75.</p>
    {divs[0]}
  </section>

  <section class="cartao">
    <h2>Evolução por faixa de rating</h2>
    <p class="legenda">Mediana diária do spread em cada faixa de rating.</p>
    {divs[1]}
  </section>

  <section class="cartao">
    <h2>Dispersão por faixa de rating em {data_txt}</h2>
    <p class="legenda">Cada ponto é uma debênture; a caixa vai do P25 ao P75 e o traço central é a mediana. Passe o mouse para ver o papel.</p>
    {divs[2]}
  </section>

  <section class="cartao">
    <h2>Spread contra duration em {data_txt}</h2>
    <p class="legenda">Somente grau de investimento (AAA, AA e A). Os papéis especulativos ficam fora para não achatar a escala.</p>
    {divs[3]}
  </section>

  <section class="cartao">
    <h2>Incentivadas contra não incentivadas</h2>
    <p class="legenda">Mediana diária do spread de grau de investimento, separando papéis da Lei 12.431 (isentos de IR para pessoa física).</p>
    {divs[4]}
  </section>

  <section class="cartao">
    <h2>Estatísticas por faixa de rating (bps)</h2>
    <p class="legenda">Todas as datas do período.</p>
    <div class="tabela-rolagem">{tabela_rating(rating)}</div>
  </section>

  <section class="cartao">
    <h2>Controle de observações</h2>
    <p class="legenda">Cada observação é uma debênture em uma data.</p>
    {tabela_controle(controle)}
  </section>

  <section class="cartao notas">
    <h2>Limitações</h2>
    <ul>
      <li>O rating é a foto atual e foi aplicado a todo o período (possível viés de look-ahead).</li>
      <li>A janela cobre apenas {primeira_data:%m/%Y} a {ultima_data:%m/%Y}.</li>
      <li>A faixa BBB tem {n_bbb} debênture(s) e aparece só na tabela, não nos gráficos.</li>
      <li>A amostra de não incentivadas é pequena; a comparação com incentivadas deve ser lida com cautela.</li>
    </ul>
  </section>
</main>
{JS_TEMA % pd.Series(TEMA).to_json()}
</body>
</html>"""

    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write(pagina)

    return caminho


# ============================================================
# EXCEL
# ============================================================

def exportar_excel(resultado, caminho="resultado_spread.xlsx"):
    """
    Salva cada tabela do resultado em uma aba do Excel.
    """
    controle = pd.DataFrame(
        list(resultado["controle_observações"].items()), columns=["Etapa", "Observações"])

    abas = {
        "Rating": resultado["rating"],
        "Historico": resultado["historico"],
        "Historico por rating": resultado["historico_rating"],
        "Historico Lei 12.431": resultado["historico_incentivada"],
        "Controle observacoes": controle,
        "Detalhe": resultado["detalhe"],
    }

    with pd.ExcelWriter(caminho, engine="openpyxl") as escritor:
        for nome, tabela in abas.items():
            tabela = tabela.copy()
            # Categorias viram texto para o Excel
            for coluna in tabela.select_dtypes("category").columns:
                tabela[coluna] = tabela[coluna].astype(str).replace("nan", "")
            tabela.to_excel(escritor, sheet_name=nome, index=False)

            planilha = escritor.sheets[nome]
            planilha.freeze_panes = "A2"
            colunas_data = set(tabela.select_dtypes("datetime").columns)
            for posicao, coluna in enumerate(tabela.columns):
                letra = planilha.cell(row=1, column=posicao + 1).column_letter
                planilha.column_dimensions[letra].width = min(max(len(str(coluna)), 10) + 2, 45)
                if coluna in colunas_data:
                    for (celula,) in planilha.iter_rows(min_row=2, min_col=posicao + 1, max_col=posicao + 1):
                        celula.number_format = "DD/MM/YYYY"

    return caminho
