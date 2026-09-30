#!/usr/bin/env bash
# Ponto de entrada unico da avaliacao final:
#
#   bash run.sh <caminho_db> <pasta_txt> <arquivo_saida.csv>
#
# Escreve o CSV de submissao em <arquivo_saida.csv> e o JSON completo de cada
# documento, do contrato de saida, em <arquivo_saida>_json/. Se o terceiro
# argumento nao terminar em .csv, ele e tratado como pasta: os JSONs vao nela e
# o CSV vai em <pasta>/submission.csv.
#
# O contrato de 28/08 (--input/--output) continua valendo:
#   bash run.sh --input /data/in --output /data/out [--db base.db]
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python3}"

if [[ "${1:-}" == --* ]]; then
    exec "$PY" "$AQUI/run.py" "$@"
fi

if [[ $# -ne 3 ]]; then
    echo "uso: bash run.sh <caminho_db> <pasta_txt> <arquivo_saida.csv>" >&2
    exit 2
fi

DB="$1"; TXT="$2"; SAIDA="$3"
if [[ "$SAIDA" == *.csv ]]; then
    CSV="$SAIDA"; JSONS="${SAIDA%.csv}_json"
else
    JSONS="$SAIDA"; CSV="$SAIDA/submission.csv"
fi
mkdir -p "$JSONS" "$(dirname "$CSV")"
exec "$PY" "$AQUI/run.py" --db "$DB" --input "$TXT" --output "$JSONS" --submissao "$CSV"
