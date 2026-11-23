# QoLsterizer

Pipeline para agrupar (clusterizar) os distritos de São Paulo a partir dos indicadores abertos do [ObservaSampa](https://observasampa.prefeitura.sp.gov.br): da revisão manual das variáveis até a modelagem com análise fatorial e K-Means.

## Fluxo

```
data/raw/                         CSVs originais do ObservaSampa (Indicadores + Variáveis)
   │
   │  tools/variable_reviewer/    revisão manual: quais variáveis manter  ──►  data/variable_review/
   ▼
preprocessing/preprocess.py       formato largo, seleção de variáveis, remoção de nulos, normalização demográfica
   │                              ──►  data/interim/  (merged_1sel, merged_2sel)
   │                              ──►  data/processed/ (sel3_full, sel4_full)
   ▼
analysis/                         EDA.ipynb (nulos/zeros, correlação, variância) e normalization_tester.py
   │                              ──►  analysis/figures/
   ▼
modeling&training/                Modelagem&Treinamento.ipynb: imputação de nulos ─► monotonicidade ─► z-score
                                  ─► análise fatorial (Varimax) ─► K-Means (K=7) ─► ANOVA e mapas
                                  entrada: data/processed/sel4_full.csv
                                  ──►  data/results/ (resultado_clusters.csv, clusters_por_distrito.csv)
                                  ──►  modeling&training/figures/ (heatmaps de completude e figuras dos clusters)
```

## Estrutura

```
QoLsterizer/
├── data/
│   ├── raw/                 dados originais, nunca editar
│   ├── interim/             saídas intermediárias do pré-processamento
│   ├── processed/           tabelas finais (sel4_full.csv é a entrada da modelagem)
│   ├── results/             saídas da modelagem: resultado_clusters.csv e clusters_por_distrito.csv
│   └── variable_review/     extracted/ (entrada do reviewer) e generated/ (decisões exportadas)
├── tools/variable_reviewer/ interface web + parser para revisar variáveis
├── preprocessing/           preprocess.py
├── analysis/                EDA.ipynb, normalization_tester.py, figures/
├── modeling&training/       Modelagem&Treinamento.ipynb e figures/ (heatmaps de completude e clusters/)
└── requirements.txt
```

## Como rodar

Sempre a partir da raiz do repositório:

```bash
pip install -r requirements.txt

python preprocessing/preprocess.py          # data/raw  ->  data/interim + data/processed
python analysis/normalization_tester.py     # compara normalizações (PCA clássico vs. robusto)
```

Depois, abra e execute os notebooks, nesta ordem:

1. `analysis/EDA.ipynb`: análise exploratória (nulos/zeros, correlação, variância).
2. `modeling&training/Modelagem&Treinamento.ipynb`: modelagem e clusterização dos distritos.

Os dois notebooks encontram a raiz do repositório sozinhos, então podem ser abertos de qualquer diretório.

O `Modelagem&Treinamento.ipynb` lê `data/processed/sel4_full.csv` e cria, se necessário, as pastas `data/results/` e `modeling&training/figures/`. A malha dos distritos usada nos mapas é baixada do GitHub ([codigourbano/distritos-sp](https://github.com/codigourbano/distritos-sp)) na última célula, então ela precisa de internet.

Detalhes da revisão de variáveis: [`tools/variable_reviewer/README.md`](tools/variable_reviewer/README.md).
