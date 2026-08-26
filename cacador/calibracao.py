# -*- coding: utf-8 -*-
"""Gerado por escolhe_confianca.py - NAO editar a mao.

Nenhum modelo bateu uma constante no dado real: com poucos erros
no goldenset nao ha sinal para ajustar nada mais fino. Emitimos a
acuracia medida, com uma margem para baixo - errar por excesso de
confianca custa mais no Brier do que errar por falta.
"""

MODO = "constante"
CONSTANTE = 0.9593
# acuracia medida no goldenset: 0.9693; margem aplicada: 0.01
PESOS = None
