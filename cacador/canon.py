# -*- coding: utf-8 -*-
"""Indice da base canonica: acordaos, sumulas e dispositivos de lei.

A base e uma cobertura congelada de 1.018 registros. O indice responde a
pergunta que decide a classe de uma citacao: quantos FEITOS distintos casam
com estes identificadores?

Um feito e identificado por (numero de processo normalizado, tribunal); um
mesmo feito pode ter mais de um registro no acervo (embargos de declaracao,
por exemplo), e por isso o valor do indice e uma lista.
"""
import collections
import os
import re
import sqlite3

from .normalize import (com_correcao_ocr, digitos, limpa_quebras, sem_acento,
                        texto_canonico, texto_canonico_leve, variantes_cnj)

DB_PADRAO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         'dados', 'desafio1_bracis.db')

# --------------------------------------------------------------------------
# cabecalho dos acordaos
# --------------------------------------------------------------------------

# Lixo de digitalizacao que carrega numeros e antecede o identificador real.
_LIXO_CABECALHO = re.compile(
    r'\d{2}/\d{2}/\d{4}'                      # data
    r'|P[áa]gina\s+\d+\s+de\s+\d+'            # paginacao
    r'|Inteiro\s+Teor\s+do\s+Ac[óo]rd[ãa]o'
    r'|Ementa\s*e\s*Ac[óo]rd[ãa]o'
    r'|\bDJe?\s*n?[ºo°]?\s*[\d./-]+',         # referencia de diario
    re.I)

# NNNNNNN-DD.AAAA.J.TR.OOOO, tolerando espaco e quebra no meio.
_CNJ = re.compile(r'\d[\d.\s]{0,9}\d\s*-\s*\d{2}\s*\.\s*\d{4}\s*\.\s*\d\s*\.\s*\d{2}\s*\.\s*\d{4}')
# 1.741.784 ou 76.532 - numero "curto" pontuado de 3 em 3.
_PONTUADO = re.compile(r'\d{1,3}(?:\.\s?\d{3})+')
# numero cru; anos sao descartados depois.
_CRU = re.compile(r'\b\d{4,7}\b')

_ANO_MIN, _ANO_MAX = 1930, 2100


def _parece_ano(d):
    return len(d) == 4 and _ANO_MIN <= int(d) <= _ANO_MAX


def _candidatos(h):
    """Numeros do cabecalho, do mais para o menos confiavel."""
    for m in _CNJ.finditer(h):
        yield digitos(m.group())
    for m in _PONTUADO.finditer(h):
        yield digitos(m.group())
    for m in _CRU.finditer(h):
        d = digitos(m.group())
        if not _parece_ano(d):
            yield d


def _primeiro(h):
    for d in _candidatos(h):
        if len(d) >= 4:
            return d
    return None


def _stf(t):
    # 'HABEAS CORPUS 192.063 RIO DE JANEIRO' - a classe vem em caixa alta e o
    # numero logo depois. O CNJ que aparece no cabecalho do STF e o processo de
    # ORIGEM, nao o feito, entao o numero curto tem prioridade.
    h = _LIXO_CABECALHO.sub(' ', t[:600])
    m = _PONTUADO.search(h)
    if m:
        return digitos(m.group())
    return _primeiro(h)


def _stj(t):
    # 'RECURSO ESPECIAL Nº 1.741.784 - PR (2018/0116304-1)'
    h = _LIXO_CABECALHO.sub(' ', t[:600])
    m = re.search(r'N[ºo°]\s*([\d.\s]+?)\s*-\s*[A-Z]{2}\b', h)
    if m and len(digitos(m.group(1))) >= 4:
        return digitos(m.group(1))
    return _primeiro(h)


def _tse(t):
    h = _LIXO_CABECALHO.sub(' ', t[:800])
    return _primeiro(h)


def _tst(t):
    # 'estes autos de Recurso de Revista n TST-RR-1234-56.2011.5.21.0009, em que
    # e Recorrente ...' - a linha de autuacao e o unico lugar onde o numero e do
    # proprio feito; as outras ocorrencias de 'TST-' sao processos CITADOS.
    janela = t[:20000]
    melhor = None
    for m in re.finditer(r'TST\s*-\s*(?:[A-Za-z]+\s*-\s*)*(\d[\d.\-\s]{5,})', janela):
        d = digitos(m.group(1))
        if len(d) < 6:
            continue
        antes = janela[max(0, m.start() - 120):m.start()]
        depois = janela[m.end():m.end() + 160]
        autuacao = (re.search(r'autos\s+de\b', antes, re.I)
                    or re.search(r'^\s*,?\s*em\s+que\s+(é|e|s[ãa]o)\b', depois, re.I))
        if autuacao:
            return d
        if melhor is None:
            melhor = d
    return melhor


def _stm(t):
    h = _LIXO_CABECALHO.sub(' ', t[:2000])
    return _primeiro(h)


PARSERS = {'STF': _stf, 'STJ': _stj, 'TSE': _tse, 'TST': _tst, 'STM': _stm}

# --------------------------------------------------------------------------
# diplomas legais
# --------------------------------------------------------------------------

# Cada dispositivo da base traz o texto do artigo, mas nao diz de qual diploma
# e. O mapa abaixo foi lido registro a registro no proprio acervo (o texto de
# cada artigo identifica o codigo sem ambiguidade) e vale enquanto a cobertura
# estiver congelada; `carrega_dispositivos` falha alto se algum id sumir.
DISPOSITIVOS = {
    10577194:  ('ce',   '276'),  # 'As decisoes dos Tribunais Regionais sao terminativas'
    10590194:  ('cpm',  '290'),  # trafico - Codigo Penal Militar
    10606184:  ('cdc',  '14'),   # 'O fornecedor de servicos responde ... defeitos'
    10626510:  ('cf',   '93'),   # 'Estatuto da Magistratura' - CF/88
    10637358:  ('clt',  '896'),  # 'Cabe Recurso de Revista para Turma do TST'
    10641213:  ('cf',   '7'),    # 'direitos dos trabalhadores urbanos e rurais'
    10641516:  ('cf',   '5'),    # 'Todos sao iguais perante a lei'
    10647746:  ('clt',  '818'),  # onus da prova - reclamante/reclamado
    10652044:  ('cpp',  '312'),  # prisao preventiva
    10710324:  ('clt',  '477'),  # extincao do contrato de trabalho
    10718759:  ('cc',   '186'),  # ato ilicito
    11304039:  ('lc64', '1'),    # 'Sao inelegiveis' - LC 64/1990
    28893055:  ('cpc',  '373'),  # onus da prova - autor/reu
}

# Sumulas cujo numero nao aparece no proprio texto do registro.
SUMULAS_SEM_NUMERO_NO_TEXTO = {
    1289712966: ('10', 'STF', True),    # 'Viola a clausula de reserva de plenario' = SV 10
    1431369957: ('331', 'TST', False),  # terceirizacao, itens I-VI = Sumula 331 do TST
}

_SUMULA_NO_TEXTO = re.compile(r'S[ÚU]MULA\s+(\d+)', re.I)

# Formas de superficie -> codigo canonico. Vocabulario de direito, nao do
# gerador dos documentos: cobre abreviacao, nome por extenso e apelido.
DIPLOMAS = [
    ('cpc',  r'c\.?p\.?c\.?(?:\s*/\s*\d{2,4})?|codigo de processo civil'),
    ('cpp',  r'c\.?p\.?p\.?|codigo de processo penal'),
    ('cppm', r'c\.?p\.?p\.?m\.?|codigo de processo penal militar'),
    ('cpm',  r'c\.?p\.?m\.?|codigo penal militar'),
    ('cp',   r'codigo penal'),
    ('cdc',  r'c\.?d\.?c\.?|codigo de defesa do consumidor'),
    ('clt',  r'c\.?l\.?t\.?|consolidacao das leis do trabalho'),
    ('cc',   r'c\.?c\.?(?:\s*/\s*\d{2,4})?|codigo civil'),
    ('ce',   r'codigo eleitoral'),
    ('cf',   r'c\.?f\.?(?:\s*/\s*\d{2,4})?|constituicao (?:federal|da republica|do brasil)?'
             r'|carta magna|lei maior'),
    ('lc64', r'lei complementar n?o?\.?\s*64(?:\s*/\s*\d{2,4})?|lc n?o?\.?\s*64(?:\s*/\s*\d{2,4})?'),
]
_DIPLOMAS_RX = [(cod, re.compile(r'\b(?:' + rx + r')\b')) for cod, rx in DIPLOMAS]

_LEI_NUMERADA = re.compile(
    r'\blei\s+(?:complementar\s+|ordinaria\s+)?(?:n\s*[.o]*\s*)?'
    r'([\d.]+)\s*(?:/|de\s+)\s*(\d{4})')


def codigo_do_diploma(trecho):
    """Codigo canonico do diploma citado, ou None se nao houver diploma nomeado.

    Uma lei numerada que nao seja a LC 64/1990 vira uma chave propria
    (`lei:13105/2015`): e buscavel, mas nao esta na cobertura congelada, o que
    faz da citacao uma `inventada` - nao uma `incompleta`.
    """
    leve = texto_canonico_leve(trecho)
    m = _LEI_NUMERADA.search(leve)
    if m:
        num, ano = m.group(1).replace('.', ''), m.group(2)
        return 'lc64' if num == '64' else f'lei:{num}/{ano}'
    c = texto_canonico(trecho)
    for tentativa in (c, com_correcao_ocr(c)):
        for cod, rx in _DIPLOMAS_RX:
            if rx.search(tentativa):
                return cod
    return None


# --------------------------------------------------------------------------
# indice
# --------------------------------------------------------------------------

Feito = collections.namedtuple('Feito', 'chave registros')


def _posicao_no_cabecalho(texto, frase, janela):
    """O numero aparece no comeco do documento - logo, o feito e este."""
    digitos_alvo = frase.replace(' ', '')
    cabeca = texto[:janela]
    corrido = re.sub(r'[^0-9]', '', cabeca)
    return digitos_alvo in corrido or digitos_alvo.lstrip('0') in corrido


class BaseCanonica:
    def __init__(self, db=DB_PADRAO):
        self.con = sqlite3.connect(db)
        self.acordaos = collections.defaultdict(list)   # (numero, tribunal) -> [reg]
        self.por_numero = collections.defaultdict(list)  # numero -> [(tribunal, [reg])]
        self.dispositivos = {}                           # (codigo, artigo) -> reg
        self.sumulas = {}                                # (numero, tribunal|None) -> reg
        self.sumulas_vinculantes = {}                    # numero -> reg
        self._carrega()

    # -- construcao --------------------------------------------------------
    def _carrega(self):
        self._carrega_acordaos()
        self._carrega_dispositivos()
        self._carrega_sumulas()

    def _carrega_acordaos(self):
        linhas = self.con.execute(
            "SELECT documento_id,id,tribunal,ano,relator,texto "
            "FROM documentos WHERE natureza='acordao'").fetchall()
        self.total_acordaos = len(linhas)
        self.sem_numero = []
        for did, i, trib, ano, rel, texto in linhas:
            n = PARSERS[trib](texto)
            if not n or len(n) < 4:
                self.sem_numero.append((did, trib))
                continue
            reg = {'documento_id': did, 'id': i, 'tribunal': trib, 'ano': ano,
                   'relator': rel}
            for v in variantes_cnj(n):
                self.acordaos[(v, trib)].append(reg)
        # Desempate entre registros do MESMO feito. O enunciado diz que
        # `id_canonico` e um conjunto e que qualquer id do feito conta como
        # acerto, mas no goldenset de desenvolvimento 4 das 96 `real` caem num
        # feito com mais registros do que o gabarito aceita - inclusive um par
        # de textos byte a byte identicos. Nesses casos nao ha sinal: adotamos
        # uma ordem deterministica (maior documento_id). Nos dois casos
        # observados ela acerta, o que com n=2 nao e evidencia de nada; e so
        # melhor do que depender da ordem de leitura do SQLite.
        for regs in self.acordaos.values():
            regs.sort(key=lambda r: r['documento_id'], reverse=True)
        vistos = set()
        for (n, trib), regs in self.acordaos.items():
            self.por_numero[n].append((trib, regs))
            vistos.add(n)

    def _carrega_dispositivos(self):
        for i, (cod, art) in DISPOSITIVOS.items():
            row = self.con.execute(
                "SELECT documento_id,id,natureza FROM documentos WHERE id=?", (i,)).fetchone()
            if row is None or row[2] != 'dispositivo':
                raise RuntimeError(
                    f'dispositivo {i} nao esta mais na base como esperado - '
                    'a cobertura mudou, revise cacador.canon.DISPOSITIVOS')
            self.dispositivos[(cod, art)] = {'documento_id': row[0], 'id': row[1]}
        n = self.con.execute(
            "SELECT COUNT(*) FROM documentos WHERE natureza='dispositivo'").fetchone()[0]
        if n != len(DISPOSITIVOS):
            raise RuntimeError(f'a base tem {n} dispositivos, o mapa tem {len(DISPOSITIVOS)}')

    def _carrega_sumulas(self):
        linhas = self.con.execute(
            "SELECT documento_id,id,tribunal,texto FROM documentos "
            "WHERE natureza='sumula'").fetchall()
        for did, i, trib, texto in linhas:
            if i in SUMULAS_SEM_NUMERO_NO_TEXTO:
                num, trib_, vinc = SUMULAS_SEM_NUMERO_NO_TEXTO[i]
            else:
                m = _SUMULA_NO_TEXTO.search(texto)
                if not m:
                    raise RuntimeError(
                        f'sumula {i} sem numero no texto e sem entrada em '
                        'SUMULAS_SEM_NUMERO_NO_TEXTO')
                num, trib_, vinc = m.group(1), trib, False
            reg = {'documento_id': did, 'id': i, 'tribunal': trib_, 'vinculante': vinc}
            if vinc:
                self.sumulas_vinculantes[num] = reg
            else:
                self.sumulas[(num, trib_)] = reg

    # -- consulta ----------------------------------------------------------
    def feitos_por_numero(self, cadeias, tribunais=None):
        """Feitos distintos que casam com qualquer das cadeias de digitos."""
        achados = {}
        for d in cadeias:
            for v in variantes_cnj(d):
                for trib, regs in self.por_numero.get(v, []):
                    if tribunais and trib not in tribunais:
                        continue
                    achados[(v.lstrip('0') or v, trib)] = regs
        # duas grafias do mesmo numero (com e sem zeros) sao o mesmo feito
        unicos = {}
        for (n, trib), regs in achados.items():
            unicos[(n, trib)] = regs
        return [Feito(k, v) for k, v in unicos.items()]

    def sumula(self, numero, tribunal=None, vinculante=False):
        if vinculante:
            r = self.sumulas_vinculantes.get(numero)
            return [r] if r else []
        if tribunal:
            r = self.sumulas.get((numero, tribunal))
            return [r] if r else []
        return [r for (n, _t), r in self.sumulas.items() if n == numero]

    def dispositivo(self, codigo, artigo):
        r = self.dispositivos.get((codigo, artigo))
        return [r] if r else []

    # Onde fica o numero do PROPRIO feito, por tribunal. No STF/STJ/TSE ele
    # esta no cabecalho; no TST e no STM vem na linha de autuacao ('estes autos
    # de ... n TST-...'), que pode estar a milhares de caracteres do inicio.
    JANELA_CABECALHO = {'STF': 700, 'STJ': 700, 'TSE': 900, 'TST': 8000, 'STM': 8000}

    def feitos_por_fts(self, cadeias, tribunais=None, janela=None):
        """Ultimo recurso quando o indice de cabecalho nao acha o numero.

        O indice e construido por um parser de cabecalho; se ele errar num
        registro, uma citacao real a esse registro viraria `inventada`. O FTS
        cobre esse buraco - mas devolve tambem quem apenas CITA o numero, e por
        isso so vale o resultado em que o numero aparece nas primeiras
        `janela` posicoes, que e onde fica o numero do proprio feito.
        """
        achados = {}
        for d in cadeias:
            if len(d) < 5:
                continue
            for frase in self._frases_fts(d):
                try:
                    linhas = self.con.execute(
                        "SELECT d.documento_id, d.id, d.tribunal, d.texto "
                        "FROM documentos_fts JOIN documentos d "
                        "  ON d.rowid = documentos_fts.rowid "
                        "WHERE documentos_fts MATCH ? AND d.natureza='acordao' "
                        "LIMIT 40", (f'"{frase}"',)).fetchall()
                except sqlite3.OperationalError:
                    continue
                for did, i, trib, texto in linhas:
                    if tribunais and trib not in tribunais:
                        continue
                    lim = janela or self.JANELA_CABECALHO.get(trib, 700)
                    if _posicao_no_cabecalho(texto, frase, lim):
                        achados.setdefault((d.lstrip('0') or d, trib), []).append(
                            {'documento_id': did, 'id': i, 'tribunal': trib})
        return [Feito(k, v) for k, v in achados.items()]

    @staticmethod
    def _frases_fts(d):
        """Formas com que o numero aparece no texto, como sequencia de tokens."""
        saida = []
        if 14 <= len(d) <= 20:
            p = d.rjust(20, '0')
            saida.append(f'{p[:7]} {p[7:9]} {p[9:13]} {p[13]} {p[14:16]} {p[16:]}')
            q = p.lstrip('0')
            if len(q) >= 13:
                saida.append(f'{q[:-13]} {q[-13:-11]} {q[-11:-7]} {q[-7]} {q[-6:-4]} {q[-4:]}')
        else:
            grupos, resto = [], d
            while len(resto) > 3:
                grupos.insert(0, resto[-3:]); resto = resto[:-3]
            grupos.insert(0, resto)
            saida.append(' '.join(grupos))
        return [f for f in dict.fromkeys(saida) if f.strip()]

    def conta_acordaos(self, tribunal=None, ano=None, relator=None):
        """Quantos acordaos casam com tribunal/ano/relator - a consulta que
        caracteriza a citacao 'buscavel mas ambigua'."""
        sql = "SELECT COUNT(*) FROM documentos WHERE natureza='acordao'"
        args = []
        if tribunal:
            sql += " AND tribunal=?"; args.append(tribunal)
        if ano:
            sql += " AND ano=?"; args.append(int(ano))
        if relator:
            sql += " AND relator LIKE ?"; args.append(f'%{relator}%')
        return self.con.execute(sql, args).fetchone()[0]
