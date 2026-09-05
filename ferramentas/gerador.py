# -*- coding: utf-8 -*-
"""Gerador de pecas sinteticas com gabarito exato, para testar generalizacao.

NAO e uma copia do gerador da organizacao - e de proposito MAIS LARGO que ele:

* classes processuais vindas da mineracao do acervo, incluindo varias que os 26
  documentos distribuidos nunca usam (APM, IPM, IRDR, EAREsp, RRAg);
* formatos de numero e de UF combinados livremente, inclusive pares que o
  conjunto de desenvolvimento nao exibe;
* frases-veiculo novas, escritas fora do inventario observado;
* ruido de OCR com taxa ajustavel.

Passar aqui significa que o extrator cobre a FORMA. Falhar aqui e falha de
verdade. O que este arquivo nao pode fazer e provar o escore no conjunto cego:
ele testa contra o meu modelo do gerador, nao contra o deles.
"""
import argparse
import json
import random
import re
import unicodedata
from pathlib import Path

from baqueano.canon import BaseCanonica

# --------------------------------------------------------------------------
# inventario de superficie
# --------------------------------------------------------------------------
CLASSES_POR_TRIBUNAL = {
    'STJ': ['REsp', 'Recurso Especial', 'AREsp', 'Agravo em Recurso Especial',
            'AgInt no REsp', 'AgRg no AREsp', 'AgInt no Recurso Especial',
            'EDcl no AgInt no REsp', 'EREsp', 'EAREsp', 'RMS', 'RHC',
            'Recurso em Habeas Corpus', 'HC', 'Rec. Esp.', 'R.Esp.',
            'EDcl nos EDcl no AgInt no Agravo em Recurso Especial'],
    'STF': ['RE', 'Recurso Extraordinário', 'ARE', 'Rcl', 'Reclamação',
            'AgR na Rcl', 'Segundo AgR no RE', 'ADI', 'ADPF', 'ADC',
            'Terceiro AG.REG na Rcl', 'Recl.', 'Tema'],
    'TSE': ['REspe', 'Recurso Especial Eleitoral', 'AgR-REspe', 'AREspEI',
            'ED no AgR-REspe', 'R-Rp', 'Representação', 'AI',
            'Agravo Regimental no Agravo de Instrumento'],
    'TST': ['RR', 'Recurso de Revista', 'AIRR', 'ARR', 'Ag-ARR', 'AgARR',
            'RRAg', 'Ag-AIRR', 'TST-RR-', 'TST-AIRR-', 'TST-ED-E-ED-RR-',
            'Processo nº TST-ARR-'],
    'STM': ['APL', 'Apelação', 'RSE', 'Recurso em Sentido Estrito', 'APM',
            'IPM', 'HC', 'Correição Parcial', 'Apelação (AP)'],
}
# classes que NAO estao na lista fechada do extrator - o teste de fogo
CLASSES_INEDITAS = {'APM', 'IPM', 'RRAg', 'Ag-AIRR', 'EAREsp', 'Correição Parcial',
                    'Apelação (AP)', 'Segundo AgR no RE', 'AgR na Rcl'}

MARCADORES = ['nº ', 'n° ', 'n. ', 'No ', 'Nº ', '', 'n.º ', ' ']
UF = ['AC', 'BA', 'CE', 'DF', 'GO', 'MG', 'MS', 'PA', 'PE', 'PR', 'RJ', 'RS',
      'SC', 'SP', 'TO', 'MA', 'RO']
SUFIXO_UF = ['/{uf}', ' - {uf}', ' ({uf})', '-{uf}', ' – {uf}', '']

DIPLOMAS_TEXTO = {
    'cpc': ['do CPC', 'do Código de Processo Civil', 'do CPC/2015'],
    'cc': ['do Código Civil', 'do CC'],
    'clt': ['da CLT', 'da Consolidação das Leis do Trabalho'],
    'cf': ['da Constituição Federal', 'da Constituição da República', 'da CF/88',
           'da Carta Magna'],
    'cpp': ['do Código de Processo Penal', 'do CPP'],
    'cpm': ['do Código Penal Militar', 'do CPM'],
    'cdc': ['do Código de Defesa do Consumidor', 'do CDC'],
    'ce': ['do Código Eleitoral'],
    'lc64': ['da Lei Complementar nº 64/1990', 'da LC 64/1990'],
}
LEIS_FORA_DA_COBERTURA = ['da Lei nº 9.504/1997', 'da Lei nº 13.467/2017',
                          'da Lei nº 13.105/2015', 'da Lei nº 8.666/1993',
                          'do Código de Trânsito Brasileiro']

VEICULOS = [  # metade observados, metade escritos de novo
    'Vale invocar o', 'Reforça o argumento o', 'A propósito, veja-se o',
    'Invoca-se, ainda, o', 'Corrobora essa leitura o', 'Não se pode ignorar o',
    'Cumpre destacar o', 'Milita em favor da parte o', 'Como já se reconheceu no',
    'Impõe-se a observância do', 'Ampara a pretensão o', 'Cumpre lembrar o',
    'A orientação firmada no', 'Também na', 'O acórdão recorrido diverge do assentado no',
    # novos, fora do inventario observado:
    'Colhe-se do', 'Merece transcrição o', 'Bem ilustra a questão o',
    'No mesmo sentido caminhou o', 'Assim já decidiu esta Corte no',
    'Peço vênia para transcrever o', 'Guarda pertinência com a espécie o',
    'Robustece a tese o', 'Serve de norte o', 'Ilumina a controvérsia o',
]
ENCHIMENTO = [
    'A questão de fundo comporta solução singela.',
    'O ponto nodal da discussão reside na qualificação jurídica dos fatos incontroversos.',
    'Registre-se que o tema comporta enfrentamento sob dupla perspectiva.',
    'A leitura conjunta dos dispositivos invocados conduz à mesma conclusão.',
    'Sob outro ângulo, a solução adotada na origem afronta a segurança jurídica.',
    'Cumpre observar que a orientação dos tribunais superiores é firme no ponto.',
    'Ainda que assim não fosse, subsiste fundamento autônomo a amparar a pretensão.',
    'A moldura fática delineada na origem é suficiente para o deslinde da causa.',
    'O raciocínio desenvolvido no acórdão recorrido parte de premissa equivocada.',
    'A doutrina especializada acompanha, sem divergência relevante, esse entendimento.',
    'Nem se diga que a hipótese comportaria distinção.',
    'Os elementos coligidos aos autos apontam em sentido único.',
]
# Vaga, mas AINDA citacao: nomeia um diploma concreto, so nao diz o artigo.
# Sobreviveu a revisao de 04/09/2026 do gabarito, nos dois documentos em que
# aparece.
VAGAS_COM_FONTE = [
    ('artigo correspondente do Código de Processo Civil', 'lei'),
]
# Difusas: nao apontam para norma nem decisao nenhuma. A revisao de 04/09/2026
# tirou as 30 ocorrencias delas do gabarito. Continuam no texto como distrator.
ANAFORICAS = [
    ('normas de regência da matéria', 'lei'),
    ('legislação de regência da matéria', 'lei'),
    ('dispositivo legal de regência', 'lei'),
    ('dispositivo constitucional invocado na origem', 'lei'),
    ('lei que disciplina a prescrição no caso', 'lei'),
    ('preceito de regência da espécie', 'lei'),
    ('jurisprudência pacífica desta Corte', 'jurisprudencia'),
    ('jurisprudência consolidada dos tribunais superiores', 'jurisprudencia'),
    ('precedentes desta Casa em situações análogas', 'jurisprudencia'),
    ('precedente firmado em sede de recurso repetitivo', 'jurisprudencia'),
    ('entendimento sumulado sobre a matéria', 'jurisprudencia'),
    ('verbete sumular aplicável à espécie', 'jurisprudencia'),
    ('recente acórdão da Segunda Turma', 'jurisprudencia'),
    ('reiterados precedentes do Superior Tribunal de Justiça', 'jurisprudencia'),
    ('aresto proferido pela Seção competente', 'jurisprudencia'),
    ('orientação firmada pelo Plenário da Corte', 'jurisprudencia'),
]
MOLDES_VAGOS = [
    'julgado do {trib} proferido em {ano} pela relatoria de {rel}',
    'acórdão do {trib} julgado em {ano} sob relatoria de {rel}',
    'precedente do {trib} de {ano}, da relatoria de {rel}',
    '{classe} de {ano}, Rel. Min. {rel}',
    '{classe} do {trib}, de {ano}, Rel. Min. {rel}',
    'decisão do {trib} de {ano}, relatada por {rel}',
]
TITULOS = ['I — DA CONTROVÉRSIA', 'II — DO DIREITO APLICÁVEL',
           'III — DOS PRECEDENTES INVOCADOS', 'IV — DA IMPOSSIBILIDADE DE REEXAME FÁTICO']

# ruido de OCR, sempre preservando comprimento
DIGITO_LETRA = {'0': 'O', '1': 'l', '5': 'S', '9': 'g', '6': 'G', '8': 'B', '2': 'Z'}
LETRA_LETRA = {'e': 'c', 'i': 'l', 'a': 'ã', 'o': '0', 's': '5'}


# --------------------------------------------------------------------------
def formata_numero(d, rng):
    """Renderiza uma cadeia de digitos como numero de processo."""
    if 14 <= len(d) <= 20:
        d = d.rjust(20, '0')
        base = f'{d[:7]}-{d[7:9]}.{d[9:13]}.{d[13]}.{d[14:16]}.{d[16:]}'
        estilo = rng.random()
        if estilo < 0.25:
            base = base.lstrip('0')
        elif estilo < 0.40:
            base = re.sub(r'[.\-]', '', base)
        elif estilo < 0.50:
            base = base.replace('.', ' ')
        return base
    if len(d) >= 4 and rng.random() < 0.6:
        partes = []
        while len(d) > 3:
            partes.insert(0, d[-3:]); d = d[:-3]
        partes.insert(0, d)
        return '.'.join(partes)
    return d


def cita_real(base, rng):
    (num, trib), regs = rng.choice(list(base.acordaos.items()))
    classe = rng.choice(CLASSES_POR_TRIBUNAL[trib])
    marca = '' if classe.endswith('-') else rng.choice(MARCADORES)
    sufixo = rng.choice(SUFIXO_UF).format(uf=rng.choice(UF))
    texto = f'{classe}{"" if classe.endswith("-") else " "}{marca}{formata_numero(num, rng)}{sufixo}'
    # Quando o feito tem mais de um registro, o gerador NAO sabe qual e o
    # canonico - ele so sabe o feito. Gravar `regs[0]` faria o gabarito repetir
    # a ordem do nosso proprio indice, e a suite passaria a medir essa ordem em
    # vez da resolucao. Aceitamos qualquer registro do feito.
    ids = ' '.join(sorted(str(r['id']) for r in regs))
    return re.sub(r'  +', ' ', texto), 'real', 'jurisprudencia', ids


def cita_inventada(base, rng):
    trib = rng.choice(list(CLASSES_POR_TRIBUNAL))
    for _ in range(60):
        d = ''.join(rng.choice('0123456789') for _ in range(rng.choice([5, 6, 7, 20])))
        if not any((v, t) in base.acordaos for v in (d, d.rjust(20, '0'), d.lstrip('0'))
                   for t in CLASSES_POR_TRIBUNAL):
            break
    classe = rng.choice(CLASSES_POR_TRIBUNAL[trib])
    marca = '' if classe.endswith('-') else rng.choice(MARCADORES)
    sufixo = rng.choice(SUFIXO_UF).format(uf=rng.choice(UF))
    texto = f'{classe}{"" if classe.endswith("-") else " "}{marca}{formata_numero(d, rng)}{sufixo}'
    return re.sub(r'  +', ' ', texto), 'inventada', 'jurisprudencia', None


def cita_sumula(base, rng):
    if rng.random() < 0.5:
        chave = rng.choice(list(base.sumulas) + [('V', 'STF')])
        if chave == ('V', 'STF'):
            n, reg = next(iter(base.sumulas_vinculantes.items()))
            return f'Súmula Vinculante {n}', 'real', 'jurisprudencia', str(reg['id'])
        num, trib = chave
        return (f'Súmula {num} do {trib}', 'real', 'jurisprudencia',
                str(base.sumulas[chave]['id']))
    n = rng.randint(400, 999)
    trib = rng.choice(['STF', 'STJ', 'TST', 'TSE'])
    return f'Súmula {n} do {trib}', 'inventada', 'jurisprudencia', None


def cita_lei(base, rng):
    if rng.random() < 0.55:
        (cod, art), reg = rng.choice(list(base.dispositivos.items()))
        inciso = rng.choice(['', f', {rng.choice("I II III IV V IX XXIX LV".split())}',
                             ', § 1º', ', § 1º-A'])
        return (f'art. {art}{inciso} {rng.choice(DIPLOMAS_TEXTO[cod])}',
                'real', 'lei', str(reg['id']))
    if rng.random() < 0.5:
        cod = rng.choice(list(DIPLOMAS_TEXTO))
        art = rng.randint(1000, 1999)
        return f'artigo {art} {rng.choice(DIPLOMAS_TEXTO[cod])}', 'inventada', 'lei', None
    return (f'art. {rng.randint(50, 400)} {rng.choice(LEIS_FORA_DA_COBERTURA)}',
            'inventada', 'lei', None)


def cita_vaga(base, rng, relatores):
    """Referencia vaga que AINDA e citacao: tribunal, ano e relator identificados.

    A revisao do gabarito de 04/09/2026 tirou do escopo a referencia difusa
    ('jurisprudencia pacifica desta Corte'), porque nao ha decisao concreta por
    tras dela. Ela continua sendo gerada, mas como enchimento nao anotado - ver
    `gera_documento` -, que e o papel que passou a ter: distrator.
    """
    if rng.random() < 0.12:
        texto, tipo = rng.choice(VAGAS_COM_FONTE)
        return texto, 'incompleta', tipo, None
    trib = rng.choice(list(CLASSES_POR_TRIBUNAL))
    molde = rng.choice(MOLDES_VAGOS)
    texto = molde.format(trib=trib, ano=rng.randint(2015, 2026),
                         rel=rng.choice(relatores),
                         classe=rng.choice([c for c in CLASSES_POR_TRIBUNAL[trib]
                                            if not c.endswith('-')]))
    return texto, 'incompleta', 'jurisprudencia', None


def suja(texto, taxa, rng):
    saida = list(texto)
    for i, ch in enumerate(texto):
        if rng.random() > taxa:
            continue
        if ch.isdigit():
            viz = ((i and texto[i - 1].isdigit())
                   or (i + 1 < len(texto) and texto[i + 1].isdigit()))
            if viz and ch in DIGITO_LETRA:
                saida[i] = DIGITO_LETRA[ch]
        elif ch == ' ' and rng.random() < 0.3:
            saida[i] = '\n'
        elif ch.lower() in LETRA_LETRA:
            saida[i] = LETRA_LETRA[ch.lower()]
    return ''.join(saida)


def gera_documento(base, rng, relatores, nivel, ruido=0.006):
    trib_peca = rng.choice(list(CLASSES_POR_TRIBUNAL))
    cnj_autos = ''.join(rng.choice('0123456789') for _ in range(20))
    partes = [
        rng.choice(['MINISTÉRIO PÚBLICO FEDERAL', 'DEFENSORIA PÚBLICA DA UNIÃO',
                    'PODER JUDICIÁRIO', 'MINISTÉRIO PÚBLICO ELEITORAL']),
        rng.choice(['PROCURADORIA-GERAL DA REPÚBLICA', 'GABINETE DO RELATOR',
                    'OFÍCIO JUNTO AO SUPERIOR TRIBUNAL MILITAR']),
        '',
        f'Processo nº {cnj_autos[:7]}-{cnj_autos[7:9]}.{cnj_autos[9:13]}.'
        f'{cnj_autos[13]}.{cnj_autos[14:16]}.{cnj_autos[16:]}',
        f'Recorrente: {rng.choice(["TRANSPORTES MARAJÓ EIRELI", "AGROPECUÁRIA SANTA CLARA S.A."])}',
        f'Protocolo nº {rng.randint(2019, 2026)}.{rng.randint(100000, 999999)}',
        '',
        rng.choice(['PARECER', 'MEMORIAL', 'DECISÃO MONOCRÁTICA', 'PETIÇÃO']),
        '',
    ]
    corpo, gabarito = [], []
    pos = len('\n'.join(partes)) + 1

    def escreve(txt):
        nonlocal pos
        corpo.append(txt)
        pos += len(txt)

    sorteios = [cita_real] * 4 + [cita_inventada] * 3 + [cita_vaga] * 3 + \
               [cita_sumula, cita_lei, cita_lei]
    for t_idx, titulo in enumerate(TITULOS):
        escreve(titulo + '\n\n')
        for _ in range(rng.randint(2, 3)):
            escreve(rng.choice(ENCHIMENTO) + ' ')
            f = rng.choice(sorteios)
            cit, classe, tipo, idc = (f(base, rng, relatores) if f is cita_vaga
                                      else f(base, rng))
            veic = rng.choice(VEICULOS)
            escreve(veic + ' ')
            ini = pos
            escreve(cit)
            gabarito.append({'inicio': ini, 'fim': pos, 'trecho': cit,
                             'tipo': tipo, 'classificacao': classe,
                             'id_canonico': idc, 'nivel': nivel})
            escreve(rng.choice([', que trata de situação equivalente.',
                                ', cuja fundamentação se pede vênia para transcrever.',
                                '.', ', no ponto em que afasta a exigência combatida.']) + ' ')
            if rng.random() < 0.3:
                escreve(f'Confira-se, ainda, às fls. {rng.randint(100, 900)}/'
                        f'{rng.randint(100, 900)}. ')
            # referencia difusa como DISTRATOR: entra no texto, fica fora do
            # gabarito. Marca-la e falso positivo desde a revisao de 04/09.
            if rng.random() < 0.35:
                escreve(rng.choice(VEICULOS) + ' ' + rng.choice(ANAFORICAS)[0] + '. ')
        escreve('\n\n')
    texto = '\n'.join(partes) + '\n' + ''.join(corpo)
    for c in gabarito:                      # confere que o span bate mesmo
        assert texto[c['inicio']:c['fim']] == c['trecho'], (c, texto[c['inicio']:c['fim']])
    if nivel == 2:
        texto = suja(texto, ruido, rng)
        for c in gabarito:
            c['trecho'] = texto[c['inicio']:c['fim']]
    return texto, gabarito


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=200)
    ap.add_argument('--semente', type=int, default=42)
    ap.add_argument('--saida', default='sintetico')
    ap.add_argument('--ruido', type=float, default=0.006,
                    help='taxa de ruido de OCR nos documentos de nivel 2')
    a = ap.parse_args()
    base = BaseCanonica()
    relatores = [re.sub(r'^(Min\.?|Ministr[oa])\s+', '', r[0]).strip()
                 for r in base.con.execute(
        "SELECT DISTINCT relator FROM documentos WHERE relator IS NOT NULL LIMIT 200")]
    rng = random.Random(a.semente)
    d = Path(a.saida); (d / 'txt').mkdir(parents=True, exist_ok=True)
    linhas = []
    for i in range(a.n):
        nivel = 1 if i % 2 == 0 else 2
        texto, gab = gera_documento(base, rng, relatores, nivel, a.ruido)
        nome = f'syn_n{nivel}_{i:04d}'
        (d / 'txt' / f'{nome}.txt').write_text(texto, encoding='utf-8')
        for k, c in enumerate(gab, 1):
            linhas.append({'nivel': nivel, 'documento_id': nome, 'citacao_id': f'g{k}',
                           **c})
    import csv
    with (d / 'goldenset.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, ['nivel', 'documento_id', 'citacao_id', 'inicio', 'fim',
                               'trecho', 'tipo', 'classificacao', 'id_canonico'],
                           extrasaction='ignore')
        w.writeheader()
        for l in linhas:
            l = dict(l); l['trecho'] = l['trecho'].replace('\n', '\\n')
            w.writerow(l)
    print(f'{a.n} documentos, {len(linhas)} citacoes -> {d}')


if __name__ == '__main__':
    main()
