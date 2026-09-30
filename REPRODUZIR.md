# Reprodução

Determinístico por construção: sem modelo de linguagem, sem amostragem, sem
semente. A mesma entrada dá byte a byte a mesma saída.

## Os dados

`dados/` fica fora do git e guarda o pacote do Kaggle como veio:

```bash
kaggle competitions download desafio-jusbrasil-bracis-2026 -p dados
cd dados && unzip desafio-jusbrasil-bracis-2026.zip && cd ..
```

Ficam lá `desafio1_bracis.db`, `goldenset_offsets.csv`, `txt/`,
`json_to_submission.py`, `kaggle_metric.py` e `sample_submission.csv`.

## O comando exato que gera as predições submetidas

```bash
bash run.sh dados/desafio1_bracis.db dados/txt submission.csv
```

Equivale a `python run.py --db dados/desafio1_bracis.db --input dados/txt
--output submission_json --submissao submission.csv`.

É o comando da submissão de 15/09 que tirou 1,10000 no Kaggle. O
`submission.csv` sai do conversor do organizador, `dados/json_to_submission.py`;
sem ele, `run.py` escreve o mesmo formato internamente.

`run.py` usa **apenas a biblioteca padrão do Python 3.12**. Foi rodado com o
interpretador do sistema, sem pandas nem numpy instalados. Não há download de
pesos, chamada de rede ou dependência de GPU.

## Contrato de execução do desafio

A entrega final (e-mail de 30/09) pede um ponto de entrada único que recebe o
caminho do `.db` e a pasta dos `.txt`:

```bash
bash run.sh <caminho_db> <pasta_txt> <arquivo_saida.csv>
```

Sai o CSV de submissão em `<arquivo_saida.csv>` e o JSON completo de cada
documento em `<arquivo_saida>_json/`. Se o terceiro argumento não terminar em
`.csv`, ele é tratado como pasta: os JSONs vão nela e o CSV em
`<pasta>/submission.csv`.

O contrato de 28/08 continua valendo. `run.sh --input ... --output ...` repassa
os argumentos ao `run.py`, que procura a base dentro da pasta de entrada ou ao
lado dela, depois em `/data` e por fim em `dados/`, pelo nome
`desafio1_bracis.db` ou como único `.db` da pasta:

```
/data/
  <base>.db
  in/          os .txt
  out/         os .json, escritos aqui
```

Para rodar no container, o `run_docker.sh` aceita os mesmos três argumentos:
constrói a imagem, monta a base, os `.txt` e a pasta de saída, e roda com
`--network none`. Os arquivos de saída ficam com o usuário que chamou.

```bash
bash run_docker.sh <caminho_db> <pasta_txt> <arquivo_saida.csv>
```

A imagem tem 120 MB, não instala nada além do Python 3.12 da imagem-base (fixada
por digest) e usa o `run.sh` como entrada. Direto no `docker`:

```bash
docker build -t baqueano .
docker run --rm --network none -v /caminho/data:/data baqueano \
  /data/<base>.db /data/in /data/out/submission.csv
# sem argumentos: --input /data/in --output /data/out
docker run --rm --network none -v /caminho/data:/data baqueano
```

Os dois caminhos foram testados na base de desenvolvimento e saem idênticos,
byte a byte, à submissão de 15/09.

A base da avaliação é outra, e o código não depende de nenhum id da base de
desenvolvimento: o índice de dispositivos e súmulas sai da primeira linha de
cada registro. Foi testado com três bases alteradas (um dispositivo a mais, um a
menos, um acórdão de tribunal novo) e com a base sob outro nome: o lote roda
inteiro nos quatro casos.

## Modelos

**Nenhum.** A solução é simbólica: extração por forma jurídica, resolução
contra a base canônica distribuída pela organização, e a tabela de decisão do
enunciado. O único valor ajustado a partir de dados é a constante de confiança,
em `baqueano/calibracao.py`, regenerável com:

```bash
python -m ferramentas.confianca
```

A ferramenta mede a acurácia no goldenset, compara a constante com as
estratégias ajustadas e grava a constante. Rodada sem argumentos, reproduz o
valor submetido, 1,0. O porquê de não haver margem está no README, na seção de
confiança.

## Envelope de execução

| recurso | exigido pelo desafio | usado |
|---|---|---|
| GPU | até 24 GB de VRAM | nenhuma |
| RAM | até 32 GB | 130 MB |
| tempo | média de até 60 s por documento | 1,2 s para os 26 documentos |

## Verificar

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python verifica.py
```
