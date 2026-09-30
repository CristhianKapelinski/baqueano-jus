# -*- coding: utf-8 -*-
"""Le uma pasta de documentos .txt e escreve os JSONs do contrato.

    python run.py <pasta_txt> <pasta_saida> [--db base.db] [--submissao submission.csv]

Na avaliacao final o ponto de entrada e o run.sh, que passa a base explicita.

O CSV de submissao e gerado pelo proprio conversor do organizador
(dados/json_to_submission.py), para garantir que o formato e o dele.
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import unicodedata
from pathlib import Path

from baqueano.canon import BaseCanonica
from baqueano.pipeline import ESQUEMA, processa_documento

CHAVES_DO_CONTRATO = ('id', 'inicio', 'fim', 'trecho', 'tipo', 'classificacao',
                      'resolucao', 'confianca')


def _acha_base(entrada):
    """Localiza o desafio1_bracis.db sem depender de rede nem de caminho fixo.

    Na verificacao a base de referencia e montada pela organizacao, e o contrato
    de execucao so fixa --input e --output. Procuramos no lugar mais provavel
    (ao lado da entrada) antes de cair no symlink de desenvolvimento.
    """
    pastas = [Path(entrada).parent, Path(entrada), Path('/data'),
              Path(__file__).parent / 'dados']
    for pasta in pastas:
        if (pasta / 'desafio1_bracis.db').is_file():
            return str(pasta / 'desafio1_bracis.db')
        # a base da avaliacao final e outra e pode ter outro nome: um .db
        # sozinho na pasta so pode ser ela
        outros = sorted(pasta.glob('*.db')) if pasta.is_dir() else []
        if len(outros) == 1:
            return str(outros[0])
    return None


def _le(arq, avisos):
    """Le o documento, substituindo byte invalido em vez de desistir dele.

    O desafio garante UTF-8 valido, entao isto e defesa. Mas desistir custa o
    documento inteiro, enquanto substituir custa um caractere: `errors=replace`
    poe um U+FFFD por byte invalido, o comprimento em codepoints nao muda, e as
    citacoes ao redor continuam extraiveis com os offsets certos.
    """
    bruto = arq.read_bytes()
    texto = bruto.decode('utf-8', errors='replace')
    if '\ufffd' in texto:
        avisos.append(f'{arq.name}: {texto.count(chr(0xfffd))} byte(s) invalido(s) '
                      'substituido(s), o resto do documento foi processado')
    return texto


def _escreve_submissao(pasta_json, destino):
    """Mesmo CSV que dados/json_to_submission.py produz, sem depender dele."""
    linhas = []
    for arq in sorted(Path(pasta_json).glob('*.json')):
        doc = json.loads(arq.read_text(encoding='utf-8'))
        partes = []
        for c in doc.get('citacoes', []):
            resol = c.get('resolucao') or {}
            idc = str(resol.get('id_canonico', '') or '').strip() or '-'
            conf = c.get('confianca')
            partes.append(f"{int(c['inicio'])},{int(c['fim'])},{c['classificacao']},"
                          f"{idc},{'-' if conf is None else format(float(conf), '.4f')}")
        linhas.append((doc.get('documento_id') or arq.stem, '|'.join(partes) or '-'))
    with open(destino, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['documento_id', 'citacoes'])
        w.writerows(linhas)


def _confere_encoding(texto, doc, arq):
    """As regras de encoding do desafio sao rigidas - falhar alto e melhor.

    UTF-8 sem BOM, quebra LF, Unicode NFC, offsets em codepoints com fim
    exclusivo. Conferimos o que da para conferir do nosso lado: que o trecho
    entregue e exatamente texto[inicio:fim].
    """
    if texto.startswith('\ufeff'):
        raise ValueError('arquivo com BOM - o desafio exige UTF-8 sem BOM')
    if '\r' in texto:
        raise ValueError('quebra CRLF - o desafio exige LF')
    if unicodedata.normalize('NFC', texto.replace('\ufffd', '')) != texto.replace('\ufffd', ''):
        raise ValueError('texto nao esta em NFC')
    for c in doc['citacoes']:
        if texto[c['inicio']:c['fim']] != c['trecho']:
            raise ValueError(f"span {c['id']} nao bate com o texto "
                             f"({texto[c['inicio']:c['fim']]!r} != {c['trecho']!r})")


def main():
    ap = argparse.ArgumentParser(
        description='Verificador de citacoes juridicas. Aceita o contrato fixo do '
                    'desafio (--input/--output) e tambem argumentos posicionais.')
    ap.add_argument('entrada', nargs='?', help='pasta com os .txt')
    ap.add_argument('saida', nargs='?', help='pasta onde escrever os .json')
    ap.add_argument('--input', dest='entrada_flag', help='pasta com os .txt')
    ap.add_argument('--output', dest='saida_flag', help='pasta onde escrever os .json')
    ap.add_argument('--db', default=None, help='caminho do desafio1_bracis.db')
    ap.add_argument('--submissao', default=None, help='escreve tambem o CSV de submissao')
    a = ap.parse_args()

    origem = a.entrada_flag or a.entrada
    destino = a.saida_flag or a.saida
    if not origem or not destino:
        ap.error('informe as pastas de entrada e saida, por posicao ou por '
                 '--input/--output')
    caminho_db = a.db or _acha_base(origem)
    base = BaseCanonica(caminho_db) if caminho_db else BaseCanonica()
    entrada, saida = Path(origem), Path(destino)
    saida.mkdir(parents=True, exist_ok=True)

    arquivos = sorted(entrada.glob('*.txt'))
    if not arquivos:
        sys.exit(f'nenhum .txt em {entrada}')
    total = 0
    avisos, falhas = [], []
    for arq in arquivos:
        # ISOLAMENTO POR DOCUMENTO. O conjunto de teste e processado em lote,
        # sem ninguem por perto: um arquivo com encoding estranho ou estrutura
        # inesperada nao pode custar o lote inteiro. Falha vira predicao vazia
        # para aquele documento - perda de um, nao de todos.
        try:
            texto = _le(arq, avisos)
            doc = processa_documento(texto, base, documento_id=arq.stem)
            doc['citacoes'] = [{k: c[k] for k in CHAVES_DO_CONTRATO}
                               for c in doc['citacoes']]
            _confere_encoding(texto, doc, arq)
        except Exception as e:                       # noqa: BLE001 - de proposito
            falhas.append(f'{arq.name}: {type(e).__name__}: {e}')
            doc = {'schema_version': ESQUEMA, 'documento_id': arq.stem, 'citacoes': []}
        (saida / f'{arq.stem}.json').write_text(
            json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')
        total += len(doc['citacoes'])
    print(f'{len(arquivos)} documentos, {total} citacoes -> {saida}')
    for titulo, lista in (('recuperado(s)', avisos), ('sem predicao', falhas)):
        if lista:
            print(f'AVISO: {len(lista)} documento(s) {titulo}:', file=sys.stderr)
            for m in lista:
                print('  ' + m, file=sys.stderr)

    if a.submissao:
        conversor = Path(__file__).parent / 'dados' / 'json_to_submission.py'
        if conversor.exists():
            subprocess.run([sys.executable, str(conversor), str(saida), a.submissao],
                           check=True)
        else:
            # o conversor do organizador vem no pacote de dados; sem ele,
            # escrevemos o mesmo CSV aqui - o formato esta no proprio script
            _escreve_submissao(saida, a.submissao)
            print(f'{a.submissao}: {len(arquivos)} documentos '
                  '(conversor do organizador ausente, formato reproduzido)')


if __name__ == '__main__':
    main()
