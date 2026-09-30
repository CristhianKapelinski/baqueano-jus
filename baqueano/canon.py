# -*- coding: utf-8 -*-
"""Indice da base canonica: acordaos, sumulas e dispositivos de lei.

A base e uma cobertura congelada. O indice responde a
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
import sys
from pathlib import Path

from .normalize import (com_correcao_ocr, digitos, sem_acento, texto_canonico,
                        texto_canonico_leve, variantes_cnj)

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


def _cabecalho(t, janela):
    """O inicio do documento sem o lixo de digitalizacao que carrega numeros."""
    return _LIXO_CABECALHO.sub(' ', t[:janela])


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
    h = _cabecalho(t, 600)
    m = _PONTUADO.search(h)
    if m:
        return digitos(m.group())
    return _primeiro(h)


def _stj(t):
    # 'RECURSO ESPECIAL Nº 1.741.784 - PR (2018/0116304-1)'
    h = _cabecalho(t, 600)
    m = re.search(r'N[ºo°]\s*([\d.\s]+?)\s*-\s*[A-Z]{2}\b', h)
    if m and len(digitos(m.group(1))) >= 4:
        return digitos(m.group(1))
    return _primeiro(h)


def _tse(t):
    return _primeiro(_cabecalho(t, 800))


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
    return _primeiro(_cabecalho(t, 2000))


def _generico(t):
    # tribunal sem leitor proprio: o primeiro numero do cabecalho
    return _primeiro(_cabecalho(t, 800))


PARSERS = {'STF': _stf, 'STJ': _stj, 'TSE': _tse, 'TST': _tst, 'STM': _stm}

# --------------------------------------------------------------------------
# diplomas legais
# --------------------------------------------------------------------------

# Cada dispositivo da base abre com uma linha que diz qual e:
# 'Artigo 373 da Lei nº 13.105, de 16 de março de 2015'. A base da avaliacao e
# outra, entao o indice sai dessa linha e nao de uma lista de ids. Os codigos
# com nome proprio sao reconhecidos pelo numero da lei; qualquer outra lei vira
# a chave `lei:numero/ano`, a mesma que `codigo_do_diploma` gera na citacao.
CODIGO_DA_LEI = {
    '13105': 'cpc',   # Codigo de Processo Civil
    '3689':  'cpp',   # Codigo de Processo Penal (Decreto-Lei)
    '1002':  'cppm',  # Codigo de Processo Penal Militar (Decreto-Lei)
    '1001':  'cpm',   # Codigo Penal Militar (Decreto-Lei)
    '2848':  'cp',    # Codigo Penal (Decreto-Lei)
    '8078':  'cdc',   # Codigo de Defesa do Consumidor
    '5452':  'clt',   # Consolidacao das Leis do Trabalho (Decreto-Lei)
    '10406': 'cc',    # Codigo Civil
    '4737':  'ce',    # Codigo Eleitoral
    '64':    'lc64',  # Lei Complementar 64/1990, das inelegibilidades
}

_CABECALHO_ARTIGO = re.compile(r'Artigo\s+(\d[\d.]*)\s*[º°o]?\s+d[aoe]s?\s+(.+)', re.I)
_NORMA_NUMERADA = re.compile(
    r'\b(?:decreto-lei|lei\s+complementar|lei)\s+n\s*[º°o.]*\s*([\d.]+).*?(\d{4})\b', re.I)
_CABECALHO_SUMULA = re.compile(
    r'S[úu]mula\s+(Vinculante\s+)?n\s*[º°o.]*\s*(\d+)(?:\s+d[oe]\s+([A-Z]{2,4})\b)?', re.I)


def normaliza_artigo(artigo):
    """'7º' -> '7', '1.134' -> '1134': a mesma forma na base e na citacao."""
    return str(artigo).strip().rstrip('º°o').replace('.', '').strip()


def dispositivo_do_cabecalho(texto):
    """(codigo, artigo) lidos da primeira linha do registro, ou None."""
    m = _CABECALHO_ARTIGO.match(texto.lstrip().split('\n', 1)[0])
    if not m:
        return None
    artigo, norma = normaliza_artigo(m.group(1)), m.group(2)
    if re.search(r'constitui[çc][ãa]o', norma, re.I):
        return 'cf', artigo
    n = _NORMA_NUMERADA.search(norma)
    if not n:
        return None
    num = n.group(1).replace('.', '')
    return CODIGO_DA_LEI.get(num, f'lei:{num}/{n.group(2)}'), artigo


def _avisa(msg):
    print(f'AVISO base: {msg}', file=sys.stderr)


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

    Lei citada pelo numero cai no codigo dela ('Lei nº 13.105/2015' e o CPC);
    outra lei numerada vira a chave `lei:numero/ano`, a mesma que o indice da
    aos dispositivos dessa lei. Fora da cobertura, a citacao sai `inventada` -
    nao `incompleta`.
    """
    leve = texto_canonico_leve(trecho)
    m = _LEI_NUMERADA.search(leve)
    if m:
        num, ano = m.group(1).replace('.', ''), m.group(2)
        return CODIGO_DA_LEI.get(num, f'lei:{num}/{ano}')
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

# Classe processual escrita no cabecalho do acordao. Dois recursos sobre o mesmo
# processo (o REsp e os embargos de divergencia nele) compartilham o numero e
# por isso caem no mesmo feito; o que os separa e a classe.
_CLASSE_CABECALHO = re.compile(
    r'(embargos\s+de\s+diverg[êe]ncia|embargos\s+de\s+declara[çc][ãa]o|'
    r'agravo\s+interno|agravo\s+regimental|agravo\s+em\s+recurso\s+especial|'
    r'recurso\s+especial\s+eleitoral|recurso\s+especial|recurso\s+extraordin[áa]rio|'
    r'recurso\s+de\s+revista|recurso\s+em\s+mandado\s+de\s+seguran[çc]a|'
    r'recurso\s+em\s+habeas\s+corpus|habeas\s+corpus|mandado\s+de\s+seguran[çc]a|'
    r'reclama[çc][ãa]o|apela[çc][ãa]o|recurso\s+em\s+sentido\s+estrito|'
    r'agravo\s+de\s+instrumento|a[çc][ãa]o\s+rescis[óo]ria|representa[çc][ãa]o)',
    re.I)


def classe_do_cabecalho(texto, janela=600):
    """Classes processuais nomeadas no cabecalho, em ordem de aparicao."""
    vista = sem_acento(texto[:janela]).lower()
    return [sem_acento(m.group()).lower() for m in _CLASSE_CABECALHO.finditer(vista)]


# Numero de processo no texto, para a checagem posicional. Data e paginacao
# ficam de fora - elas vem antes do identificador e o mascarariam.
_LIXO_POSICIONAL = re.compile(
    r'\d{2}/\d{2}/\d{4}|P[áa]gina\s+\d+\s+de\s+\d+|\b(?:19|20)\d{2}\b')
_NUM_POSICIONAL = re.compile(r'\d[\d.\s-]{3,30}\d')
# No TST e no STM o numero do feito vem na linha de autuacao, nao no cabecalho.
_AUTUACAO = re.compile(r'autos\s+de\b|em\s+que\s+(?:é|e|s[ãa]o)\b', re.I)


def _posicao_no_cabecalho(texto, frase, janela, tribunal=None):
    """O numero e o do PROPRIO feito - nao o de um processo que ele cita.

    Aparecer cedo nao basta. A ementa comeca logo depois do cabecalho e cita
    outros processos: no STF, 'AG.REG. NA RECLAMACAO 66.755' menciona o RE
    958.252 no caractere 644, dentro de qualquer janela generosa. Por isso o
    criterio e mais duro:

    * STF/STJ/TSE - o numero tem que ser o PRIMEIRO numero de processo do
      documento (datas e paginacao descontadas);
    * TST/STM - tem que estar junto da linha de autuacao ('estes autos de ...',
      '..., em que e Agravante'), que e onde mora o numero do feito.
    """
    sem_zero = frase.replace(' ', '').lstrip('0')
    cabeca = _LIXO_POSICIONAL.sub(' ', texto[:janela])

    if tribunal in ('TST', 'STM'):
        for m in _NUM_POSICIONAL.finditer(cabeca):
            if digitos(m.group()).lstrip('0') == sem_zero:
                volta = cabeca[max(0, m.start() - 130):m.start()]
                adiante = cabeca[m.end():m.end() + 160]
                if _AUTUACAO.search(volta) or _AUTUACAO.search(adiante):
                    return True
        return False

    for m in _NUM_POSICIONAL.finditer(cabeca):
        d = digitos(m.group())
        if len(d) >= 4:
            return d.lstrip('0') == sem_zero
    return False


class BaseCanonica:
    def __init__(self, db=None):
        db = db or DB_PADRAO
        if not os.path.isfile(db):
            raise FileNotFoundError(f'base canonica nao encontrada: {db}')
        # so leitura: a base pode vir montada sem permissao de escrita, e um
        # caminho errado nao cria um arquivo vazio no lugar
        self.con = sqlite3.connect(Path(db).resolve().as_uri() + '?mode=ro', uri=True)
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
            "SELECT documento_id,id,tribunal,texto FROM documentos "
            "WHERE natureza='acordao'").fetchall()
        sem_leitor = collections.Counter(t for _d, _i, t, _x in linhas if t not in PARSERS)
        for trib, n in sem_leitor.items():
            _avisa(f'{n} acordao(s) do tribunal {trib!r}, sem leitor proprio de '
                   'cabecalho: usado o primeiro numero do cabecalho')
        for did, i, trib, texto in linhas:
            n = PARSERS.get(trib, _generico)(texto)
            if not n or len(n) < 4:
                continue
            # a classe do cabecalho desempata dois recursos do mesmo processo
            reg = {'documento_id': did, 'id': i, 'tribunal': trib,
                   'texto_len': len(texto), 'classes': classe_do_cabecalho(texto)}
            for v in variantes_cnj(n):
                self.acordaos[(v, trib)].append(reg)
        # Desempate entre registros do MESMO feito. O acervo traz o mesmo
        # acordao transcrito duas vezes, sob ids diferentes, quando a extracao
        # foi feita em passadas distintas: uma delas perde acentos, troca aspas
        # e engole trechos curtos. A que ficou MAIS LONGA e a mais completa, e e
        # ela que serve de registro canonico - criterio de conteudo, defensavel
        # sem olhar gabarito nenhum, e nao a ordem de leitura do SQLite.
        for (n, trib), regs in self.acordaos.items():
            regs.sort(key=lambda r: (-r['texto_len'], r['documento_id']))
            self.por_numero[n].append((trib, regs))

    def _carrega_dispositivos(self):
        linhas = self.con.execute(
            "SELECT documento_id,id,texto FROM documentos "
            "WHERE natureza='dispositivo'").fetchall()
        for did, i, texto in linhas:
            chave = dispositivo_do_cabecalho(texto)
            if chave is None:
                _avisa(f'dispositivo {i}: primeira linha nao identifica o artigo, '
                       'fica fora do indice')
                continue
            self.dispositivos.setdefault(chave, {'documento_id': did, 'id': i})

    def _carrega_sumulas(self):
        linhas = self.con.execute(
            "SELECT documento_id,id,tribunal,texto FROM documentos "
            "WHERE natureza='sumula'").fetchall()
        for did, i, trib, texto in linhas:
            m = _CABECALHO_SUMULA.match(texto.lstrip())
            if m:
                num, vinc = m.group(2), bool(m.group(1))
                trib_ = trib or (m.group(3) or '').upper() or None
            else:
                m = _SUMULA_NO_TEXTO.search(texto)
                if not m:
                    _avisa(f'sumula {i}: numero nao encontrado, fica fora do indice')
                    continue
                num, trib_, vinc = m.group(1), trib, False
            reg = {'documento_id': did, 'id': i, 'tribunal': trib_, 'vinculante': vinc}
            if vinc:
                self.sumulas_vinculantes.setdefault(num, reg)
            else:
                self.sumulas.setdefault((num, trib_), reg)

    # -- consulta ----------------------------------------------------------
    def feitos_por_numero(self, cadeias, tribunais=None):
        """Feitos distintos que casam com qualquer das cadeias de digitos."""
        achados = {}
        for d in cadeias:
            for v in variantes_cnj(d):
                for trib, regs in self.por_numero.get(v, []):
                    if not tribunais or trib in tribunais:
                        # com e sem zeros a esquerda e o mesmo feito
                        achados[(v.lstrip('0') or v, trib)] = regs
        return [Feito(k, v) for k, v in achados.items()]

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

    def feitos_por_fts(self, cadeias, tribunais=None):
        """Ultimo recurso quando o indice de cabecalho nao acha o numero.

        O indice e construido por um parser de cabecalho; se ele errar num
        registro, uma citacao real a esse registro viraria `inventada`. O FTS
        cobre esse buraco - mas devolve tambem quem apenas CITA o numero, e por
        isso so vale o resultado em que o numero aparece onde fica o numero do
        proprio feito, numa janela que depende do tribunal.
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
                    lim = self.JANELA_CABECALHO.get(trib, 700)
                    if _posicao_no_cabecalho(texto, frase, lim, trib):
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
