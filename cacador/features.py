# -*- coding: utf-8 -*-
"""Features da citacao, para o modelo de confianca.

Tudo aqui e calculavel em tempo de execucao, so com a biblioteca padrao: o
treino usa numpy, a inferencia e um produto interno.
"""
import math

from .normalize import digitos, limpa_quebras

FORMAS = ('numerada', 'sumula', 'artigo', 'vaga_trib_ano_rel',
          'vaga_classe_ano_rel', 'vaga_anaforica')
CLASSES = ('real', 'inventada', 'incompleta')
# Qual regra reconheceu a citacao. A lista fechada de classes e a mais
# confiavel; a sigla generica e a mais arriscada.
ANCORAS = ('classe', 'tst', 'nucleo', 'processo', 'sigla')

NOMES = (('vies',)
         + tuple(f'forma={f}' for f in FORMAS)
         + tuple(f'classe={c}' for c in CLASSES)
         + ('n_feitos', 'sem_feito', 'muitos_feitos', 'log_digitos', 'e_cnj',
            'tem_pista_tribunal', 'pista_confere', 'letras_ocr', 'tem_quebra',
            'log_tamanho', 'diploma_conhecido', 'herdada_de_lista')
         + tuple(f'ancora={a}' for a in ANCORAS))


def vetor(span, classe, diag):
    """Vetor de features na ordem de NOMES."""
    trecho = span.get('trecho', '')
    d = digitos(limpa_quebras(trecho))
    n = diag.get('n_feitos', 0)
    v = [1.0]
    v += [1.0 if span['forma'] == f else 0.0 for f in FORMAS]
    v += [1.0 if classe == c else 0.0 for c in CLASSES]
    v += [
        min(n, 3) / 3.0,
        1.0 if n == 0 else 0.0,
        1.0 if n > 1 else 0.0,
        math.log1p(len(d)) / 4.0,
        1.0 if len(d) in (18, 19, 20) else 0.0,
        1.0 if diag.get('pistas') else 0.0,
        1.0 if diag.get('pista_confere') else 0.0,
        min(sum(1 for c in trecho if c.isalpha()
                and any(ch.isdigit() for ch in trecho)), 6) / 6.0,
        1.0 if '\n' in trecho else 0.0,
        math.log1p(len(trecho)) / 5.0,
        1.0 if diag.get('diploma') else 0.0,
        1.0 if span.get('classe_herdada') else 0.0,
    ]
    v += [1.0 if span.get('ancora') == a else 0.0 for a in ANCORAS]
    return v


def sigmoide(x):
    if x < -30:
        return 1e-13
    if x > 30:
        return 1 - 1e-13
    return 1.0 / (1.0 + math.exp(-x))
