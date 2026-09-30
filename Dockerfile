# Ambiente de verificacao do desafio Jusbrasil x BRACIS 2026.
#
# A solucao nao usa modelo de linguagem, entao a imagem nao baixa pesos e o
# container nao precisa de rede em nenhum momento. Nao ha GPU no caminho de
# execucao: os 26 documentos de desenvolvimento saem em ~1 s de CPU, muito
# abaixo do teto de 60 s por documento.
#
# Pesos e dados NAO vao dentro da imagem. A base de referencia e montada.
# Imagem-base fixada por digest: o build de qualquer maquina usa o mesmo Python.
FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f

# run.py usa apenas a biblioteca padrao, entao a imagem nao instala nada. As
# dependencias de requirements.txt servem so as suites de avaliacao, que rodam
# fora do container.

WORKDIR /app
COPY . /app

# Determinismo: sem amostragem, sem semente aleatoria no caminho de inferencia.
# PYTHONHASHSEED fixa a unica fonte de variacao que restaria, a ordem de
# iteracao de conjuntos.
ENV PYTHONHASHSEED=0 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Ponto de entrada unico (regras da entrega final, 30/09). O jeito simples de
# usar a imagem e o run_docker.sh, que monta os caminhos sozinho:
#   bash run_docker.sh <caminho_db> <pasta_txt> <arquivo_saida.csv>
# Direto no docker, com a base e os .txt montados em /data:
#   docker run --rm --network none -v /caminho/dados:/data baqueano \
#     /data/<base>.db /data/in /data/out/submission.csv
# Sem argumentos vale o contrato de 28/08, com a base achada em /data.
ENTRYPOINT ["bash", "run.sh"]
CMD ["--input", "/data/in", "--output", "/data/out"]
