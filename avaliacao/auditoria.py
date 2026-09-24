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

from baqueano.canon import BaseCanonica
from baqueano.classify import classifica
from baqueano.extract import extrai
from baqueano.normalize import digitos

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


def leituras_no_acervo(con, alvo):
    """Posicao da primeira ocorrencia e numero de ocorrencias, por documento.

    O FTS estreita os candidatos; as duas medidas saem de uma varredura propria.
    Nao ha chamada ao parser de cabecalho em lugar nenhum daqui.
    """
    sem_zero = alvo.lstrip('0')
    achados, contagem = {}, {}
    for frase in _frases(alvo):
        linhas = con.execute(
            "SELECT d.documento_id, d.texto FROM documentos_fts "
            "JOIN documentos d ON d.rowid = documentos_fts.rowid "
            "WHERE documentos_fts MATCH ? AND d.natureza='acordao'",
            (f'"{frase}"',)).fetchall()
        for did, texto in linhas:
            if did in achados:
                continue
            posicoes = [m.start() for m in NUM.finditer(texto)
                        if digitos(m.group()) in (alvo, sem_zero)
                        or digitos(m.group()).lstrip('0') == sem_zero]
            if posicoes:
                achados[did], contagem[did] = posicoes[0], len(posicoes)
    return achados, contagem


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--amostra', type=int, default=60,
                    help='quantas citacoes auditar (a varredura e cara)')
    ap.add_argument('--semente', type=int, default=3)
    ap.add_argument('--fontes', type=int, default=150,
                    help='quantos acordaos varrer atras de citacoes')
    a = ap.parse_args()
    base = BaseCanonica()
    linhas = base.con.execute(
        "SELECT documento_id, id, tribunal, texto FROM documentos "
        "WHERE natureza='acordao'").fetchall()
    doc_por_id = {l[1]: l[0] for l in linhas}
    trib_por_doc = {l[0]: l[2] for l in linhas}

    # colhe citacoes reais do corpo dos acordaos (amostra das fontes primeiro:
    # varrer os 1.000 inteiros custa minutos e nao muda a conclusao)
    rng0 = random.Random(a.semente)
    fontes = rng0.sample(linhas, min(a.fontes, len(linhas)))
    casos = []
    for did, i, trib, texto in fontes:
        for s in extrai(texto):
            if s['forma'] != 'numerada':
                continue
            classe, idc, _ = classifica(s, base)
            if classe != 'real' or not idc:
                continue
            d = digitos(s['trecho'].replace('\n', ' '))
            alvo = doc_por_id.get(int(idc))
            if len(d) < 5 or alvo == did:
                continue
            casos.append((did, d, int(idc), trib_por_doc.get(alvo, '?')))

    # amostra ESTRATIFICADA por tribunal: aleatoria concentra STF e STJ e deixa
    # o TST e o STM, onde o oraculo de posicao e fraco, sem caso nenhum.
    rng = random.Random(a.semente)
    por_trib = collections.defaultdict(list)
    for c in casos:
        por_trib[c[3]].append(c)
    cota = max(1, a.amostra // max(1, len(por_trib)))
    casos = []
    for trib in sorted(por_trib):
        grupo = por_trib[trib]
        rng.shuffle(grupo)
        casos.extend(grupo[:cota])
    rng.shuffle(casos)

    por_trib = collections.defaultdict(lambda: collections.Counter())
    exemplos = []
    for citante, d, idc, trib in casos:
        pos, freq = leituras_no_acervo(base.con, d)
        pos.pop(citante, None); freq.pop(citante, None)
        c = por_trib[trib]
        if not pos:
            c['sem_dado'] += 1
            continue
        resolvido = doc_por_id.get(idc)
        # empate = dois registros do MESMO feito. O enunciado diz que acertar
        # qualquer id do conjunto conta como acerto pleno, entao empate e
        # concordancia, nao divergencia.
        vence_pos = {k for k, v in pos.items() if v == min(pos.values())}
        vence_freq = {k for k, v in freq.items() if v == max(freq.values())}
        c['total'] += 1
        c['posicao'] += resolvido in vence_pos
        c['frequencia'] += resolvido in vence_freq
        divergiu = (trib, d, resolvido, pos.get(resolvido), freq.get(resolvido),
                    sorted(vence_pos)[:1], sorted(vence_freq)[:1])
        if (resolvido not in vence_pos or resolvido not in vence_freq) \
                and divergiu not in exemplos and len(exemplos) < 10:
            exemplos.append(divergiu)
    print(f'{"tribunal":9s} {"n":>4s} {"posicao":>10s} {"frequencia":>12s}')
    tot = collections.Counter()
    for trib in sorted(por_trib):
        c = por_trib[trib]; tot.update(c)
        if not c['total']:
            print(f'{trib:9s} {0:>4d}  (nenhuma citacao resolvivel amostrada)'); continue
        print(f'{trib:9s} {c["total"]:>4d} {c["posicao"]/c["total"]:>9.0%} '
              f'{c["frequencia"]/c["total"]:>11.0%}')
    if tot['total']:
        print(f'{"TOTAL":9s} {tot["total"]:>4d} {tot["posicao"]/tot["total"]:>9.0%} '
              f'{tot["frequencia"]/tot["total"]:>11.0%}')
    for e in exemplos:
        print(f'   [{e[0]}] numero {e[1]}: resolvedor -> {e[2]} '
              f'(posicao {e[3]}, {e[4]} ocorrencias); '
              f'posicao aponta {e[5]}, frequencia aponta {e[6]}')


if __name__ == '__main__':
    main()
