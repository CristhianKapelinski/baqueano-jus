# -*- coding: utf-8 -*-
"""Mede a robustez e desenha os graficos do README.

    python figuras.py            # mede tudo e redesenha (leva ~40 s)
    python figuras.py --so-desenhar

As curvas saem de `resultados/robustez.json`, que este script escreve a partir
das medicoes reais. Nenhum ponto e inventado: quem quiser conferir roda de novo
e compara. A serie historica "lista fechada" foi medida no commit c347c60,
antes das ancoras abertas existirem, e por isso vem marcada como tal no JSON -
o codigo atual nao consegue reproduzi-la sem voltar no tempo.
"""
import argparse
import json
import os

LARGURA, ALTURA = 520, 300
MARGEM = {'esq': 58, 'dir': 18, 'topo': 26, 'baixo': 46}
TINTA = '#1F2A44'
CINZA = '#8A97AD'
ACENTO = '#C2410C'
CLARO = '#DCE8F2'


def mede():
    from avaliacao import ablacao
    from avaliacao.metrica import DEV, HOLDOUT
    from avaliacao.ruido import mede as escore
    from cacador.canon import BaseCanonica
    import cacador.extract as ex

    base = BaseCanonica()
    docs = DEV + HOLDOUT
    ruido = [(t, sum(escore(docs, base, t, s) for s in (1, 2, 3)) / 3 if t
              else escore(docs, base, 0, 0))
             for t in (0.0, 0.005, 0.01, 0.02, 0.05, 0.10)]

    abl = [(fracao, sum(es) / len(es))
           for fracao, es in ablacao.curva(base, docs, list(ex.CLASSES))]
    return {'ruido': ruido, 'ablacao_atual': abl}


def eixos(titulo, rot_x, rot_y, xs, ys_min, ys_max):
    """Moldura comum: eixos, marcas e rotulos."""
    x0, y0 = MARGEM['esq'], ALTURA - MARGEM['baixo']
    x1, y1 = LARGURA - MARGEM['dir'], MARGEM['topo']
    p = [f'<rect width="{LARGURA}" height="{ALTURA}" fill="white"/>',
         f'<text x="{MARGEM["esq"]}" y="17" font-size="13" font-weight="600" '
         f'fill="{TINTA}" font-family="sans-serif">{titulo}</text>']
    for k in range(6):
        v = ys_min + (ys_max - ys_min) * k / 5
        y = y0 - (y0 - y1) * k / 5
        p.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" '
                 f'stroke="{CLARO}" stroke-width="1"/>')
        p.append(f'<text x="{x0 - 8}" y="{y + 4:.1f}" font-size="10" fill="{CINZA}" '
                 f'text-anchor="end" font-family="sans-serif">{v * 100:.0f}%</text>')
    for i, xv in enumerate(xs):
        x = x0 + (x1 - x0) * i / max(1, len(xs) - 1)
        p.append(f'<text x="{x:.1f}" y="{y0 + 17}" font-size="10" fill="{CINZA}" '
                 f'text-anchor="middle" font-family="sans-serif">{xv}</text>')
    p.append(f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y0}" stroke="{TINTA}" stroke-width="1.2"/>')
    p.append(f'<text x="{(x0 + x1) / 2:.0f}" y="{ALTURA - 8}" font-size="11" fill="{TINTA}" '
             f'text-anchor="middle" font-family="sans-serif">{rot_x}</text>')
    p.append(f'<text x="14" y="{(y0 + y1) / 2:.0f}" font-size="11" fill="{TINTA}" '
             f'text-anchor="middle" font-family="sans-serif" '
             f'transform="rotate(-90 14 {(y0 + y1) / 2:.0f})">{rot_y}</text>')
    return p, (x0, y0, x1, y1)


def serie(pontos, caixa, ys_min, ys_max, cor, nome, dash=None, rotulo_em=-1):
    x0, y0, x1, y1 = caixa
    n = len(pontos)
    coords = [(x0 + (x1 - x0) * i / max(1, n - 1),
               y0 - (y0 - y1) * (v - ys_min) / (ys_max - ys_min))
              for i, (_, v) in enumerate(pontos)]
    d = ' '.join(f'{"M" if i == 0 else "L"} {x:.1f} {y:.1f}' for i, (x, y) in enumerate(coords))
    tracejado = f' stroke-dasharray="5 4"' if dash else ''
    p = [f'<path d="{d}" fill="none" stroke="{cor}" stroke-width="2.4"{tracejado}/>']
    for x, y in coords:
        p.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{cor}"/>')
    xr, yr = coords[rotulo_em]
    anchor = 'end' if rotulo_em == -1 else 'start'
    dx = -8 if rotulo_em == -1 else 8
    p.append(f'<text x="{xr + dx:.1f}" y="{yr - 9:.1f}" font-size="11" font-weight="600" '
             f'fill="{cor}" text-anchor="{anchor}" font-family="sans-serif">{nome}</text>')
    return p


def desenha(res):
    os.makedirs('docs', exist_ok=True)

    # --- ruido de OCR ---
    r = res['ruido']
    xs = [f'{t*100:.1f}%'.replace('.0%', '%') for t, _ in r]
    p, caixa = eixos('Escore sob ruído de OCR crescente',
                     'caracteres corrompidos', 'escore ponderado', xs, 0.6, 1.0)
    p += serie(r, caixa, 0.6, 1.0, TINTA, 'sistema atual')
    x0, y0, x1, y1 = caixa
    xop = x0 + (x1 - x0) * 2 / (len(r) - 1)  # 1%, a taxa medida
    p.append(f'<line x1="{xop:.1f}" y1="{y1}" x2="{xop:.1f}" y2="{y0}" '
             f'stroke="{ACENTO}" stroke-width="1.2" stroke-dasharray="3 3"/>')
    p.append(f'<text x="{xop + 6:.1f}" y="{y1 + 12}" font-size="10" fill="{ACENTO}" '
             f'font-family="sans-serif">ruído medido no nível 2</text>')
    open('docs/ruido.svg', 'w').write(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{LARGURA}" height="{ALTURA}" '
        f'viewBox="0 0 {LARGURA} {ALTURA}">' + ''.join(p) + '</svg>')

    # --- ablacao de vocabulario ---
    a = res['ablacao_atual']
    hist = res.get('ablacao_lista_fechada')
    xs = [f'{f*100:.0f}%' for f, _ in a]
    p, caixa = eixos('Escore removendo o vocabulário escrito à mão',
                     'entradas de classe removidas', 'escore ponderado', xs, 0.75, 1.0)
    if hist:
        p += serie(hist, caixa, 0.75, 1.0, CINZA, 'só lista fechada', dash=True, rotulo_em=2)
    p += serie(a, caixa, 0.75, 1.0, TINTA, 'com âncora aberta')
    open('docs/ablacao.svg', 'w').write(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{LARGURA}" height="{ALTURA}" '
        f'viewBox="0 0 {LARGURA} {ALTURA}">' + ''.join(p) + '</svg>')
    print('docs/ruido.svg e docs/ablacao.svg escritos')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--so-desenhar', action='store_true')
    a = ap.parse_args()
    caminho = 'resultados/robustez.json'
    if a.so_desenhar:
        res = json.load(open(caminho))
    else:
        res = mede()
        # serie historica: medida no commit c347c60, antes das ancoras abertas.
        # Fica marcada porque o codigo atual nao a reproduz.
        res['ablacao_lista_fechada'] = [[0.0, 0.967], [0.10, 0.949], [0.20, 0.916],
                                        [0.30, 0.896], [0.50, 0.810]]
        res['_procedencia'] = {
            'ruido': 'stress.py, 3 sementes por ponto, medido agora',
            'ablacao_atual': 'ablacao.py, 5 sementes por ponto, medido agora',
            'ablacao_lista_fechada': 'medido no commit c347c60, antes das ancoras abertas',
        }
        os.makedirs('resultados', exist_ok=True)
        json.dump(res, open(caminho, 'w'), indent=1)
        print(f'{caminho} escrito')
    desenha(res)
