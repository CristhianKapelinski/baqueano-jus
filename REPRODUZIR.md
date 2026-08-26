# Reprodução

Determinístico por construção: sem modelo de linguagem, sem amostragem, sem
semente. A mesma entrada dá byte a byte a mesma saída.

## O comando exato que gera as predições submetidas

```bash
python run.py <pasta_com_os_txt> saida_json \
  --db <caminho>/desafio1_bracis.db \
  --submissao submission.csv
```

`run.py` usa **apenas a biblioteca padrão do Python 3.12**. Não há download de
pesos, chamada de rede ou dependência de GPU.

## Docker

```bash
docker build -t cacador .
docker run --rm \
  -v /caminho/material_desafio_jusbrasil_bracis:/dados:ro \
  -v "$PWD/saida":/saida \
  cacador
```

## Modelos

**Nenhum.** A solução é simbólica: extração por forma jurídica, resolução
contra a base canônica distribuída pela organização, e a tabela de decisão do
enunciado. O único componente ajustado é a calibração da confiança — uma
regressão logística de 27 pesos, versionada em `cacador/calibracao.py` e
regenerável com:

```bash
python -m ferramentas.confianca
```

que treina em `dados/goldenset.csv` mais os conjuntos sintéticos gerados por
`ferramentas/gerador.py` (sementes fixas: 20260828 e 777).

## Envelope de execução

| recurso | exigido pelo desafio | usado |
|---|---|---|
| GPU | até 24 GB VRAM | **nenhuma** |
| RAM | até 32 GB | ~130 MB |
| tempo | — | ~1,2 s para 26 documentos |

## Verificar

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python verifica.py
```
