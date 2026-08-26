# Ambiente de reproducao. A solucao nao usa modelo de linguagem nem GPU:
# roda os 26 documentos em ~1 s de CPU, bem dentro do envelope do desafio
# (1 GPU 24 GB, 8 vCPUs, 32 GB RAM).
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# O dataset nao vai na imagem (nao e nosso para redistribuir). Monte-o:
#   docker run --rm \
#     -v /caminho/material_desafio_jusbrasil_bracis:/dados:ro \
#     -v "$PWD/saida":/saida \
#     cacador
ENV PYTHONHASHSEED=0
CMD ["python", "run.py", "/dados/txt", "/saida/json", \
     "--db", "/dados/desafio1_bracis.db", \
     "--submissao", "/saida/submission.csv"]
