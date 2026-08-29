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

import baqueano.extract as ex
from baqueano.canon import BaseCanonica

from .metrica import DEV, HOLDOUT
from .ruido import mede

FRACOES = (0.0, 0.10, 0.20, 0.30, 0.50)
SEMENTES = 5


@contextlib.contextmanager
def sem_ancora_aberta():
    """Desliga as vias abertas de reconhecimento, deixando so a lista fechada.

    E o que permite medir a ablacao das duas versoes sobre a MESMA base, em vez
    de comparar com um numero historico medido noutro acervo e noutro codigo.
    """
    nunca = ex.re.compile(r'(?!)')          # nunca casa
    original = (ex.ANCORA_NUCLEO, ex.ANCORA_SIGLA, ex.ANCORA_PROCESSO)
    try:
        ex.ANCORA_NUCLEO = ex.ANCORA_SIGLA = ex.ANCORA_PROCESSO = nunca
        yield
    finally:
        ex.ANCORA_NUCLEO, ex.ANCORA_SIGLA, ex.ANCORA_PROCESSO = original


@contextlib.contextmanager
def vocabulario(classes):
    """Roda o bloco com CLASSES reduzido e devolve o modulo ao estado original.

    A ablacao precisa trocar expressoes ja compiladas dentro de baqueano.extract.
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


def curva(base, docs, completo, aberta=True):
    """Escore medio para cada fracao removida, com ou sem a ancora aberta."""
    for fracao in FRACOES:
        escores = []
        for semente in range(SEMENTES if fracao else 1):
            rng = random.Random(semente)
            manter = [c for c in completo if rng.random() >= fracao]
            if aberta:
                with vocabulario(manter):
                    escores.append(mede(docs, base, 0, 0))
            else:
                with sem_ancora_aberta(), vocabulario(manter):
                    escores.append(mede(docs, base, 0, 0))
        yield fracao, escores


def main():
    base = BaseCanonica()
    docs = DEV + HOLDOUT
    completo = list(ex.CLASSES)
    print(f'vocabulario completo: {len(completo)} entradas')
    print(f'{"removido":>9s} | {"com ancora aberta":>18s} | {"so lista fechada":>17s}')
    com = {f: sum(e) / len(e) for f, e in curva(base, docs, completo, True)}
    sem = {f: sum(e) / len(e) for f, e in curva(base, docs, completo, False)}
    for fracao in FRACOES:
        print(f'  {fracao:>6.0%}   | {com[fracao]:>17.1%} | {sem[fracao]:>16.1%}')


if __name__ == '__main__':
    main()
