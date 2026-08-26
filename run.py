# -*- coding: utf-8 -*-
"""Le uma pasta de documentos .txt e escreve os JSONs do contrato.

    python run.py <pasta_txt> <pasta_saida> [--submissao submission.csv]

O CSV de submissao e gerado pelo proprio conversor do organizador
(dados/json_to_submission.py), para garantir que o formato e o dele.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from cacador.canon import BaseCanonica
from cacador.pipeline import processa_documento

CHAVES_DO_CONTRATO = ('inicio', 'fim', 'trecho', 'tipo', 'classificacao',
                      'confianca', 'resolucao')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('entrada', help='pasta com os .txt')
    ap.add_argument('saida', help='pasta onde escrever os .json')
    ap.add_argument('--db', default=None, help='caminho do desafio1_bracis.db')
    ap.add_argument('--submissao', default=None, help='escreve tambem o CSV do Kaggle')
    a = ap.parse_args()

    base = BaseCanonica(a.db) if a.db else BaseCanonica()
    entrada, saida = Path(a.entrada), Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)

    arquivos = sorted(entrada.glob('*.txt'))
    if not arquivos:
        sys.exit(f'nenhum .txt em {entrada}')
    total = 0
    for arq in arquivos:
        texto = arq.read_text(encoding='utf-8')
        doc = processa_documento(texto, base, documento_id=arq.stem)
        doc['citacoes'] = [{k: c[k] for k in CHAVES_DO_CONTRATO} for c in doc['citacoes']]
        (saida / f'{arq.stem}.json').write_text(
            json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')
        total += len(doc['citacoes'])
    print(f'{len(arquivos)} documentos, {total} citacoes -> {saida}')

    if a.submissao:
        conversor = Path(__file__).parent / 'dados' / 'json_to_submission.py'
        subprocess.run([sys.executable, str(conversor), str(saida), a.submissao],
                       check=True)


if __name__ == '__main__':
    main()
