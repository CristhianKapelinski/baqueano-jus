# -*- coding: utf-8 -*-
"""Quanto do escore depende do vocabulario FECHADO de classe processual?

Remove uma fracao aleatoria das entradas escritas a mao e remede. E o proxy
direto do risco que o conjunto cego traz: uma classe processual que nao esta na
lista. Se a curva cai rapido, o resultado depende do inventario; se cai devagar,
depende do formato, que e o que se quer.

    python -m avaliacao.ablacao
"""
import contextlib
import random

import cacador.extract as ex
from cacador.canon import BaseCanonica

from .metrica import DEV, HOLDOUT
from .ruido import mede

FRACOES = (0.0, 0.10, 0.20, 0.30, 0.50)
SEMENTES = 5


@contextlib.contextmanager
def vocabulario(classes):
    """Roda o bloco com CLASSES reduzido e devolve o modulo ao estado original.

    A ablacao precisa trocar expressoes ja compiladas dentro de cacador.extract.
    Feita solta, a troca deixa o modulo corrompido se algo falhar no meio; por
    isso vive num contexto que restaura sempre, inclusive em excecao.
    """
    original = (ex.CLASSES, ex._CLASSE_ALT, ex.CADEIA_CLASSE)
    try:
        alt = '|'.join(classes)
        ex.CLASSES, ex._CLASSE_ALT = classes, alt
        ex.CADEIA_CLASSE = ex.re.compile(
            r'(?:' + ex.ORDINAL_PREFIXO + r')?'
            r"(?:(?:" + alt + r")\.?['’]?s?" + ex._CONECTOR + r'?){1,6}'
            + ex._MARCA_FIM, ex.re.I)
        yield
    finally:
        ex.CLASSES, ex._CLASSE_ALT, ex.CADEIA_CLASSE = original


def curva(base, docs, completo):
    """Escore medio para cada fracao removida."""
    for fracao in FRACOES:
        escores = []
        for semente in range(SEMENTES if fracao else 1):
            rng = random.Random(semente)
            manter = [c for c in completo if rng.random() >= fracao]
            with vocabulario(manter):
                escores.append(mede(docs, base, 0, 0))
        yield fracao, escores


def main():
    base = BaseCanonica()
    docs = DEV + HOLDOUT
    completo = list(ex.CLASSES)
    print(f'vocabulario completo: {len(completo)} entradas')
    print('removido | escore medio')
    for fracao, escores in curva(base, docs, completo):
        media = sum(escores) / len(escores)
        detalhe = ('[' + ', '.join(f'{e:.1%}' for e in escores) + ']') if fracao else ''
        print(f'  {fracao:>5.0%}   | {media:6.1%}  {detalhe}')


if __name__ == '__main__':
    main()
