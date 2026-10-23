# QoLsterizer

Pipeline completo para agrupar (clusterizar) os distritos de São Paulo a partir dos indicadores abertos do [ObservaSampa](https://observasampa.prefeitura.sp.gov.br): da revisão manual das variáveis até a busca de hiperparâmetros com Optuna e o registro dos modelos no MLflow.

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
clustering/                       Optuna (scaler + redutor + clusterer) ─► métricas/estabilidade ─► MLflow
                                  entrada: data/processed/sel4_full.csv
```

## Estrutura

```
QoLsterizer/
├── data/
│   ├── raw/                 dados originais, nunca editar
│   ├── interim/             saídas intermediárias do pré-processamento
│   ├── processed/           tabelas finais (sel4_full.csv é a entrada da clusterização)
│   └── variable_review/     extracted/ (entrada do reviewer) e generated/ (decisões exportadas)
├── tools/variable_reviewer/ interface web + parser para revisar variáveis
├── preprocessing/           preprocess.py
├── analysis/                EDA.ipynb, normalization_tester.py, figures/
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

O notebook `analysis/EDA.ipynb` encontra a raiz do repositório sozinho, então pode ser aberto de qualquer diretório.

Detalhes de cada etapa: [`tools/variable_reviewer/README.md`](tools/variable_reviewer/README.md) e [`clustering/README.md`](clustering/README.md).
