#!/usr/bin/env bash
# O mesmo que o run.sh, com os mesmos argumentos, dentro do container do
# Dockerfile:
#
#   bash run_docker.sh <caminho_db> <pasta_txt> <arquivo_saida.csv>
#
# Constroi a imagem (na primeira vez), monta a base, a pasta dos .txt e a pasta
# de saida, e roda sem rede. Os arquivos de saida ficam com o seu usuario.
set -euo pipefail

if [[ $# -ne 3 ]]; then
    echo "uso: bash run_docker.sh <caminho_db> <pasta_txt> <arquivo_saida.csv>" >&2
    exit 2
fi
[[ -f "$1" ]] || { echo "base nao encontrada: $1" >&2; exit 1; }
[[ -d "$2" ]] || { echo "pasta de .txt nao encontrada: $2" >&2; exit 1; }

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGEM="${IMAGEM:-baqueano}"
DB="$(realpath "$1")"
TXT="$(realpath "$2")"
if [[ "$3" == *.csv ]]; then
    mkdir -p "$(dirname "$3")"
    SAIDA="$(realpath "$(dirname "$3")")"; ALVO="/saida/$(basename "$3")"
else
    mkdir -p "$3"
    SAIDA="$(realpath "$3")"; ALVO="/saida"
fi

docker build -q -t "$IMAGEM" "$AQUI" >/dev/null
exec docker run --rm --network none --user "$(id -u):$(id -g)" \
    -v "$DB:/entrada/base.db:ro" \
    -v "$TXT:/entrada/txt:ro" \
    -v "$SAIDA:/saida" \
    "$IMAGEM" /entrada/base.db /entrada/txt "$ALVO"
