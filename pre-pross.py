# %%
import pandas as pd
var_v = pd.read_csv('raw/ObservaSampaDadosAbertosVariaveisCSV.csv', delimiter=';')
var_i = pd.read_csv('raw/ObservaSampaDadosAbertosIndicadoresCSV.csv', delimiter=';')

def tratar_disposicao(df):
    # Apenas as vars disponiveis por distrito
    df['tipo_regiao'] = df['Região'].str.extract(r'\((.*?)\)$')
    df['Distrito'] = df['Região'].str.replace(r'\s*\(Distrito\)$', '', regex=True)
    dist = df[df['tipo_regiao'] == 'Distrito']
    dist = dist.drop(columns=['tipo_regiao', 'Região'])
    print(f"{dist['Nome'].nunique()} variáveis disponíveis por distrito (de {df['Nome'].nunique()} no total)")

    # Criando Dataset em que as variaveis presentes na linhas estarao nas colunas
    df = dist.pivot_table(
        index=['Período', 'Distrito'],  # Mantém como identificadores de linha
        columns='Nome',                                # Valores que virarão colunas
        values='Resultado',                            # Valores que preencherão as células
        aggfunc='first'                                # Pega o primeiro valor (evita erro de duplicatas)
    ).reset_index()

    df.columns.name = None # Remove o nome do eixo das colunas ('Nome') para limpar a visualização da tabela

    # TRANSFORMANDO RESULTADOS EM NUMERICO
    colunas_indicadores = df.columns.drop(['Período', 'Distrito'])

    # Convertendo cada uma delas de object para número
    for coluna in colunas_indicadores:
        # Transforma em string, troca a vírgula por ponto, e converte para número.
        # errors='coerce' garante que, se houver algum texto inválido ou vazio, ele vire NaN (nulo)
        df[coluna] = pd.to_numeric(df[coluna].astype(str).str.replace(',', '.')) #errors='coerce')
    return df.copy()

# JUNTANDO variaveis + indicadores
merged = pd.merge(tratar_disposicao(var_i), tratar_disposicao(var_v), on=['Período', 'Distrito'], how='inner')


def selecionar_cols_relevantes(df):
    # FILTRANDO APENAS VARS RELEVANTES
    # Lista contendo exatamente os nomes das colunas que você deseja selecionar
    colunas_selecionadas = [
    'Período',
    'Distrito',
    '01.01.01 Quantidade de famílias em situação de extrema pobreza (até 1/4 salário mínimo)',
    '01.02.01 Quantidade de famílias em situação de pobreza (renda por pessoa de ⅛ até ¼ de salário-mínimo) ',
    '01.02.02 Quantidade de famílias em situação de baixa renda (renda por pessoa de ¼ até ½ salário mínimo)',
    '01.03.02 Quantidade de famílias beneficiárias do Programa Bolsa Família',
    '01.05.02 Número de famílias em atendimento habitacional provisório (Auxílio Aluguel) por situação de risco e emergência ',
    '02.02.05 Proporção de nascidos vivos com peso ao nascer inferior a 2.500 gramas (%)',
    '03.01.01 Razão de mortalidade materna (por 100 mil nascidos vivos)',
    '03.02.01 Taxa de mortalidade infantil (por mil nascidos vivos)',
    '03.07.02 Proporção de gestantes adolescentes (%)',
    '04.02.01 Demanda Atendida de Vagas em Creches da Rede Municipal de Ensino (%)',
    '04.0a.01 Porcentagem de escolas com recursos para Atendimento Educacional Especializado (%)',
    '11.01.03 Número de Unidades Habitacionais entregues (por meio de programas habitacionais e parcerias firmadas)',
    '11.01.07 Número estimado de domicílios em favelas',
    '11.01.08 Total de famílias beneficiárias de Auxílio Aluguel por ano',
    '11.05.02 Número de ocorrências atendidas – deslizamento',
    '11.05.03 Número de ocorrências atendidas – inundação',
    '16.02.03 Número de casos notificados de violência contra crianças e adolescentes',
    'Demanda atendida de vagas em Pré-escolas da Rede Municipal de Ensino (%)',
    'Equipamentos públicos municipais de cultura (por 100 mil habitantes)',
    'Escolas Municipais de Ensino Fundamental que oferecem turmas em educação integral em tempo integral (7h/dia ou mais)',
    'Número de acidentes de bicicleta',
    'Número de casos de notificação de violência contra pessoas idosas',
    'Número de matrículas em tempo integral nas escolas públicas municipais de Educação Infantil',
    'Número de ocorrências atendidas – alagamento',
    'Número de ocorrências atendidas – queda de árvore',
    'População com 60 anos ou mais',
    'População total',
    'População total - mulheres',
    'Porcentagem de lâmpadas LED na iluminação pública (%)',
    'Professores da Rede Municipal com Ensino Superior completo (%)',
    'Quantidade de lâmpadas na iluminação pública ',
    'Taxa de abandono escolar no Ensino Fundamental da Rede Municipal de Ensino (%)',
    'Taxa de abandono escolar no Ensino Médio da Rede Municipal de Ensino (%)',
    'Índice de envelhecimento',
    'V0005-População - 0 a 3 anos',
    'V0011-População - 4 a 17 anos',
    'V0016-Número de óbitos menores de 1 ano de idade',
    'V0017-Número de nascidos vivos',
    'V0091-Soma de alunos aprovados, reprovados e que abandonaram a escola no Ensino Médio na rede municipal',
    'V0206-Famílias que recebem recursos dos programas de transferência de renda',
    'V0245-Óbitos da população de 60 anos ou mais vítimas de causas externas, exceto vítimas de agressão',
    'V0246-Óbitos da população de 60 anos ou mais vítimas de agressão',
    'V0247-Óbitos de crianças e adolescentes vítimas de causas externas, exceto vítimas de agressão',
    'V0248-Óbitos de crianças e adolescentes vítimas de agressão',
    'V0250-Óbitos de mulheres por agressão',
    'V0281-Domicílios particulares permanentes',
    'V0288-Domicílios não conectados à rede geral de água',
    'V0289-Domicílios não conectados à rede geral de esgoto',
    'V0340-População total - masculina',
    'V0720-População em situação de rua acolhida',
    'V0721-População em situação de rua - Total recenseada',
    'V0723-População em idade ativa',
    'V0800-Idade média ao morrer (em anos)',
    'V0844-Número de alunos da Educação Infantil que moram até 1,5Km da escola'
    ]
    return df[colunas_selecionadas].copy()

# Criando um novo DataFrame contendo apenas as colunas especificadas
df_sel = selecionar_cols_relevantes(merged)
df_sel.to_csv("raw/merged_1sel_full.csv", sep=';')

# analisadas em relacao a nulls e zeros, vamos retirar as piores
def retirar_nulls(df):
    ruins = [
        'Escolas Municipais de Ensino Fundamental que oferecem turmas em educação integral em tempo integral (7h/dia ou mais)',
        #'Porcentagem de lâmpadas LED na iluminação pública (%)',
        'V0091-Soma de alunos aprovados, reprovados e que abandonaram a escola no Ensino Médio na rede municipal',
        'V0005-População - 0 a 3 anos',
        'V0011-População - 4 a 17 anos',
        'V0247-Óbitos de crianças e adolescentes vítimas de causas externas, exceto vítimas de agressão',
        'V0245-Óbitos da população de 60 anos ou mais vítimas de causas externas, exceto vítimas de agressão',
        'V0246-Óbitos da população de 60 anos ou mais vítimas de agressão',
        'V0248-Óbitos de crianças e adolescentes vítimas de agressão',
        'V0250-Óbitos de mulheres por agressão',
        'V0288-Domicílios não conectados à rede geral de água',
        'V0289-Domicílios não conectados à rede geral de esgoto',
        'V0720-População em situação de rua acolhida',
        'V0721-População em situação de rua - Total recenseada',
        'V0723-População em idade ativa',
        'V0800-Idade média ao morrer (em anos)',
        'V0844-Número de alunos da Educação Infantil que moram até 1,5Km da escola'
    ]
    return df.drop(columns=ruins).copy()

df_sem_nulls = retirar_nulls(df_sel)
df_sem_nulls.to_csv("raw/merged_2sel_full.csv", sep=';')

# normalização demografica

def norm_demografica(df):
    # Dicionário atualizado com as novas variáveis
    # Formato: {'Nome Original': ('Denominador Efetivo', Multiplicador, 'Nome Intuitivo')}
    # ATENÇÃO: A ordem importa. Variáveis que servem de denominador para outras estão no final.
    regras_ajustadas = {
        # === VARIÁVEIS ORIGINAIS DA SUA LISTA ===
        '01.01.01 Quantidade de famílias em situação de extrema pobreza (até 1/4 salário mínimo)': (
            'População total', 100000, 'Famílias em Extrema Pobreza (por 100 mil hab.)'
        ),
        '01.02.01 Quantidade de famílias em situação de pobreza (renda por pessoa de ⅛ até ¼ de salário-mínimo) ': (
            'População total', 100000, 'Famílias em situação de pobreza (por 100 mil hab.)'
        ),
        '01.02.02 Quantidade de famílias em situação de baixa renda (renda por pessoa de ¼ até ½ salário mínimo)': (
            'População total', 100000, 'Famílias de baixa renda (por 100 mil hab.)'
        ),
        '01.03.02 Quantidade de famílias beneficiárias do Programa Bolsa Família': (
            'População total', 100000, 'Famílias Beneficiárias Bolsa Família (por 100 mil hab.)'
        ),
        '01.05.02 Número de famílias em atendimento habitacional provisório (Auxílio Aluguel) por situação de risco e emergência ': (
            'População total', 100000, 'Famílias em Auxílio Aluguel Risco (por 100 mil hab.)'
        ),
        '11.01.07 Número estimado de domicílios em favelas': (
            'População total', 100000, 'Domicílios em Favelas (por 100 mil hab.)'
        ),
        '11.01.08 Total de famílias beneficiárias de Auxílio Aluguel por ano': (
            'População total', 100000, 'Familias beneficiárias de Auxílio Aluguel (por 100 mil hab.)'
        ),
        '11.05.02 Número de ocorrências atendidas – deslizamento': (
            'População total', 100000, 'Ocorrências de Deslizamento (por 100 mil hab.)'
        ),
        '11.05.03 Número de ocorrências atendidas – inundação': (
            'População total', 100000, 'Ocorrências de Inundação (por 100 mil hab.)'
        ),
        'Número de ocorrências atendidas – alagamento': (
            'População total', 100000, 'Ocorrências de Alagamento (por 100 mil hab.)'
        ),
        'Número de ocorrências atendidas – queda de árvore': (
            'População total', 100000, 'Ocorrências de Queda de Árvore (por 100 mil hab.)'
        ),
        'Número de acidentes de bicicleta': (
            'População total', 100000, 'Acidentes de Bicicleta (por 100 mil hab.)'
        ),
        '16.02.03 Número de casos notificados de violência contra crianças e adolescentes': (
            'População total', 100000, 'Casos notificados de violência contra crianças e adolescentes (por 100 mil hab.)'
        ),
        'Número de matrículas em tempo integral nas escolas públicas municipais de Educação Infantil': (
            'População total', 100000, 'Matrículas Educação Infantil Integral (por 100 mil hab.)'
        ),
        'Quantidade de lâmpadas na iluminação pública ': (
            'População total', 1, 'Lâmpadas de Iluminação Pública por Habitante'
        ),
        '11.01.03 Número de Unidades Habitacionais entregues (por meio de programas habitacionais e parcerias firmadas)': (
            'População total', 100000, 'Unidades Habitacionais entregues (por 100 mil hab.)'
        ),

        # === NOVAS VARIÁVEIS ADICIONADAS ===
        # Demografia
        'V0340-População total - masculina': ('População total', 100, 'População Masculina (%)'),
        
        # Assistência Social
        'V0206-Famílias que recebem recursos dos programas de transferência de renda': ('População total', 100000, 'Famílias com Transferência de Renda (por 100 mil hab.)'),

        # === DEPENDÊNCIAS DE DENOMINADORES === 
        # (As variáveis que usam os denominadores abaixo precisam ser processadas ANTES que o denominador seja deletado)

        # Usa "População com 60 anos ou mais" como base:
        'Número de casos de notificação de violência contra pessoas idosas': ('População com 60 anos ou mais', 100000, 'Violência contra Idosos (por 100 mil idosos)'),
        
        # Usa "V0017-Número de nascidos vivos" como base:
        'V0016-Número de óbitos menores de 1 ano de idade': ('V0017-Número de nascidos vivos', 1000, 'Taxa de Mortalidade Infantil (por 1.000 nascidos vivos)'),

        # === AS VARIÁVEIS QUE SERVEM DE DENOMINADOR (DELETADAS POR ÚLTIMO) ===
        'População com 60 anos ou mais': ('População total', 100, 'População com 60 Anos ou Mais (%)'),
        'População total - mulheres': ('População total', 100, 'População Feminina (%)'),
        'V0017-Número de nascidos vivos': ('População total', 1000, 'Taxa de Natalidade (por 1.000 hab.)'),
        'V0281-Domicílios particulares permanentes': ('População total', 1, 'Domicílios Particulares Permanentes (por habitante)'),
    }

    # Criando a cópia contendo todas as variáveis originais de df_selecionado
    df_normalizado = df.copy()

    # Executando a normalização diretamente com base nas colunas presentes em df_normalizado
    for col_num, (col_den, mult, nome_intuitivo) in regras_ajustadas.items():
        if col_num in df_normalizado.columns and col_den in df_normalizado.columns:
            denominador = df_normalizado[col_den].replace(0, pd.NA)
            df_normalizado[nome_intuitivo] = (
                df_normalizado[col_num] / denominador
            ) * mult
            df_normalizado.drop(columns=[col_num], inplace=True)  # Drop compacto
            print(
                f'Sucesso: "{col_num}" normalizado por "{col_den}" -> Criado'
                f' "{nome_intuitivo}".'
            )
        else:
            print(
                f'Erro: A coluna "{col_num}" ou o denominador "{col_den}" não foram'
                ' encontrados.'
            )
    return df_normalizado

df_norm = norm_demografica(df_sem_nulls)
df_norm.to_csv("normalizado/sel3_full.csv", sep=';')


# %%
