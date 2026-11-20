# QoLsterizer

Pipeline completo para agrupar (clusterizar) os distritos de São Paulo a partir dos indicadores abertos do [ObservaSampa](https://observasampa.prefeitura.sp.gov.br): da revisão manual das variáveis até a modelagem com análise fatorial e K-Means (notebook) e a busca de hiperparâmetros com Optuna, com registro dos modelos no MLflow.

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
   │  entrada das duas etapas de clusterização: data/processed/sel4_full.csv
   │
   ├─► modeling&training/         Modelagem&Treinamento.ipynb: imputação de nulos ─► monotonicidade ─► z-score
   │                              ─► análise fatorial (Varimax) ─► K-Means (K=7) ─► ANOVA e mapas
   │                              ──►  data/results/ (resultado_clusters.csv, clusters_por_distrito.csv)
   │                              ──►  modeling&training/figures/ (heatmaps de completude e figuras dos clusters)
   │
   └─► clustering/                Optuna (scaler + redutor + clusterer) ─► métricas/estabilidade ─► MLflow
```

## Estrutura

```
QoLsterizer/
├── data/
│   ├── raw/                 dados originais, nunca editar
│   ├── interim/             saídas intermediárias do pré-processamento
│   ├── processed/           tabelas finais (sel4_full.csv é a entrada da clusterização)
│   ├── results/             saídas da modelagem: resultado_clusters.csv e clusters_por_distrito.csv
│   └── variable_review/     extracted/ (entrada do reviewer) e generated/ (decisões exportadas)
├── tools/variable_reviewer/ interface web + parser para revisar variáveis
├── preprocessing/           preprocess.py
├── analysis/                EDA.ipynb, normalization_tester.py, figures/
├── modeling&training/       Modelagem&Treinamento.ipynb e figures/ (heatmaps de completude e clusters/)
├── clustering/              run.py, prepare_data.py, config.yaml, src/
└── requirements.txt
```

## Como rodar

Sempre a partir da raiz do repositório:

```bash
pip install -r requirements.txt

python preprocessing/preprocess.py          # data/raw  ->  data/interim + data/processed
python analysis/normalization_tester.py     # compara normalizações (PCA clássico vs. robusto)

python clustering/prepare_data.py --year 2023   # opcional: relatório de qualidade dos dados
python clustering/run.py                        # usa clustering/config.yaml
mlflow ui --backend-store-uri ./mlruns
```

Os notebooks `analysis/EDA.ipynb` e `modeling&training/Modelagem&Treinamento.ipynb` encontram a raiz do repositório sozinhos, então podem ser abertos de qualquer diretório.

O `Modelagem&Treinamento.ipynb` lê `data/processed/sel4_full.csv` e cria, se necessário, as pastas `data/results/` e `modeling&training/figures/`. A malha dos distritos usada nos mapas é baixada do GitHub ([codigourbano/distritos-sp](https://github.com/codigourbano/distritos-sp)) na última célula, então ela precisa de internet.

Detalhes de cada etapa: [`tools/variable_reviewer/README.md`](tools/variable_reviewer/README.md) e [`clustering/README.md`](clustering/README.md).
