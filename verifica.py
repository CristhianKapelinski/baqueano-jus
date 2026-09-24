# -*- coding: utf-8 -*-
"""Roda a bateria inteira de avaliacao e imprime um placar unico.

    python verifica.py [--rapido]

Sao cinco superficies independentes. Nenhuma delas sozinha diz se a solucao vai
bem no conjunto cego; juntas, cercam o problema por todos os lados que ele tem.
"""
import argparse
import subprocess
import sys
import time

def modulo(nome, *args):
    return [sys.executable, '-m', nome, *args]


SUITES = [
    ('goldenset (26 documentos distribuidos)',
     modulo('avaliacao.metrica', '--conjunto', 'tudo'), False),
    ('acervo real (citacoes dentro do acervo)',
     modulo('avaliacao.acervo', '--amostra', '0'), True),
    ('auditoria independente do link (sem o leitor de cabecalho)',
     modulo('avaliacao.auditoria', '--fontes', '120', '--amostra', '80'), True),
    ('sintetico proprio, semente inedita',
     modulo('avaliacao.sintetico', '--dir', 'sintetico'), False),
    ('robustez a ruido de OCR', modulo('avaliacao.ruido'), True),
    ('ablacao do vocabulario de classe', modulo('avaliacao.ablacao'), True),
]


def garante_sintetico():
    """O corpus sintetico nao vai no repositorio (e derivado); gera se faltar."""
    from pathlib import Path
    for pasta, n, semente, ruido in (('sintetico', 200, 20260828, 0.006),
                                     ('sintetico_dificil', 150, 777, 0.035)):
        if (Path(pasta) / 'goldenset.csv').exists():
            continue
        print(f'    (gerando {pasta}/ - nao existia)')
        subprocess.run([sys.executable, '-m', 'ferramentas.gerador', '--n', str(n),
                        '--semente', str(semente), '--ruido', str(ruido),
                        '--saida', pasta], check=True, capture_output=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rapido', action='store_true',
                    help='pula as suites lentas (acervo, ruido, ablacao)')
    a = ap.parse_args()
    garante_sintetico()
    falhou = False
    for nome, cmd, lenta in SUITES:
        if a.rapido and lenta:
            print(f'\n### {nome}\n    (pulada com --rapido)')
            continue
        print(f'\n### {nome}')
        t0 = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            falhou = True
            print('    FALHOU\n' + '\n'.join('    ' + l for l in r.stderr.splitlines()[-6:]))
            continue
        for linha in r.stdout.splitlines():
            if linha.strip():
                print('    ' + linha)
        print(f'    ({time.time() - t0:.0f}s)')
    sys.exit(1 if falhou else 0)


if __name__ == '__main__':
    main()
