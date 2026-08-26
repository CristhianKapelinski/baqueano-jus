# -*- coding: utf-8 -*-
"""Gerado por calibra.py - NAO editar a mao."""

# (forma de extracao, classe) -> confianca empirica suavizada
CONFIANCA = {
    ('artigo', 'incompleta'): 0.7500,  # 2/2
    ('artigo', 'inventada'): 0.9375,  # 14/14
    ('artigo', 'real'): 0.8750,  # 13/14
    ('numerada', 'inventada'): 0.9778,  # 43/43
    ('numerada', 'real'): 0.9494,  # 74/77
    ('sumula', 'inventada'): 0.8889,  # 7/7
    ('sumula', 'real'): 0.8571,  # 5/5
    ('vaga_anaforica', 'incompleta'): 0.8824,  # 29/32
    ('vaga_classe_ano_rel', 'incompleta'): 0.9286,  # 12/12
    ('vaga_trib_ano_rel', 'incompleta'): 0.9545,  # 20/20
}
PADRAO = 0.5
