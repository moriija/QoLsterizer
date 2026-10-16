# Variable reviewer

Ferramenta para revisar as variáveis do ObservaSampa (indicadores por distrito/subprefeitura de São Paulo) e decidir quais manter.

```
tools/variable_reviewer/
  observa_parser.py   converte os CSVs em um JSON para revisão
  index.html          interface para revisar as variáveis e decidir quais manter
  script.js, styles.css
data/variable_review/
  extracted/          dados brutos extraídos (formato largo, uma coluna por indicador)
  generated/          dados já processados (formato longo) e planilha de decisões
```

## Formatos de CSV aceitos

O parser reconhece dois formatos automaticamente:

- **Longo**: `Nome;Região;Período;Resultado`
- **Largo**: `Período;tipo_regiao;Distrito;<indicador 1>;<indicador 2>;...`, onde cada coluna vira uma variável e células vazias são descartadas.

## Como usar

1. Rode o parser sobre um ou mais CSVs para gerar o JSON (a partir da raiz do repositório):

```bash
python tools/variable_reviewer/observa_parser.py data/variable_review/extracted/dados_filtrados_2013_2024.csv -o dataset.json
```

O script imprime um relatório com total de linhas, variáveis, regiões e estatísticas do período coberto.

2. Abra `tools/variable_reviewer/index.html` no navegador e carregue o `dataset.json` (ou os CSVs diretamente).

3. Na interface, revise cada variável e marque "Manter" ou "Não manter". Também é possível aplicar uma regra automática de descarte por cobertura de distritos e percentual de dados nulos.

4. Exporte o resultado (salve em `data/variable_review/generated/`):
   - `variaveis_revisao.csv` — lista das decisões (manter/não manter) por variável
   - `dados_filtrados.csv` — dados finais já filtrados, apenas com as variáveis mantidas

## Requisitos

Python 3, sem dependências externas (usa apenas a biblioteca padrão).
