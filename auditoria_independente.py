# -*- coding: utf-8 -*-
"""Segunda leitura, independente do parser de cabecalho.

A auditoria embutida em avalia_acervo.py e CIRCULAR: ela confere o link
chamando o mesmo `PARSERS` que constroi o indice. Se o parser le um cabecalho
errado, auditor e resolvedor erram igual e o teste reporta acerto - valida
consistencia, nao correcao.

Aqui o criterio nao passa pelo parser. Dado um numero citado, varre-se o acervo
inteiro atras de TODOS os documentos que o contem e mede-se a POSICAO da
primeira ocorrencia em cada um. O documento que E o processo carrega o numero
mais cedo (cabecalho ou linha de autuacao); os que apenas CITAM o trazem no
corpo. O registro certo, portanto, e o de menor posicao - e isso e um algoritmo
diferente, nao uma reexecucao do mesmo.
"""
import argparse
import collections
import random
import re

from cacador.canon import BaseCanonica
from cacador.classify import classifica
from cacador.extract import extrai
from cacador.normalize import digitos

NUM = re.compile(r'\d[\d.\s–-]{4,30}\d')
E_LEI = re.compile(r'(?:lei|decreto|s[úu]mula|art(?:igo)?s?\.?|R\$)\s*'
                   r'(?:complementar\s*)?n?[.ºo°]{0,2}\s*$', re.I)


def _frases(d):
    """O numero como sequencia de tokens, para a busca por frase no FTS."""
    saida = []
    if 14 <= len(d) <= 20:
        p = d.rjust(20, '0')
        saida.append(f'{p[:7]} {p[7:9]} {p[9:13]} {p[13]} {p[14:16]} {p[16:]}')
        q = p.lstrip('0')
        if len(q) >= 13:
            saida.append(f'{q[:-13]} {q[-13:-11]} {q[-11:-7]} {q[-7]} {q[-6:-4]} {q[-4:]}')
    else:
        g, r = [], d
        while len(r) > 3:
            g.insert(0, r[-3:]); r = r[:-3]
        g.insert(0, r)
        saida.append(' '.join(g))
    return list(dict.fromkeys(saida))


def posicoes_no_acervo(con, alvo):
    """Posicao da primeira ocorrencia do numero, em cada documento que o contem.

    O FTS estreita os candidatos; a posicao e medida no texto, com uma varredura
    propria - nao ha chamada ao parser de cabecalho em lugar nenhum daqui.
    """
    sem_zero = alvo.lstrip('0')
    achados = {}
    for frase in _frases(alvo):
        linhas = con.execute(
            "SELECT d.documento_id, d.texto FROM documentos_fts "
            "JOIN documentos d ON d.rowid = documentos_fts.rowid "
            "WHERE documentos_fts MATCH ? AND d.natureza='acordao'",
            (f'"{frase}"',)).fetchall()
        for did, texto in linhas:
            if did in achados:
                continue
            for m in NUM.finditer(texto):
                d = digitos(m.group())
                if d == alvo or d == sem_zero or d.lstrip('0') == sem_zero:
                    achados[did] = m.start()
                    break
    return achados


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--amostra', type=int, default=60,
                    help='quantas citacoes auditar (a varredura e cara)')
    ap.add_argument('--semente', type=int, default=3)
    a = ap.parse_args()
    base = BaseCanonica()
    linhas = base.con.execute(
        "SELECT documento_id, id, tribunal, texto FROM documentos "
        "WHERE natureza='acordao'").fetchall()
    textos = {l[0]: (l[2], l[3]) for l in linhas}
    id_por_doc = {l[0]: l[1] for l in linhas}
    doc_por_id = {l[1]: l[0] for l in linhas}

    # colhe citacoes reais do corpo dos acordaos
    casos = []
    for did, i, trib, texto in linhas:
        for s in extrai(texto):
            if s['forma'] != 'numerada':
                continue
            classe, idc, _, _ = classifica(s, base)
            if classe != 'real' or not idc:
                continue
            d = digitos(s['trecho'].replace('\n', ' '))
            if len(d) < 5 or doc_por_id.get(int(idc)) == did:
                continue
            casos.append((did, d, int(idc)))
    rng = random.Random(a.semente)
    rng.shuffle(casos)
    casos = casos[:a.amostra]

    concorda = discorda = sem_dado = 0
    exemplos = []
    for citante, d, idc in casos:
        pos = posicoes_no_acervo(base.con, d)
        pos.pop(citante, None)
        if not pos:
            sem_dado += 1
            continue
        vencedor = min(pos, key=pos.get)
        resolvido = doc_por_id.get(idc)
        if vencedor == resolvido:
            concorda += 1
        else:
            discorda += 1
            if len(exemplos) < 8:
                exemplos.append((d, resolvido, pos.get(resolvido), vencedor, pos[vencedor]))
    total = concorda + discorda
    print(f'citacoes auditadas: {total} (mais {sem_dado} sem outra ocorrencia no acervo)')
    if total:
        print(f'a segunda leitura CONCORDA com o resolvedor: {concorda} '
              f'({concorda/total:.1%})')
        print(f'discorda: {discorda}')
    for e in exemplos:
        print(f'   numero {e[0]}: resolvedor -> {e[1]} (posicao {e[2]}), '
              f'segunda leitura -> {e[3]} (posicao {e[4]})')


if __name__ == '__main__':
    main()
