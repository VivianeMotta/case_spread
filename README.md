# Spread de debêntures IPCA+ sobre NTN-B

Análise do prêmio de risco das debêntures indexadas ao IPCA em relação às NTN-Bs, com casamento por duration, evolução histórica e dispersão por rating.

**Pergunta central:** o que o prêmio de risco das debêntures IPCA+ tem a informar?

A análise se divide em três eixos:

1. **Evolução histórica:** o prêmio abriu ou fechou ao longo de 2026?
2. **Dispersão por rating:** o mercado cobra mais de quem tem nota pior? Quanto o spread varia dentro de uma mesma faixa?
3. **Efeito tributário:** quanto do spread é risco de crédito e quanto é isenção de IR (Lei 12.431)?

## Estrutura do projeto

| Arquivo | Conteúdo |
|---|---|
| `calculo_spread.py` | Tratamento dos dados e cálculo do spread. É o script principal. |
| `relatorio.py` | Gera o relatório HTML com os gráficos e exporta o Excel. |
| `Dados_debentures.xlsx` | Dados da ANBIMA (debêntures) e ratings da Quantum Axis. |
| `Dados_TPF.xlsx` | Dados da ANBIMA (títulos públicos federais). |
| `serie_hist_quantum.xlsx` | Séries diárias da Quantum Axis (debêntures e NTN-Bs). |
| `relatorio_spread.html` | Saída: relatório com indicadores, gráficos interativos e tabelas. |
| `resultado_spread.xlsx` | Saída: todas as tabelas do resultado, uma por aba. |
| `apresentacao_metodologia.html` | Apresentação da metodologia (12 slides). |

## Fonte dos dados

| Fonte | Uso |
|---|---|
| **ANBIMA** | Define o universo: quais papéis entram na análise e suas características (emissor, remuneração, vencimento, Lei 12.431). |
| **Quantum Axis** | Séries diárias de 2026 (taxa indicativa, duration e PU indicativo) e ratings de Fitch, S&P e Moody's por código CETIP (aba `Rating` de `Dados_debentures.xlsx`). |

### Extração das debêntures

1. Na ANBIMA, download dos preços de debêntures dos últimos dias (21 a 25/09/2026, 6.408 registros).
2. Filtro na data mais recente (25/09/2026).
3. Filtro nas debêntures com indexador IPCA (661 papéis), salvas na aba `debentures_IPCA`.
4. Na Quantum Axis, extração da taxa indicativa, da duration e do PU indicativo de cada dia de 2026 para essa lista (aba `Debentures` de `serie_hist_quantum.xlsx`).

### Extração das NTN-Bs

1. Na ANBIMA, download dos preços de títulos públicos federais dos últimos dias.
2. Filtro somente nas NTN-Bs (14 títulos, de 2027 a 2060), salvas na aba `NTN-B` de `Dados_TPF.xlsx`.
3. Na Quantum Axis, extração da taxa indicativa, da duration e do PU indicativo de cada dia de 2026 (aba `NTN-B` de `serie_hist_quantum.xlsx`).

## Como executar

Requisitos: Python 3 com `pandas`, `numpy`, `openpyxl` e `plotly`. O projeto foi rodado com Python 3.14, pandas 3.0, numpy 2.4, openpyxl 3.1 e plotly 7.1.

```bash
pip install pandas numpy openpyxl plotly
python calculo_spread.py
```

Os arquivos de entrada precisam estar na mesma pasta do script. A execução leva cerca de 35 segundos, a maior parte para gravar a aba `Detalhe` no Excel, e gera `relatorio_spread.html` e `resultado_spread.xlsx`.

O relatório HTML abre direto no navegador, sem internet, porque a biblioteca de gráficos vai embutida no arquivo.

## Metodologia

### 1. Tratamento do rating (`preparar_rating`)

- As notas vêm no formato `AGÊNCIA | NOTA` (ex.: `FITCH | AA+`), em até duas colunas por papel.
- Usa-se o **Rating 1**. O Rating 2 só entra quando o primeiro não é uma nota válida (ex.: "Retirado").
- As notas da Moody's já vêm na notação de S&P e Fitch, então a escala é a mesma para as três agências.
- As notas são agrupadas em faixas, ordenadas pelo risco e não pela ordem alfabética:

| Faixa | Notas | Grupo |
|---|---|---|
| AAA | AAA | Grau de investimento |
| AA | AA+, AA, AA- | Grau de investimento |
| A | A+, A, A- | Grau de investimento |
| BBB | BBB+, BBB, BBB- | Grau de investimento |
| Especulativo | BB+ ou pior | Especulativo |

Só entram na análise as debêntures com rating válido (550 das 661).

### 2. Casamento por duration (`interpolar_ntnb`)

- A duration das debêntures vem em **dias úteis**, e a das NTN-Bs em **anos**. A das debêntures é convertida para anos (÷ 252).
- Para cada data, a curva é formada pelas NTN-Bs daquele dia (12 a 14 vértices).
- A taxa da NTN-B na duration exata da debênture é obtida por **interpolação linear** entre os dois vértices vizinhos.
- Se duas NTN-Bs têm a mesma duration, usa-se a média das taxas.
- **Não há extrapolação:** um papel com duration fora do intervalo da curva fica sem spread naquele dia.

### 3. Cálculo do spread (`analisar_spread_debentures_ntnb`)

```
Spread (bps) = (taxa da debênture − taxa NTN-B interpolada) × 10.000
```

As taxas vêm em decimal (0,0761 = 7,61% a.a.), daí o fator 10.000. As duas taxas são reais (acima do IPCA), então a diferença isola o prêmio sem efeito de inflação.

**Exemplo:** AESLA5 em 25/09/2026, com duration de 1.241 dias úteis (4,93 anos), fica entre a NTN-B 2031 e a 2032. Taxa da debênture de 7,6082% menos NTN-B interpolada de 7,6595% dá um spread de **−5,1 bps**.

### 4. Agregações

| Saída | Descrição |
|---|---|
| `historico` | Mediana, média, P25, P75 e desvio padrão diários, só com grau de investimento. |
| `historico_rating` | Mediana diária por faixa de rating. |
| `historico_incentivada` | Mediana diária de incentivadas contra não incentivadas, só com grau de investimento. |
| `rating` | Estatísticas por faixa de rating, juntando todo o período. |
| `detalhe` | Uma linha por debênture e data, com as taxas, a duration e o spread. |
| `controle_observações` | Quantidade de observações em cada etapa do tratamento. |

A **mediana** é a estatística principal, porque a composição da amostra muda de um dia para o outro e há papéis com spreads extremos.

### Parâmetros

| Parâmetro | Valor |
|---|---|
| Período | 02/01 a 25/09/2026, diário (184 datas) |
| Taxa utilizada | Taxa indicativa (Quantum Axis) |
| Base de dias úteis | 252 |
| Interpolação | Linear, sem extrapolação |
| `duration_minima_ntnb` | `None`, sem corte. Se informado (em anos), exclui NTN-Bs curtas da curva. |
| Rating | Rating 1, com Rating 2 como alternativa |

### Controle da amostra

| Etapa | Observações |
|---|---|
| Observações iniciais (papel × data) | 98.021 |
| Após juntar características e rating | 98.021 |
| Sem taxa ou duration | −2.506 |
| Duration fora da curva de NTN-B | −1.426 |
| **Observações usadas** | **94.089 (96%)** |

## Limitações

- **Rating estático:** a nota atual é aplicada a todo o período, o que pode antecipar rebaixamentos ocorridos no ano (viés de look-ahead).
- **Janela curta:** cerca de 9 meses, sem um ciclo completo de crédito.
- **Amostras pequenas:** 1 papel BBB (que fica fora dos gráficos) e 16 não incentivadas.
- **Tributação:** as incentivadas (Lei 12.431) são isentas de IR e a NTN-B não, então o spread delas fica comprimido e pode ser negativo.
- **Ponta curta da curva:** a NTN-B mai/2027 tem taxa bem abaixo das demais e pode elevar o spread dos papéis curtos. O parâmetro `duration_minima_ntnb` permite testar a análise sem ela.
- **Taxa indicativa:** é uma marcação de referência, não necessariamente o preço de negócio.
