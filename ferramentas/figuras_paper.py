# -*- coding: utf-8 -*-
"""Figuras do artigo que saem de medicao propria.

    python -m ferramentas.figuras_paper

Duas figuras, ambas a partir de dado medido e nao de valor digitado a mao:

* posicoes.svg - onde fica, dentro de um acordao, o numero do PROPRIO feito e
  onde ficam os numeros que ele apenas CITA. E a evidencia da heuristica de
  posicao usada pelo resolvedor.
* bootstrap.svg - distribuicao da vantagem da melhor estrategia de confianca
  ajustada sobre uma constante, reamostrando documentos. E a evidencia de que a
  diferenca nao se separa do ruido.
"""
import collections
import math
import os
import re

import numpy as np

TINTA, CINZA, ACENTO, CLARO = '#1F2A44', '#8A97AD', '#C2410C', '#DCE8F2'
L, A = 560, 300
M = {'esq': 62, 'dir': 20, 'topo': 28, 'baixo': 48}


def _moldura(titulo, rx, ry):
    x0, y0, x1, y1 = M['esq'], A - M['baixo'], L - M['dir'], M['topo']
    p = [f'<rect width="{L}" height="{A}" fill="white"/>',
         f'<text x="{M["esq"]}" y="18" font-size="13" font-weight="600" fill="{TINTA}" '
         f'font-family="sans-serif">{titulo}</text>',
         f'<text x="{(x0+x1)/2:.0f}" y="{A-8}" font-size="11" fill="{TINTA}" '
         f'text-anchor="middle" font-family="sans-serif">{rx}</text>',
         f'<text x="13" y="{(y0+y1)/2:.0f}" font-size="11" fill="{TINTA}" '
         f'text-anchor="middle" font-family="sans-serif" '
         f'transform="rotate(-90 13 {(y0+y1)/2:.0f})">{ry}</text>']
    return p, (x0, y0, x1, y1)


def _salva(nome, partes):
    os.makedirs('docs', exist_ok=True)
    open(f'docs/{nome}.svg', 'w').write(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{L}" height="{A}" '
        f'viewBox="0 0 {L} {A}">' + ''.join(partes) + '</svg>')
    print(f'docs/{nome}.svg')


def posicoes(dados):
    """ECDF em escala log: quao cedo o numero aparece, proprio contra citado."""
    p, (x0, y0, x1, y1) = _moldura(
        'Onde o número aparece dentro do acórdão',
        'posição da primeira ocorrência, em caracteres (escala log)',
        'fração acumulada')
    lo, hi = 1.0, 5.0                                   # 10^0 a 10^5
    px = lambda v: x0 + (x1 - x0) * (math.log10(max(v, 10)) - lo) / (hi - lo)
    for k in range(6):
        v = y0 - (y0 - y1) * k / 5
        p.append(f'<line x1="{x0}" y1="{v:.1f}" x2="{x1}" y2="{v:.1f}" stroke="{CLARO}"/>')
        p.append(f'<text x="{x0-8}" y="{v+4:.1f}" font-size="10" fill="{CINZA}" '
                 f'text-anchor="end" font-family="sans-serif">{k*20}%</text>')
    for e in range(1, 6):
        x = x0 + (x1 - x0) * (e - lo) / (hi - lo)
        p.append(f'<text x="{x:.1f}" y="{y0+17}" font-size="10" fill="{CINZA}" '
                 f'text-anchor="middle" font-family="sans-serif">10^{e}</text>')
    p.append(f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y0}" stroke="{TINTA}" stroke-width="1.2"/>')
    for chave, cor, rotulo, dash in (('proprio', TINTA, 'número do próprio feito', ''),
                                     ('citado', ACENTO, 'número apenas citado', ' stroke-dasharray="5 4"')):
        vs = sorted(v for lista in dados[chave].values() for v in lista)
        pts = [(px(v), y0 - (y0 - y1) * (i + 1) / len(vs)) for i, v in enumerate(vs)]
        pts = pts[::max(1, len(pts) // 300)]
        d = ' '.join(f'{"M" if i==0 else "L"} {x:.1f} {y:.1f}' for i, (x, y) in enumerate(pts))
        p.append(f'<path d="{d}" fill="none" stroke="{cor}" stroke-width="2.4"{dash}/>')
        alvo = int(len(pts) * (0.45 if chave == 'proprio' else 0.62))
        xr, yr = pts[alvo]
        anc = 'start' if chave == 'proprio' else 'end'
        dx = 8 if chave == 'proprio' else -8
        p.append(f'<text x="{xr+dx:.1f}" y="{yr-9:.1f}" font-size="11" font-weight="600" '
                 f'fill="{cor}" text-anchor="{anc}" '
                 f'font-family="sans-serif">{rotulo} (n={len(vs)})</text>')
    _salva('posicoes', p)


def bootstrap(dados):
    """Histograma da vantagem sobre a constante, com o zero marcado."""
    difs = np.array(dados['difs'])
    p, (x0, y0, x1, y1) = _moldura(
        'Vantagem da melhor confiança ajustada sobre uma constante',
        'diferença de Brier por reamostragem de documentos', 'reamostras')
    lo, hi = float(difs.min()), float(difs.max())
    n, bordas = np.histogram(difs, bins=42, range=(lo, hi))
    px = lambda v: x0 + (x1 - x0) * (v - lo) / (hi - lo)
    for i, c in enumerate(n):
        h = (y0 - y1) * c / n.max()
        xa, xb = px(bordas[i]), px(bordas[i + 1])
        cor = CLARO if bordas[i] < 0 else '#F6D9CE'
        p.append(f'<rect x="{xa:.1f}" y="{y0-h:.1f}" width="{max(1,xb-xa-0.6):.1f}" '
                 f'height="{h:.1f}" fill="{cor}" stroke="{CINZA}" stroke-width="0.4"/>')
    xz = px(0.0)
    p.append(f'<line x1="{xz:.1f}" y1="{y1}" x2="{xz:.1f}" y2="{y0}" stroke="{TINTA}" '
             f'stroke-width="1.6"/>')
    p.append(f'<text x="{xz+6:.1f}" y="{y0-8:.1f}" font-size="10" fill="{TINTA}" '
             f'font-family="sans-serif">zero</text>')
    for v, txt in ((dados['lo'], 'IC 2,5%'), (dados['hi'], 'IC 97,5%')):
        p.append(f'<line x1="{px(v):.1f}" y1="{y1+30}" x2="{px(v):.1f}" y2="{y0}" '
                 f'stroke="{ACENTO}" stroke-width="1.1" stroke-dasharray="3 3"/>')
        p.append(f'<text x="{px(v):.1f}" y="{y1+42}" font-size="9.5" fill="{ACENTO}" '
                 f'text-anchor="middle" font-family="sans-serif">{txt}</text>')
    for k in range(5):
        v = y0 - (y0 - y1) * k / 4
        p.append(f'<text x="{x0-8}" y="{v+4:.1f}" font-size="10" fill="{CINZA}" '
                 f'text-anchor="end" font-family="sans-serif">{int(n.max()*k/4)}</text>')
    p.append(f'<text x="{x0+14}" y="{y1+16}" font-size="10.5" font-weight="600" '
             f'fill="{TINTA}" font-family="sans-serif">a constante vence em '
             f'{(1-dados["vitorias"])*100:.0f}% das reamostras</text>')
    p.append(f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y0}" stroke="{TINTA}" stroke-width="1.2"/>')
    _salva('bootstrap', p)


if __name__ == '__main__':
    # As duas figuras saem de medicao feita agora, na base que esta no disco:
    # ler dado gravado antes arriscaria publicar figura de uma rodada anterior.
    from avaliacao.acervo import posicoes_por_tribunal
    from baqueano.canon import BaseCanonica
    from ferramentas.confianca import dados_bootstrap

    base = BaseCanonica()
    posicoes(posicoes_por_tribunal(base))
    bootstrap(dados_bootstrap(base))
