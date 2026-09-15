# -*- coding: utf-8 -*-
"""Gerado por escolhe_confianca.py - NAO editar a mao.

Nenhuma estrategia ajustada superou uma constante COM FOLGA neste
conjunto. Isso nao diz que nao existe sinal: diz que 228 predicoes
com 5 erros nao tem resolucao para separar uma vantagem de
milesimo do ruido de amostragem. Ate haver mais dado real
rotulado, a constante e a escolha defensavel. Emitimos a acuracia
medida com uma margem para baixo, porque errar por excesso de
confianca custa mais no Brier do que errar por falta.
"""

MODO = "constante"
CONSTANTE = 1.0
# acuracia medida no goldenset: 1.0000; margem aplicada: 0.0
PESOS = None
