# -*- coding: utf-8 -*-
"""Quanto do escore depende do vocabulario FECHADO de classe processual?

Remove uma fracao aleatoria das entradas de CLASSES e remede. E o proxy direto
para o risco do conjunto cego: uma classe processual que nao esta na lista.
"""
import importlib
import random

from eval import DEV, HOLDOUT
from stress import mede
import cacador.extract as ex
from cacador.canon import BaseCanonica


def recompila(classes):
    ex.CLASSES = classes
    alt = '|'.join(classes)
    ex._CLASSE_ALT = alt
    ex.CADEIA_CLASSE = ex.re.compile(
        r'(?:' + ex.ORDINAL_PREFIXO + r')?'
        r'(?:(?:' + alt + r')\.?' + ex._CONECTOR + r'?){1,6}' + ex._MARCA_FIM, ex.re.I)
    ex.VAGA_CLASSE_ANO_REL = ex.re.compile(
        r'\b(' + alt + r')\s*'
        r'(?:d[oe]\s+(' + '|'.join(ex.TRIBUNAIS) + r')\s*,?\s*)?'
        r'de\s*(\d{4})\s*,?\s*'
        r'(?:Rel\.?|relatoria|relatad[oa])\s*(?:Min\.?)?\s*d?[ceo]?\s*(' + ex._NOME + r')',
        ex.re.I)


if __name__ == '__main__':
    base = BaseCanonica()
    docs = DEV + HOLDOUT
    completo = list(ex.CLASSES)
    print(f'vocabulario completo: {len(completo)} entradas')
    print('removido | escore medio (5 sementes)')
    for frac in (0.0, 0.10, 0.20, 0.30, 0.50):
        escores = []
        for s in range(5 if frac else 1):
            rng = random.Random(s)
            manter = [c for c in completo if rng.random() >= frac]
            recompila(manter)
            escores.append(mede(docs, base, 0, 0))
        recompila(completo)
        print(f'  {frac:>5.0%}   | {sum(escores)/len(escores):6.1%}  ' +
              ('[' + ', '.join(f'{e:.1%}' for e in escores) + ']' if frac else ''))
