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

SUITES = [
    ('goldenset (26 documentos distribuidos)', [sys.executable, 'eval.py', '--conjunto', 'tudo'], False),
    ('acervo real (627 citacoes dos 1.018 registros)', [sys.executable, 'avalia_acervo.py', '--amostra', '0'], True),
    ('sintetico proprio, semente inedita', [sys.executable, 'avalia_sintetico.py', '--dir', 'sintetico'], False),
    ('referencia sem identificador (parafrases ineditas)', [sys.executable, 'avalia_anaforica.py'], False),
    ('robustez a ruido de OCR', [sys.executable, 'stress.py'], True),
    ('ablacao do vocabulario de classe', [sys.executable, 'ablacao.py'], True),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rapido', action='store_true',
                    help='pula as suites lentas (acervo, ruido, ablacao)')
    a = ap.parse_args()
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
