# Ambiente de verificacao do desafio Jusbrasil x BRACIS 2026.
#
# A solucao nao usa modelo de linguagem, entao a imagem nao baixa pesos e o
# container nao precisa de rede em nenhum momento. Nao ha GPU no caminho de
# execucao: os 26 documentos de desenvolvimento saem em ~1 s de CPU, muito
# abaixo do teto de 60 s por documento.
#
# Pesos e dados NAO vao dentro da imagem. A base de referencia e montada.
FROM python:3.12-slim

# run.py usa apenas a biblioteca padrao. As dependencias abaixo servem as
# suites de avaliacao e ficam pinadas para a imagem ser reproduzivel.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

WORKDIR /app
COPY . /app

# Determinismo: sem amostragem, sem semente aleatoria no caminho de inferencia.
# PYTHONHASHSEED fixa a unica fonte de variacao que restaria, a ordem de
# iteracao de conjuntos.
ENV PYTHONHASHSEED=0 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Contrato de execucao do desafio:
#   docker run --rm --network none \
#     -v /caminho/dados:/data:ro -v /caminho/saida:/data/out \
#     baqueano --input /data/in --output /data/out
ENTRYPOINT ["python", "run.py"]
CMD ["--input", "/data/in", "--output", "/data/out"]
