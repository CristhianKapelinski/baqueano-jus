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
import unicodedata
from pathlib import Path

from cacador.canon import BaseCanonica
from cacador.pipeline import processa_documento

CHAVES_DO_CONTRATO = ('id', 'inicio', 'fim', 'trecho', 'tipo', 'classificacao',
                      'resolucao', 'confianca')


def _confere_encoding(texto, doc, arq):
    """As regras de encoding do desafio sao rigidas - falhar alto e melhor.

    UTF-8 sem BOM, quebra LF, Unicode NFC, offsets em codepoints com fim
    exclusivo. Conferimos o que da para conferir do nosso lado: que o trecho
    entregue e exatamente texto[inicio:fim].
    """
    if texto.startswith('\ufeff'):
        sys.exit(f'{arq}: arquivo com BOM - o desafio exige UTF-8 sem BOM')
    if '\r' in texto:
        sys.exit(f'{arq}: quebra CRLF - o desafio exige LF')
    if unicodedata.normalize('NFC', texto) != texto:
        sys.exit(f'{arq}: texto nao esta em NFC')
    for c in doc['citacoes']:
        if texto[c['inicio']:c['fim']] != c['trecho']:
            sys.exit(f"{arq}: span {c['id']} nao bate com o texto "
                     f"({texto[c['inicio']:c['fim']]!r} != {c['trecho']!r})")


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
        _confere_encoding(texto, doc, arq)
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
