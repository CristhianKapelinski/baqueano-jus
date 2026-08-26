# -*- coding: utf-8 -*-
"""Normalizacao de identificadores processuais.

Duas garantias do enunciado guiam este modulo:

* o ruido do nivel 2 nunca troca um digito por outro digito, logo toda
  citacao `real` ruidosa e recuperavel por normalizacao;
* o tokenizador do FTS quebra em nao-alfanumerico, entao a forma canonica de
  um numero e a sequencia de digitos, nao a string com pontuacao.
"""
import re
import unicodedata

# Letras que o ruido de OCR troca por digito. So se aplicam quando a letra esta
# GRUDADA em digito - dentro do identificador -, nunca em palavra corrida.
OCR_LETRA_DIGITO = {
    'O': '0', 'o': '0', 'D': '0', 'Q': '0',
    'l': '1', 'I': '1', 'i': '1', '|': '1',
    'Z': '2', 'z': '2',
    'E': '3',
    'A': '4',
    'S': '5', 's': '5',
    'G': '6', 'b': '6',
    'T': '7',
    'B': '8',
    'g': '9', 'q': '9',
}

# Ruido de OCR que NAO envolve digito. O enunciado lista apenas m <-> rn; nao
# invente outros: 'cl' -> 'd', por exemplo, destroi 'CLT'.
OCR_LETRA_LETRA = [('rn', 'm')]

_NAO_DIGITO = re.compile(r'\D')


def digitos(s):
    """So os digitos de `s`."""
    return _NAO_DIGITO.sub('', s)


def sem_acento(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s)
                   if not unicodedata.combining(c))


def limpa_quebras(s):
    """Junta quebras de linha e espacos duros dentro de um identificador.

    O gabarito guarda a quebra como `\\n` literal; o texto tem `\\n` de verdade.
    Os dois viram espaco simples.
    """
    s = s.replace('\\n', ' ').replace('\n', ' ').replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', s).strip()


def texto_canonico(s):
    """Minusculo, sem acento, sem pontuacao, espaco unico. Para casar diplomas.

    A correcao de OCR NAO entra aqui: aplicada as cegas ela quebra palavras
    legitimas ('rn' -> 'm' estraga 'governo'). Quem precisa dela chama
    `com_correcao_ocr` como segunda tentativa.
    """
    s = sem_acento(limpa_quebras(s)).lower()
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return s.strip()


def texto_canonico_leve(s):
    """Como `texto_canonico`, mas preserva ponto e barra.

    Numero de lei ('13.105/2015') perde a identidade se a pontuacao sumir.
    """
    s = sem_acento(limpa_quebras(s)).lower()
    s = re.sub(r'[^a-z0-9./]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def com_correcao_ocr(s):
    for errado, certo in OCR_LETRA_LETRA:
        s = s.replace(errado, certo)
    return s


def _posicoes_ambiguas(t):
    """Indices de letras que estao coladas em digito - candidatas a ruido OCR."""
    return [i for i, ch in enumerate(t)
            if ch in OCR_LETRA_DIGITO
            and ((i > 0 and t[i - 1].isdigit())
                 or (i + 1 < len(t) and t[i + 1].isdigit()))]


_CADEIA = re.compile(r'\d[\d.\s\-/]*\d|\d')


def cadeias_de_digitos(trecho, max_ambiguas=10, limite=256):
    """Todas as leituras plausiveis de `trecho` como sequencia de digitos.

    Expande as ambiguidades de OCR letra<->digito e devolve o conjunto de
    cadeias de digitos encontradas em qualquer das leituras.
    """
    t = limpa_quebras(trecho)
    amb = _posicoes_ambiguas(t)[:max_ambiguas]
    saida = set()
    for mask in range(1 << len(amb)):
        s = list(t)
        for k, i in enumerate(amb):
            if mask >> k & 1:
                s[i] = OCR_LETRA_DIGITO[t[i]]
        cand = ''.join(s)
        for m in _CADEIA.finditer(cand):
            d = digitos(m.group())
            if 2 <= len(d) <= 20:
                saida.add(d)
        if len(saida) >= limite:
            break
    return saida


def variantes_cnj(d):
    """Formas equivalentes de um numero CNJ escrito sem os zeros a esquerda.

    O CNJ tem 20 digitos (NNNNNNN-DD.AAAA.J.TR.OOOO). Quando o documento
    suprime zeros do sequencial, a cadeia vem com menos de 20; padronizar para
    20 casa as duas escritas do mesmo feito.
    """
    out = {d}
    if 14 <= len(d) < 20:
        out.add(d.rjust(20, '0'))
    if len(d) == 20:
        out.add(d.lstrip('0') or d)
    return out
