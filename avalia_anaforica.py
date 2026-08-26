# -*- coding: utf-8 -*-
"""Teste dedicado da familia mais fragil: a referencia SEM identificador.

Os positivos sao parafrases escritas de proposito FORA do vocabulario da regra
- outros substantivos de autoridade juridica, outras ancoras de referencia. Os
negativos sao frases reais dos 26 documentos que o gabarito NAO anota: se o
extrator marca uma delas, e falso positivo comprovado, nao suposto.

Isto e o que o conjunto sintetico nao consegue medir: la, as frases anaforicas
foram copiadas do gabarito observado, entao o teste seria circular.
"""
from cacador.extract import extrai

# --- positivos: referencia a autoridade juridica sem identificador ---------
POSITIVOS = [
    'os preceitos legais que regem a espécie',
    'o entendimento firmado por esta Casa',
    'a diretriz jurisprudencial predominante',
    'o comando normativo aplicável à hipótese',
    'as súmulas pertinentes ao tema',
    'o precedente vinculante sobre a controvérsia',
    'a orientação sedimentada no âmbito da Corte',
    'os julgados paradigmáticos da matéria',
    'a norma processual de regência',
    'os arestos desta Turma sobre a questão',
    'a legislação especial de regência',
    'o dispositivo de lei federal invocado',
    'o verbete sumular que rege a hipótese',
    'a tese firmada em repercussão geral',
    'os enunciados sumulares desta Corte',
    'o texto legal que disciplina a matéria',
    'a regra de direito material aplicável',
    'os fundamentos normativos da pretensão',
    'o entendimento consolidado no âmbito do Tribunal',
    'a jurisprudência dominante sobre o tema',
    'o julgado paradigma invocado na origem',
    'as disposições legais de regência',
    'o precedente qualificado firmado pela Corte',
    'a orientação vinculante em vigor',
    'os verbetes aplicáveis à controvérsia',
    'o preceito constitucional de regência',
    'a súmula pertinente ao caso',
    'os dispositivos processuais invocados na origem',
]
# --- negativos: frases reais dos 26 documentos, nao anotadas no gabarito ---
NEGATIVOS = [
    'A leitura conjunta dos dispositivos invocados conduz à mesma conclusão.',
    'Cumpre observar que a orientação dos tribunais superiores é firme no ponto.',
    'O raciocínio desenvolvido no acórdão recorrido parte de premissa equivocada.',
    'A doutrina especializada acompanha, sem divergência relevante, esse entendimento.',
    'O acórdão recorrido manteve a dosimetria, limitando-se a afastar uma das agravantes.',
    'Ante o exposto, requer-se o provimento do recurso, com a reforma do acórdão recorrido.',
    'A sentença de primeiro grau apreciou todos os pedidos formulados na inicial.',
    'As razões recursais reiteram os argumentos já deduzidos na peça de ingresso.',
    'O julgado hostilizado desconsiderou por completo a prova dos autos.',
    'A jurisprudência foi corretamente aplicada pelo juízo de origem.',
    'Os precedentes citados pela parte adversa não guardam pertinência com a espécie.',
    'O entendimento da Turma foi devidamente registrado na ata de julgamento.',
    'A norma invocada pela defesa não socorre a pretensão deduzida.',
    'Os artigos indicados na petição inicial foram todos apreciados na sentença.',
    'O acórdão embargado enfrentou a matéria de forma exaustiva.',
]
# frases-veiculo, para o positivo aparecer em posicao de citacao
VEICULOS = ['Invoca-se, ainda, ', 'Impõe-se a observância de ',
            'A tese encontra respaldo em ', 'Toda a construção defensiva repousa em ',
            'Vale invocar ', 'Milita em favor da parte ']


def anaforicos(texto):
    return [s for s in extrai(texto) if s['forma'] == 'vaga_anaforica']


def main():
    achou = falta = 0
    perdidos = []
    for i, p in enumerate(POSITIVOS):
        frase = f'{VEICULOS[i % len(VEICULOS)]}{p}, o que basta ao deslinde.'
        sp = anaforicos(frase)
        if sp and any(p.split()[-1] in s['trecho'] for s in sp):
            achou += 1
        else:
            falta += 1
            perdidos.append((p, [s['trecho'] for s in sp]))
    fp = []
    for n in NEGATIVOS:
        sp = anaforicos(n)
        if sp:
            fp.append((n, [s['trecho'] for s in sp]))
    print(f'POSITIVOS (parafrases ineditas): {achou}/{len(POSITIVOS)} '
          f'({achou/len(POSITIVOS):.0%} de recall)')
    for p, got in perdidos:
        print(f'   perdido: {p!r}' + (f'  -> pegou {got}' if got else ''))
    print(f'\nNEGATIVOS (frases reais nao anotadas): {len(NEGATIVOS)-len(fp)}/'
          f'{len(NEGATIVOS)} limpos ({1-len(fp)/len(NEGATIVOS):.0%} de precisao)')
    for n, got in fp:
        print(f'   FALSO POSITIVO em {n[:60]!r} -> {got}')


if __name__ == '__main__':
    main()
