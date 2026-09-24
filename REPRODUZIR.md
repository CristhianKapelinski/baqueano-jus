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
python run.py dados/txt saida_json --submissao submission.csv
```

É o comando da submissão de 15/09 que tirou 1,10000 no Kaggle. O
`submission.csv` sai do conversor do organizador, `dados/json_to_submission.py`;
sem ele, `run.py` escreve o mesmo formato internamente.

`run.py` usa **apenas a biblioteca padrão do Python 3.12**. Foi rodado com o
interpretador do sistema, sem pandas nem numpy instalados. Não há download de
pesos, chamada de rede ou dependência de GPU.

## Contrato de execução do desafio

O desafio fixa `--input` e `--output`. A base é procurada dentro da pasta de
entrada ou ao lado dela, depois em `/data` e por fim em `dados/`:

```
/data/
  desafio1_bracis.db
  in/          os .txt
  out/         os .json, escritos aqui
```

```bash
python run.py --input /data/in --output /data/out
```

Esse arranjo foi testado com o Python do sistema: 26 documentos, 192 citações.
O `Dockerfile` roda exatamente esse comando como padrão:

```bash
docker build -t baqueano .
docker run --rm --network none \
  -v /caminho/data:/data \
  baqueano
```

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
