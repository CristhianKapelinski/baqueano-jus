# -*- coding: utf-8 -*-
"""Extracao dos spans de citacao num documento.

A estrategia e ancorar em FORMA JURIDICA, nao em frase do documento: primeiro
acham-se os numeros, depois pergunta-se se a esquerda deles ha uma classe
processual; em paralelo, acham-se as sumulas e os dispositivos de lei; por fim,
as referencias vagas que identificam tribunal, ano e relator sem dar o numero.

Os spans saem em codepoints Unicode, `fim` exclusivo, como manda o contrato.
"""
import re

from .canon import codigo_do_diploma
from .normalize import digitos as digitos_de

UFS = ('AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|'
       'SC|SP|SE|TO')
TRIBUNAIS = ('STF', 'STJ', 'TSE', 'TST', 'STM')

# Inventario de classes processuais dos tribunais superiores, por extenso e
# abreviadas. E vocabulario de direito processual, nao do gerador dos
# documentos. Cada entrada e um pedaco de regex, casado sem distinguir caixa; o
# alfabeto tolera ponto e espaco no meio da abreviacao (R.Esp., Ag. Int.), que e
# o ruido de superficie do nivel 2.
CLASSES = [
    # --- recursos e acoes do STJ / STF ---
    r'Embargos\s+de\s+Declara[çc][ãa]o', r'EDcl', r'EDs?\b',
    r'Embargos\s+de\s+Diverg[êe]ncia', r'EREsp', r'EDv',
    r'Embargos\s+Infringentes', r'EI\b',
    r'Agravo\s+Regimental', r'AgRg', r'AG\.?\s*REG\.?', r'AgR',
    r'Agravo\s+Interno', r'AgInt', r'Ag\.?\s*Int\.?',
    r'Agravo\s+em\s+Recurso\s+Especial', r'AREsp', r'AgREsp',
    r'Agravo\s+de\s+Instrumento', r'AI\b', r'AgI\b',
    r'Agravo\b', r'Ag\b',
    r'Recurso\s+Especial\s+Eleitoral', r'REspe', r'AREspEI',
    r'Recurso\s+Especial', r'R\.?\s*Esp\.?', r'REsp', r'Rec\.?\s*Esp\.?',
    r'Recurso\s+Extraordin[áa]rio', r'ARE', r'RE\b',
    r'Recurso\s+(?:Ordin[áa]rio\s+)?em\s+Mandado\s+de\s+Seguran[çc]a', r'RMS',
    r'Mandado\s+de\s+Seguran[çc]a', r'MS\b',
    r'Recurso\s+(?:Ordin[áa]rio\s+)?em\s+Habeas\s+Corpus', r'RHC',
    r'Habeas\s+Corpus', r'H\.?\s*C\.?\b',
    r'Recurso\s+Ordin[áa]rio', r'RO\b',
    r'Reclama[çc][ãa]o', r'Recl\.?', r'Rcl',
    r'Suspens[ãa]o\s+de\s+Liminar\s+e\s+de\s+Senten[çc]a', r'SLS',
    r'Suspens[ãa]o\s+de\s+Liminar', r'SL\b',
    r'Suspens[ãa]o\s+de\s+Seguran[çc]a', r'SS\b',
    r'A[çc][ãa]o\s+Rescis[óo]ria', r'AR\b',
    r'Conflito\s+de\s+Compet[êe]ncia', r'CC\b',
    r'A[çc][ãa]o\s+Direta\s+de\s+Inconstitucionalidade', r'ADI',
    r'ADPF', r'ADC', r'AC\b', r'Inq\b', r'Pet\b',
    r'Tema\b', r'Tem[ãa]\b',
    # --- trabalhista ---
    r'Agravo\s+de\s+Instrumento\s+em\s+Recurso\s+de\s+Revista', r'AIRR',
    r'Agravo\s+em\s+Recurso\s+de\s+Revista', r'AgARR', r'ARR',
    r'Recurso\s+de\s+Revista', r'RR\b', r'TST',
    # --- eleitoral ---
    r'Representa[çc][ãa]o', r'R\s*-\s*Rp', r'Rp\b',
    r'AgR\s*-\s*REspe', r'AgR\s*-\s*AI', r'RCED', r'AIJE',
    # --- militar ---
    r'Recurso\s+em\s+Sentido\s+Estrito', r'RSE',
    r'Apela[çc][ãa]o', r'APL', r'Ap\b',
]
# 'Terceiro AG.REG na Reclamacao', 'Segundos Embargos de Declaracao'
ORDINAL_PREFIXO = (r'(?:Primeir|Segund|Terceir|Quart|Quint|Sext)[oa]s?\s+')
_CLASSE_ALT = '|'.join(CLASSES)
# Uma cadeia de classes: 'EDcl nos EDcl no AgInt no Agravo em Recurso Especial'
_CONECTOR = r'(?:\s*(?:-|no|na|nos|nas|em|de|do|da)\s*)'
# Entre a classe e o numero cabe um marcador ('n', 'No'), espaco, ou o HIFEN
# que cola a sigla no numero, como em 'ArgInc- 479-60.2011...' e 'ADI-MC 7.123'.
_MARCA_FIM = r'(?:\s*[nN]\s*[.ºo°O]{1,2}\s*|\s*[nN]\.\s*|\s*[-–]\s*|\s+)?\s*$'
CADEIA_CLASSE = re.compile(
    r'(?:' + ORDINAL_PREFIXO + r')?'
    r"(?:(?:" + _CLASSE_ALT + r")\.?['’]?s?" + _CONECTOR + r"?){1,6}" + _MARCA_FIM, re.I)
# --------------------------------------------------------------------------
# ancoras ABERTAS: reconhecem classe processual que nao esta na lista acima.
# A lista fechada e sempre incompleta - a mineracao do acervo
# mostra classes reais ausentes dela (APM, IPM, IRDR, EAREsp, RRAg). Estas duas
# regras cobrem o formato em vez do inventario.
# --------------------------------------------------------------------------
# (a) nucleo nominal: 'Agravo Interno na Suspensao de Liminar e de Sentenca'.
# Sao ~20 substantivos que encabecam classe processual em qualquer tribunal.
_NUCLEO_CLASSE = (r'Recursos?|Agravos?|Embargos?|Reclama[çc][õo]es|Reclama[çc][ãa]o|'
                  r'Apela[çc][ãa]o|Habeas|Mandados?|A[çc][õo]es|A[çc][ãa]o|Conflitos?|'
                  r'Suspens[ãa]o|Representa[çc][ãa]o|Temas?|Inqu[ée]ritos?|'
                  r'Peti[çc][ãa]o|Consulta|Corre[iç][çc][ãa]o|Incidentes?|'
                  r'Presta[çc][ãa]o|Medida|Argui[çc][ãa]o|Revis[ãa]o|Protesto')
_ASPA_ABRE = r'["“”\'(]?'
_ASPA_FECHA = r'["“”\')]?'
ANCORA_NUCLEO = re.compile(
    _ASPA_ABRE + r'\b(?:' + ORDINAL_PREFIXO + r')?(?:' + _NUCLEO_CLASSE + r')' + _ASPA_FECHA +
    r'(?:[\s/]+(?:de|da|do|dos|das|em|no|na|nos|nas|e|com|contra|para)?\s*'
    + _ASPA_ABRE + r'[A-Za-zÀ-ÿ][\wÀ-ÿ]*' + _ASPA_FECHA + r'){0,8}' + _MARCA_FIM, re.I)

# (b) sigla: 'APM', 'IPM', 'IRDR', 'EAREsp', 'Ag-AIRR'. Uma sigla curta colada
# no numero e, na pratica, sempre classe processual - salvo os marcadores de
# publicacao e de documento, que a lista negra abaixo remove.
ANCORA_SIGLA = re.compile(
    r'\b([A-ZÀ-Ú][A-Za-zÀ-ÿ.]{1,10}(?:\s*-\s*[A-Za-zÀ-ÿ.]{1,8}){0,4})' + _MARCA_FIM)
SIGLA_NAO_E_CLASSE = re.compile(
    r'^(?:dje?|dou|doe|lei|leis|decreto|processo|autos|feito|fls?|folhas?|oab|'
    r'art|artigo|cpf|cnpj|rg|cep|conta|s[úu]mula|p[áa]gina|volume|item|'
    r'n|no|de|da|do|em|na|res|resolu[çc][ãa]o|portaria|of[íi]cio|memorial|'
    r'eventos?|fl|doc|id|seq|anexos?|pe[çc]a|apenso|tema|item|inciso|'
    r'protocolo|parecer|peti[çc][ãa]o inicial|' + UFS.lower() + r')$', re.I)

# 'PARECER JURIDICO N 212/2023' e numeracao de documento administrativo, nao
# de processo: qualquer sigla vinda depois de uma dessas palavras nao e classe.
DOCUMENTO_NAO_E_FEITO = re.compile(
    r'\b(?:parecer|of[íi]cio|memorando|memorial|nota|portaria|resolu[çc][ãa]o|'
    r'circular|instru[çc][ãa]o|protocolo|edital|aviso|comunicado|laudo|'
    r'certid[ãa]o|ata|contrato|conv[êe]nio|termo|requerimento|despacho)\b'
    # so o que vem COLADO: a palavra do documento seguida de ate duas palavras
    # em caixa alta. 'Recurso de Oficio a este Tribunal (...' nao conta.
    r'\s+(?:[A-ZÀ-Ú][\wÀ-ÿ]*\s+){0,2}$', re.I)

# 'Processo n TST- ED - E-ED-RR-41200-79...': o prefixo TST- carrega siglas
# encadeadas que nao valem a pena enumerar uma a uma.
ANCORA_TST = re.compile(r'TST\s*-\s*(?:[A-Za-z]{1,6}\s*-\s*){0,6}' + _MARCA_FIM, re.I)

# Marcador de numero: 'nº', 'n.', 'No', 'n°', opcional.
_NUM_MARCA = r'(?:n\s*[.ºo°]{0,2}\s*)?'

# Um numero de processo: digitos com pontuacao/espaco/quebra no meio.
# O ruido do nivel 2 troca letra por digito dentro do numero ('21737l8',
# '1.528.4S5'). O run aceita essas letras e a validacao adiante confere que
# cada uma esta encostada num digito.
_OCR_NO_NUMERO = 'OoIilSsGgBbqZz'
NUMERO = re.compile('\\d[-\\d.\\s\u00a0\u2013' + _OCR_NO_NUMERO + ']{1,32}\\d'
                    '[' + _OCR_NO_NUMERO + ']?|\\b\\d{4,8}\\b')


def _run_valido(t):
    """Um run so vale como numero se cada letra estiver encostada num digito."""
    letras = [i for i, c in enumerate(t) if c.isalpha()]
    if len(letras) > 4:
        return False
    return all((i > 0 and t[i - 1].isdigit()) or (i + 1 < len(t) and t[i + 1].isdigit())
               for i in letras)
SUFIXO_REPERCUSSAO = re.compile(r'\s*d[ao]\s+repercuss[ãa]o\s+geral', re.I)
# '1.741.784 - PR', '(SC)', e tambem o sufixo de recurso interno colado no
# numero: '55.624-AgR/RO', '60.707-AgR-ED/RO'.
_SUFIXO_RECURSO = r'(?:\s*-\s*(?:AgR|ED|EDv|AgR-ED|ED-AgR|EDcl|Segundo|Terceiro)){0,3}'
UF_SUFIXO = re.compile(
    _SUFIXO_RECURSO + r'\s*(?:[/\-–]\s*(?:' + UFS + r')\b|\(\s*(?:' + UFS + r')\s*\))'
    r'|' + _SUFIXO_RECURSO.replace('{0,3}', '{1,3}'))

# --------------------------------------------------------------------------
# distratores: numeros do cabecalho e referencias que nao sao citacao
# --------------------------------------------------------------------------
DISTRATOR_ESQUERDA = re.compile(
    r'(?:fls?\.?|folhas?|f\.)\s*$'
    r'|OAB[\s/]*[A-Z]{0,2}\s*n?[.ºo°]?\s*$'
    r'|protocolo\s+n?[.ºo°]?\s*$'
    r'|R\$\s*$'
    r'|valor\s+(?:da\s+causa|atualizado)[^\n]{0,20}$'
    r'|(?:Mem[oó]rial|Of[ií]cio|Parecer|Peti[çc][ãa]o|Nota\s+T[ée]cnica)'
    r'\s+n?[.ºo°]?\s*$',
    re.I)
DISTRATOR_DIREITA = re.compile(r'^\s*%')
# No cabecalho, 'Processo nº <CNJ>' e o numero DOS AUTOS deste documento.
# No CORPO, 'Processo n <CNJ>' e referencia a OUTRO feito - portanto citacao.
ANCORA_PROCESSO = re.compile(
    r'(?:processos?|autos|feitos?|procedimentos?)\s*(?:n\s*[.ºo°]{0,2}\s*)?$', re.I)


# Rotulo de cabecalho: 'Assistido: X', 'Processo nº 123'. E a estrutura
# rotulo/valor que separa o cabecalho do corpo. A abreviacao de numero so conta
# quando vem NUMERO depois: sem isso a preposicao 'no' e lida como 'nº' e
# qualquer linha de prosa que comece com maiuscula vira rotulo.
LINHA_DE_CABECALHO = re.compile(
    r'^[A-ZÀ-Ú][\wÀ-ÿ.\-]*(?:\s+[A-Za-zÀ-ÿ][\wÀ-ÿ.\-]*){0,2}'
    r'(?::\s*\S|\s+[nN][ºo°.]{1,2}\s*\d)')


def _fim_do_cabecalho(texto, max_linhas=12):
    """Onde termina o bloco de cabecalho e comeca o corpo da peca.

    No cabecalho, o numero em formato CNJ e o dos autos DESTE documento, e por
    isso distrator; no corpo, a referencia a outro processo ja e citacao.

    O cabecalho sao as PRIMEIRAS linhas: sem esse limite, uma linha do corpo que
    comece com maiuscula e traga um 'n' ('Reforca o argumento o REsp n 1.234')
    seria lida como rotulo e engoliria o inicio do texto.
    """
    linhas = texto.split('\n', max_linhas)[:max_linhas]
    fim = pos = 0
    for linha in linhas:
        if len(linha) <= 80 and LINHA_DE_CABECALHO.match(linha):
            fim = pos + len(linha)
        pos += len(linha) + 1
    return fim if fim else min(400, len(texto))


# --------------------------------------------------------------------------
# sumulas
# --------------------------------------------------------------------------
SUMULA = re.compile(
    r'\b(?:[S5][úu]m(?:ula)?\.?)\s*(Vinculante\s*)?' + _NUM_MARCA + r'(\d{1,4})'
    r'(?:\s*d[oe]\s*(' + '|'.join(TRIBUNAIS) + r'))?',
    re.I)

# --------------------------------------------------------------------------
# dispositivos de lei
# --------------------------------------------------------------------------
_ORDINAL = r'[º°ºo]?'
_INCISOS = r'(?:\s*,?\s*(?:inciso\s+|al[íi]nea\s+)?[IVXLC]+\b|\s*,?\s*§+\s*\d+' + _ORDINAL + \
           r'(?:\s*-\s*[A-Z])?|\s*,?\s*[\'"‘“]?[a-z]\)?[\'"’”]?(?=\s*,\s*d))*'
# O diploma vai ate o fim da frase: para antes de um ponto que inicia periodo
# novo, de virgula, ponto-e-virgula ou linha em branco.
_DIPLOMA_TAIL = r'(?:(?!\.\s+[A-ZÀ-Ú])(?!\n\s*\n)[^,;()])'
ARTIGO = re.compile(
    r'\bart(?:igo)?s?\.?\s*'
    # So ha citacao de lei quando o ARTIGO esta identificado. 'artigo
    # correspondente do Codigo de Processo Civil' nomeia o diploma e nao a
    # norma: saiu do gabarito na versao final de 15/09, junto com as demais
    # referencias que nao apontam para uma fonte especifica.
    r'(\d{1,4}(?:\.\d{3})*' + _ORDINAL + r')'
    + _INCISOS +
    r'\s*,?\s*d[oaeu]s?\s+(' + _DIPLOMA_TAIL + r'{2,60})',
    re.I)

# --------------------------------------------------------------------------
# referencias vagas
# --------------------------------------------------------------------------
_NOME = r"[A-ZÀ-Ú][\wÀ-ÿ.'-]*(?:\s+(?:de|da|do|dos|das|e)?\s*[A-ZÀ-Úa-zà-ÿ][\wÀ-ÿ.'-]*){0,4}"
# 'julgado do STF proferido em 2024 pela relatoria de Dias Toffoli'
# 'acórdão do STJ julgado em 2021 sob relatoria de Assusete Magalhães'
# 'precedente do STM de 2023, da relatoria de Marco Antonio'
VAGA_TRIB_ANO_REL = re.compile(
    r'\b(?:julgado|ac[óo]rd[ãa]o|precedente|aresto|decis[ãa]o|entendimento)\s+'
    r'd[oe]\s+(' + '|'.join(TRIBUNAIS) + r')\s*,?\s*'
    r'(?:[\wÀ-ÿ]+\s+){0,3}?'
    r'(?:em|de)\s*(\d{4})\s*,?\s*'
    r'(?:[\wÀ-ÿ]+\s+){0,3}?'
    r'(?:relatoria|relatad[oa]|Rel\.?)\s*(?:Min\.?)?\s*d?[ceo]?\s*(' + _NOME + r')',
    re.I)
# '<Classe> de 2022, Rel. Min. Alexandre De Moraes'
# '<Classe por extenso> do STF, de 2020, Rel. Min. Celso De Mello'
# Nucleo da referencia vaga datada: '(do STJ,) de 2025, Rel. Min. Fulano'. E o
# ano mais o relator que identificam a forma; a classe a esquerda e decoracao,
# e por isso NAO sai de lista fechada - anda-se para tras sobre os tokens
# capitalizados, o que cobre 'EAREsp', 'IPM', 'Apelacao (AP)' e o que vier.
NUCLEO_VAGO_DATADO = re.compile(
    r'(?:d[oe]\s+(' + '|'.join(TRIBUNAIS) + r')\s*,?\s*)?'
    r'de\s*(\d{4})\s*,?\s*'
    r'(?:Rel\.?|relatoria|relatad[oa])\s*(?:Min\.?)?\s*d?[ceo]?\s*(' + _NOME + r')',
    re.I)
TOKEN_DE_CLASSE = re.compile(r"[A-ZÀ-Ú][\wÀ-ÿ.()'’-]*$")


def _estende_classe_a_esquerda(texto, ini, limite=6):
    """Anda para tras sobre tokens capitalizados, que formam o nome da classe."""
    pos = ini
    for _ in range(limite):
        j = pos
        while j > 0 and texto[j - 1] in ' \t':
            j -= 1
        if j == 0 or j == pos:
            break
        k = j
        while k > 0 and texto[k - 1] not in ' \t\n':
            k -= 1
        tok = texto[k:j]
        if not tok or tok[-1] in '.;:!?' and len(tok) > 1 and tok[:-1].islower():
            break
        if not TOKEN_DE_CLASSE.match(tok):
            break
        pos = k
    return pos


# Vista de busca: troca acento e confusao de OCR por letra simples, caractere a
# caractere - o comprimento nao muda, entao um span achado na vista tem as
# mesmas posicoes no texto original. Serve para 'ãrtigo', 'ãcórdão',
# 'jurisprudêneia' casarem sem escrever cada variante na expressao.
_VISTA = str.maketrans({
    'á': 'a', 'à': 'a', 'â': 'a', 'ã': 'a', 'ä': 'a',
    'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
    'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
    'ó': 'o', 'ò': 'o', 'ô': 'o', 'õ': 'o', 'ö': 'o',
    'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u', 'ç': 'c',
    'Á': 'A', 'À': 'A', 'Â': 'A', 'Ã': 'A', 'É': 'E', 'Ê': 'E', 'Í': 'I',
    'Ó': 'O', 'Ô': 'O', 'Õ': 'O', 'Ú': 'U', 'Ç': 'C',
})


def vista_de_busca(texto):
    return texto.translate(_VISTA)


def _apara_diploma(tail, ini_tail):
    """Corta a cauda do diploma no ponto em que ele acaba de ser nomeado.

    Sem isso, 'art. 123, I, do Codigo Penal Militar (Evento 109 da APM n
    7000237-...)' vira um span so, engolindo a citacao seguinte.

    A regra e o prefixo MAIS LONGO que nomeia um diploma - nao o mais curto:
    'Codigo Penal Militar' tem que ganhar de 'Codigo Penal', que e outro codigo.
    """
    escolhido = None
    for p in re.finditer(r'\S+', tail):
        if codigo_do_diploma(tail[:p.end()]) is not None:
            escolhido = p.end()
    if escolhido is None:
        return tail, ini_tail + len(tail)
    return tail[:escolhido], ini_tail + escolhido


def _add(spans, texto, ini, fim, tipo, forma, **extra):
    while fim > ini and texto[fim - 1] in ' \t\n .,;:-–':
        fim -= 1
    while ini < fim and texto[ini] in ' \t\n ':
        ini += 1
    if fim <= ini:
        return
    s = {'inicio': ini, 'fim': fim, 'trecho': texto[ini:fim], 'tipo': tipo,
         'forma': forma}
    s.update(extra)
    spans.append(s)


def extrai(texto):
    """Todos os spans de citacao do documento."""
    spans = []
    vista = vista_de_busca(texto)
    corpo_comeca = _fim_do_cabecalho(texto)

    # 1. sumulas
    for m in SUMULA.finditer(texto):
        _add(spans, texto, m.start(), m.end(), 'jurisprudencia', 'sumula',
             numero=m.group(2), vinculante=bool(m.group(1)),
             tribunal=(m.group(3) or '').upper() or None)

    # 2. dispositivos de lei
    for m in ARTIGO.finditer(texto):
        diploma, fim = _apara_diploma(m.group(2), m.start(2))
        _add(spans, texto, m.start(), fim, 'lei', 'artigo',
             artigo=m.group(1), diploma_txt=diploma)

    # 3. jurisprudencia numerada: acha o numero, olha a esquerda
    ocupado = [(s['inicio'], s['fim']) for s in spans]
    for m in NUMERO.finditer(texto):
        ini, fim = m.start(), m.end()
        if any(a <= ini < b for a, b in ocupado):
            continue
        if not _run_valido(m.group()):
            continue
        esquerda = texto[max(0, ini - 140):ini]
        if DISTRATOR_ESQUERDA.search(esquerda) or DISTRATOR_DIREITA.match(texto[fim:fim + 3]):
            continue
        d = digitos_de(texto[ini:fim])
        if len(d) == 4 and 1900 <= int(d) <= 2100:
            continue  # ano solto ('Rcl de 2021'), nao numero de processo
        # qual ancora reconheceu a citacao; a ferramenta de calibracao le isso
        ancora = 'classe'
        c = CADEIA_CLASSE.search(esquerda)
        if c is None:
            c, ancora = ANCORA_TST.search(esquerda), 'tst'
        if c is None and ini < corpo_comeca:
            continue      # no cabecalho, so classe explicita conta
        if c is None:
            c, ancora = ANCORA_NUCLEO.search(esquerda), 'nucleo'
        if c is None and ini >= corpo_comeca and len(digitos_de(m.group())) >= 14:
            c, ancora = ANCORA_PROCESSO.search(esquerda), 'processo'
        if c is None:
            c, ancora = ANCORA_SIGLA.search(esquerda), 'sigla'
            if c and (SIGLA_NAO_E_CLASSE.match(c.group(1).strip(' .-'))
                      or DOCUMENTO_NAO_E_FEITO.search(esquerda[-70:])):
                c = None
        if not c:
            continue
        ini_classe = max(0, ini - 140) + c.start()
        uf = UF_SUFIXO.match(texto, fim)
        if uf:
            fim = uf.end()
        rg = SUFIXO_REPERCUSSAO.match(texto, fim)
        if rg:
            fim = rg.end()
        _add(spans, texto, ini_classe, fim, 'jurisprudencia', 'numerada',
             ancora=ancora)

    # 3b. listas enumeradas: 'Rcls 60.699 e 60.703', 'Rcl's 55.624-AgR/RO,
    # 60.681-AgR/RO, 60.682-AgR/RO'. Uma classe governa varios numeros; so o
    # primeiro tem a classe a esquerda, os demais herdam.
    spans += _lista_enumerada(texto, [s for s in spans if s['forma'] == 'numerada'])

    # 4. referencias vagas com tribunal/ano/relator
    for m in VAGA_TRIB_ANO_REL.finditer(vista):
        _add(spans, texto, m.start(), m.end(), 'jurisprudencia', 'vaga_trib_ano_rel')
    for m in NUCLEO_VAGO_DATADO.finditer(vista):
        ini = _estende_classe_a_esquerda(texto, m.start())
        _add(spans, texto, ini, m.end(), 'jurisprudencia', 'vaga_classe_ano_rel')

    return _resolve_sobreposicao(spans)


# Entre dois itens de uma lista so cabe pontuacao de enumeracao.
SEPARADOR_DE_LISTA = re.compile(r'^\s*(?:[,;]\s*(?:e\s+)?|\s+e\s+)$')


def _lista_enumerada(texto, numeradas):
    """Numeros que continuam uma citacao ja reconhecida, em enumeracao.

    O `trecho` do span continua sendo o texto literal (o contrato exige isso);
    a classe do primeiro item viaja em `classe_herdada`, para a classificacao
    poder inferir o tribunal.
    """
    novos = []
    for s in numeradas:
        primeiro_digito = next((i for i, c in enumerate(s['trecho']) if c.isdigit()),
                               len(s['trecho']))
        classe = s['trecho'][:primeiro_digito].strip(' \n.,-')
        fim = s['fim']
        while True:
            prox = NUMERO.search(texto, fim, fim + 60)
            if not prox or not SEPARADOR_DE_LISTA.match(texto[fim:prox.start()]):
                break
            if not _run_valido(prox.group()) or len(digitos_de(prox.group())) < 4:
                break
            f2 = prox.end()
            uf = UF_SUFIXO.match(texto, f2)
            if uf:
                f2 = uf.end()
            novos.append({'inicio': prox.start(), 'fim': f2,
                          'trecho': texto[prox.start():f2],
                          'tipo': 'jurisprudencia', 'forma': 'numerada',
                          'classe_herdada': classe})
            fim = f2
    return novos


def _resolve_sobreposicao(spans):
    """Mantem, entre spans que se sobrepoem, o mais especifico (o mais longo)."""
    ordem = {'sumula': 0, 'artigo': 0, 'vaga_trib_ano_rel': 1,
             'vaga_classe_ano_rel': 1, 'numerada': 2}
    spans.sort(key=lambda s: (ordem[s['forma']], -(s['fim'] - s['inicio'])))
    saida = []
    for s in spans:
        if any(s['inicio'] < t['fim'] and t['inicio'] < s['fim'] for t in saida):
            continue
        saida.append(s)
    saida.sort(key=lambda s: s['inicio'])
    return saida
