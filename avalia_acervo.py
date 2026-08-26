# -*- coding: utf-8 -*-
"""Avalia o extrator nos 1.018 registros da base - sem gabarito, em escala.

Os acordaos do acervo citam uns aos outros o tempo todo, em prosa juridica de
verdade (nao sintetica). Isso da um conjunto de teste ~40x maior que o
goldenset, e de graca:

  positivo conhecido = uma ocorrencia, no CORPO de um acordao, de um numero que
  resolve para OUTRO feito do acervo. Nao e citacao anotada por ninguem, mas e
  inegavelmente uma citacao - o numero existe, e do acervo, e nao e o numero
  deste documento.

Mede-se quantos desses o extrator cobre com um span. E um limite inferior de
recall: o extrator pode acertar citacoes que este script nao sabe contar.
"""
import argparse
import collections
import random
import re

from cacador.canon import BaseCanonica, PARSERS
from cacador.extract import extrai
from cacador.normalize import digitos, variantes_cnj

# Um numero, do jeito que aparece no corpo de um acordao.
NUM_NO_TEXTO = re.compile(r'\d[\d.\s–-]{4,30}\d')
# numero precedido de 'Lei'/'Decreto'/'art' e dispositivo legal, nao processo:
# o teste nao deve cobrar isso do extrator de jurisprudencia.
E_LEI = re.compile(r'(?:lei|decreto|medida\s+provis[óo]ria|s[úu]mula|art(?:igo)?s?\.?|'
                   r'inciso|par[áa]grafo|§|R\$|valor\s+de\s+R\$)'
                   r'\s*(?:complementar\s*)?n?[.ºo°]{0,2}\s*$', re.I)


def ocorrencias_resolviveis(texto, base, numero_proprio, tribunal):
    """Posicoes onde aparece o numero de OUTRO feito do acervo."""
    achados = []
    for m in NUM_NO_TEXTO.finditer(texto):
        if '. ' in m.group():
            continue          # atravessou fim de frase: '13.352/2016. 4'
        if m.start() and texto[m.start() - 1] in '/.-0123456789':
            continue          # comeco colado noutro numero
        d = digitos(m.group())
        if len(d) < 5:
            continue
        if d == numero_proprio or d.lstrip('0') == (numero_proprio or '').lstrip('0'):
            continue
        if E_LEI.search(texto[max(0, m.start() - 40):m.start()]):
            continue
        for v in variantes_cnj(d):
            if (v, tribunal) in base.acordaos or any(
                    (v, t) in base.acordaos for t in ('STF', 'STJ', 'TSE', 'TST', 'STM')):
                achados.append((m.start(), m.end(), d))
                break
    return achados


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--amostra', type=int, default=120,
                    help='quantos acordaos avaliar (0 = todos)')
    ap.add_argument('--semente', type=int, default=7)
    ap.add_argument('--janela', type=int, default=0,
                    help='quantos caracteres de cada acordao usar (0 = tudo)')
    a = ap.parse_args()

    base = BaseCanonica()
    linhas = base.con.execute(
        "SELECT documento_id,tribunal,texto FROM documentos WHERE natureza='acordao'"
    ).fetchall()
    if a.amostra:
        rng = random.Random(a.semente)
        linhas = rng.sample(linhas, min(a.amostra, len(linhas)))

    total = cobertos = 0
    docs_com_falha = collections.Counter()
    exemplos = []
    for did, trib, texto in linhas:
        proprio = PARSERS[trib](texto)
        trecho = texto[:a.janela] if a.janela else texto
        alvos = ocorrencias_resolviveis(trecho, base, proprio, trib)
        if not alvos:
            continue
        spans = extrai(trecho)
        for ini, fim, d in alvos:
            total += 1
            if any(s['inicio'] <= ini and fim <= s['fim'] + 2 for s in spans):
                cobertos += 1
            else:
                docs_com_falha[did] += 1
                if len(exemplos) < 25:
                    exemplos.append((did, trib, repr(trecho[max(0, ini - 60):fim + 10])))
    print(f'acordaos avaliados: {len(linhas)}  (primeiros {a.janela} chars de cada)')
    print(f'citacoes resolviveis encontradas: {total}')
    print(f'cobertas por um span do extrator: {cobertos}  ({cobertos/total:.1%})' if total else 'nada')
    print(f'\ndocumentos com pelo menos uma falha: {len(docs_com_falha)}')
    print('\nexemplos de citacao NAO coberta:')
    for e in exemplos:
        print(f'  [{e[1]}] {e[2][:150]}')


if __name__ == '__main__':
    main()
