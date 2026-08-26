# -*- coding: utf-8 -*-
"""Da citacao extraida para (classe, id_canonico), pela tabela do enunciado.

    exatamente 1 feito  -> real       (id_canonico = id de qualquer registro)
    0 feitos            -> inventada  (resolucao nula)
    2+ feitos distintos -> incompleta (sem criterio de desempate)
    sem identificador   -> incompleta (nem chega a consultar a base)
"""
import re

from .canon import codigo_do_diploma
from .normalize import cadeias_de_digitos, texto_canonico

# Classe processual -> tribunal. So entram as classes privativas de um tribunal;
# HC, ED, AgR e afins sao ambiguos de proposito e nao filtram nada.
CLASSE_TRIBUNAL = [
    (r'respe|arespei|recurso especial eleitoral', 'TSE'),
    (r'\btst\b|airr|\barr\b|\brr\b|agarr|recurso de revista', 'TST'),
    (r'aresp|eresp|\bresp\b|r esp|rec esp|recurso especial|agravo em recurso especial|rms',
     'STJ'),
    (r'\bare\b|\bre\b|\brcl\b|reclamacao|adpf|\badi\b|\badc\b', 'STF'),
    (r'\brse\b|\bapl\b|apelacao|recurso em sentido estrito', 'STM'),
]
# Segmento J do numero CNJ (NNNNNNN-DD.AAAA.J.TR.OOOO): o ramo da Justica.
CNJ_RAMO = {'1': 'STF', '3': 'STJ', '5': 'TST', '6': 'TSE', '7': 'STM'}


def _tribunais_da_classe(trecho):
    c = texto_canonico(trecho)
    # 'AgR-REspe' contem 'resp': o mais especifico vence, entao TSE/TST primeiro.
    for rx, trib in CLASSE_TRIBUNAL:
        if re.search(rx, c):
            return {trib}
    return set()


def _tribunais_do_cnj(cadeias):
    out = set()
    for d in cadeias:
        if len(d) == 20:
            t = CNJ_RAMO.get(d[13])
            if t:
                out.add(t)
        elif 14 <= len(d) < 20:
            t = CNJ_RAMO.get(d.rjust(20, '0')[13])
            if t:
                out.add(t)
    return out


def _tribunal_explicito(trecho):
    m = re.search(r'\b(STF|STJ|TSE|TST|STM)\b', trecho.upper())
    return {m.group(1)} if m else set()


def classifica(span, base):
    """Devolve (classe, id_canonico|None, confianca)."""
    forma = span['forma']

    if forma == 'sumula':
        regs = base.sumula(span['numero'], span.get('tribunal'),
                           span.get('vinculante', False))
        if len(regs) == 1:
            return 'real', str(regs[0]['id']), 0.95
        if not regs:
            return 'inventada', None, 0.90
        return 'incompleta', None, 0.60

    if forma == 'artigo':
        artigo = str(span['artigo']).rstrip('º°o').strip()
        if artigo.lower() == 'correspondente':
            return 'incompleta', None, 0.85
        codigo = codigo_do_diploma(span['diploma_txt'])
        if codigo is None:
            return 'incompleta', None, 0.70
        regs = base.dispositivo(codigo, artigo)
        if len(regs) == 1:
            return 'real', str(regs[0]['id']), 0.92
        return 'inventada', None, 0.85

    if forma == 'numerada':
        cadeias = cadeias_de_digitos(span['trecho'])
        if not cadeias:
            return 'incompleta', None, 0.60
        pistas = (_tribunais_da_classe(span['trecho'])
                  | _tribunais_do_cnj(cadeias)
                  | _tribunal_explicito(span['trecho']))
        feitos = base.feitos_por_numero(cadeias, pistas) if pistas else []
        if not feitos:
            # a pista de tribunal pode estar errada; tenta sem ela antes de
            # declarar inexistente
            feitos = base.feitos_por_numero(cadeias)
        if len(feitos) == 1:
            return 'real', str(feitos[0].registros[0]['id']), 0.90
        if not feitos:
            return 'inventada', None, 0.85
        return 'incompleta', None, 0.55

    # referencias vagas
    return 'incompleta', None, 0.80
