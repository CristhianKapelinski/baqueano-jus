# -*- coding: utf-8 -*-
"""Da citacao extraida para (classe, id_canonico), pela tabela do enunciado.

    exatamente 1 feito  -> real       (id_canonico = o registro canonico do feito)
    0 feitos            -> inventada  (resolucao nula)
    2+ feitos distintos -> incompleta (sem criterio de desempate)
    sem identificador   -> incompleta (nem chega a consultar a base)
"""
import re

from .canon import codigo_do_diploma, normaliza_artigo
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

# Um diploma com nome proprio e buscavel, ainda que fora da cobertura.
DIPLOMA_NOMEADO = re.compile(
    r'\b(codigo|lei|leis|estatuto|consolidacao|constituicao|decreto|'
    r'regimento|convencao|conven[çc][ãa]o|emenda|medida provisoria|'
    r'ato das disposicoes)\b')


def _tribunais_da_classe(trecho):
    c = texto_canonico(trecho)
    # 'AgR-REspe' contem 'resp': o mais especifico vence, entao TSE/TST primeiro.
    for rx, trib in CLASSE_TRIBUNAL:
        if re.search(rx, c):
            return {trib}
    return set()


def _tribunais_do_cnj(cadeias):
    """Tribunal pelo segmento J de cada cadeia que tenha forma de CNJ."""
    ramos = (CNJ_RAMO.get(d.rjust(20, '0')[13]) for d in cadeias if 14 <= len(d) <= 20)
    return {t for t in ramos if t}


def _tribunal_explicito(trecho):
    m = re.search(r'\b(STF|STJ|TSE|TST|STM)\b', trecho.upper())
    return {m.group(1)} if m else set()


def _melhor_registro(registros, contexto):
    """Entre registros do mesmo feito, escolhe o que casa a classe processual.

    Um mesmo numero de processo pode indexar o recurso especial e os embargos
    de divergencia opostos nele. A citacao diz qual dos dois e; o cabecalho do
    registro tambem. Sem esse desempate a escolha vira ordem de identificador,
    que acerta por acaso.
    """
    if len(registros) == 1:
        return registros[0]
    alvo = texto_canonico(contexto)
    melhor, pontos = registros[0], -1
    for r in registros:
        p = sum(len(c) for c in r.get('classes', ()) if c in alvo)
        if p > pontos:
            melhor, pontos = r, p
    return melhor


def classifica(span, base):
    """Devolve (classe, id_canonico|None, diagnostico).

    O diagnostico diz como a decisao foi tomada: quantos feitos casaram, se havia
    pista de tribunal e se ela confirmou, e se o diploma foi reconhecido. A
    ferramenta de calibracao le isso; a solucao nao.
    """
    forma = span['forma']
    diag = {}

    if forma == 'sumula':
        regs = base.sumula(span['numero'], span.get('tribunal'),
                           span.get('vinculante', False))
        diag['n_feitos'] = len(regs)
        if len(regs) == 1:
            return 'real', str(regs[0]['id']), diag
        if not regs:
            return 'inventada', None, diag
        return 'incompleta', None, diag

    if forma == 'artigo':
        artigo = normaliza_artigo(span['artigo'])
        codigo = codigo_do_diploma(span['diploma_txt'])
        if codigo is None:
            # o diploma tem nome proprio ('Codigo de Transito Brasileiro',
            # 'Estatuto do Idoso'): da para buscar, e nao esta na cobertura -
            # logo 'inventada'. So e 'incompleta' quando nada foi nomeado.
            if DIPLOMA_NOMEADO.search(texto_canonico(span['diploma_txt'])):
                return 'inventada', None, diag
            return 'incompleta', None, diag
        diag['diploma'] = codigo
        regs = base.dispositivo(codigo, artigo)
        diag['n_feitos'] = len(regs)
        if len(regs) == 1:
            return 'real', str(regs[0]['id']), diag
        return 'inventada', None, diag

    if forma == 'numerada':
        # numero herdado de uma enumeracao carrega a classe do primeiro item
        contexto = span['trecho'] + ' ' + span.get('classe_herdada', '')
        cadeias = cadeias_de_digitos(span['trecho'])
        if not cadeias:
            return 'incompleta', None, diag
        pistas = (_tribunais_da_classe(contexto)
                  | _tribunais_do_cnj(cadeias)
                  | _tribunal_explicito(contexto))
        diag['pistas'] = sorted(pistas)
        feitos = base.feitos_por_numero(cadeias, pistas) if pistas else []
        diag['pista_confere'] = bool(feitos)
        if not feitos:
            # a pista de tribunal pode estar errada; tenta sem ela antes de
            # declarar inexistente
            feitos = base.feitos_por_numero(cadeias)
        if not feitos:
            # rede de seguranca: o indice vem de um parser de cabecalho, e um
            # cabecalho lido errado transformaria uma `real` em `inventada`
            feitos = base.feitos_por_fts(cadeias, pistas)
            diag['por_fts'] = bool(feitos)
        diag['n_feitos'] = len(feitos)
        if len(feitos) == 1:
            reg = _melhor_registro(feitos[0].registros, contexto)
            diag['n_registros'] = len(feitos[0].registros)
            return 'real', str(reg['id']), diag
        if not feitos:
            return 'inventada', None, diag
        return 'incompleta', None, diag

    # referencias vagas
    return 'incompleta', None, diag
