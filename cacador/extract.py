# -*- coding: utf-8 -*-
"""Extracao dos spans de citacao num documento.

A estrategia e ancorar em FORMA JURIDICA, nao em frase do documento: primeiro
acham-se os numeros, depois pergunta-se se a esquerda deles ha uma classe
processual; em paralelo, acham-se as sumulas e os dispositivos de lei; por fim,
as referencias vagas, que sao citacoes sem identificador.

Os spans saem em codepoints Unicode, `fim` exclusivo, como manda o contrato.
"""
import re
import unicodedata

from .normalize import digitos as digitos_de

Span = dict  # {'inicio','fim','trecho','tipo','forma'}

UFS = ('AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|'
       'SC|SP|SE|TO')
TRIBUNAIS = ('STF', 'STJ', 'TSE', 'TST', 'STM')

TRIBUNAL_POR_EXTENSO = {
    'supremo tribunal federal': 'STF',
    'superior tribunal de justica': 'STJ',
    'tribunal superior eleitoral': 'TSE',
    'tribunal superior do trabalho': 'TST',
    'superior tribunal militar': 'STM',
}

# Classes processuais. Cada entrada e um pedaco de regex; o alfabeto tolera
# ponto e espaco no meio da abreviacao (R.Esp. / Ag. Int. / Rec. Esp.), que e
# o ruido de superficie do nivel 2.
# Inventario de classes processuais dos tribunais superiores - forma por
# extenso e abreviacao. E vocabulario de direito processual, nao do gerador
# dos documentos: vale para qualquer peca.
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
    r'RESP',
    r'Recurso\s+Extraordin[áa]rio', r'ARE', r'RE\b',
    r'Recurso\s+(?:Ordin[áa]rio\s+)?em\s+Mandado\s+de\s+Seguran[çc]a', r'RMS',
    r'Mandado\s+de\s+Seguran[çc]a', r'MS\b',
    r'Recurso\s+(?:Ordin[áa]rio\s+)?em\s+Habeas\s+Corpus', r'RHC',
    r'Habeas\s+Corpus', r'H\.?\s*C\.?\b',
    r'Recurso\s+Ordin[áa]rio', r'RO\b',
    r'Reclama[çc][ãa]o', r'Recl\.?', r'Rcl', r'RCL',
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
    # --- generico de recurso interno ---
    r'ED\b',
]
# 'Terceiro AG.REG na Reclamacao', 'Segundos Embargos de Declaracao'
ORDINAL_PREFIXO = (r'(?:Primeir|Segund|Terceir|Quart|Quint|Sext)[oa]s?\s+')
_CLASSE_ALT = '|'.join(CLASSES)
# Uma cadeia de classes: 'EDcl nos EDcl no AgInt no Agravo em Recurso Especial'
_CONECTOR = r'(?:\s*(?:-|no|na|nos|nas|em|de|do|da)\s*)'
_MARCA_FIM = r'(?:\s*[nN]\s*[.ºo°O]{1,2}\s*|\s*[nN]\.\s*|\s+)?\s*$'
CADEIA_CLASSE = re.compile(
    r'(?:' + ORDINAL_PREFIXO + r')?'
    r"(?:(?:" + _CLASSE_ALT + r")\.?['’]?s?" + _CONECTOR + r"?){1,6}" + _MARCA_FIM, re.I)
# --------------------------------------------------------------------------
# ancoras ABERTAS: reconhecem classe processual que nao esta na lista acima.
# A lista fechada e sempre incompleta - a mineracao dos 1.018 registros da base
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
    _ASPA_ABRE + r'(?:' + ORDINAL_PREFIXO + r')?(?:' + _NUCLEO_CLASSE + r')' + _ASPA_FECHA +
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
AUTOS_PROPRIOS = re.compile(r'(?:processo|autos|feito)\s+n?[.ºo°]?\s*$', re.I)
# No CORPO, 'Processo n <CNJ>' e referencia a OUTRO feito - portanto citacao.
ANCORA_PROCESSO = re.compile(
    r'(?:processos?|autos|feitos?|procedimentos?)\s*(?:n\s*[.ºo°]{0,2}\s*)?$', re.I)


# Linha de cabecalho: 'Assistido: X', 'Processo nº Y', 'Protocolo nº Z'. E a
# estrutura rotulo/valor que separa o cabecalho do corpo - mais confiavel que
# procurar a linha do tipo da peca, que se confunde com o nome do orgao.
LINHA_DE_CABECALHO = re.compile(
    r'^[A-ZÀ-Ú][\wÀ-ÿ .\-]{2,32}(?::|\s+n[ºo°.]{1,2})\s*\S', re.M)


def _fim_do_cabecalho(texto):
    """Onde termina o bloco de cabecalho e comeca o corpo da peca.

    No cabecalho, o numero em formato CNJ e o dos autos DESTE documento, e por
    isso distrator; no corpo, a referencia a outro processo ja e citacao.
    """
    fim = 0
    for m in LINHA_DE_CABECALHO.finditer(texto[:1500]):
        fim = texto.find('\n', m.end())
        if fim < 0:
            fim = m.end()
    return fim if fim else min(600, len(texto))


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
    r'(\d{1,4}(?:\.\d{3})*' + _ORDINAL + r'|correspondente)'
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


# Nucleo juridico de uma referencia anaforica, e a ancora que ela usa para
# apontar para algo. A vista de busca ja tira o acento, entao basta a forma
# simples; o sufixo tolerante ('jurisprud[..]ia') absorve corrupcao de OCR.
_NUCLEO = (r'normas?|legislacao|leis?\b|dispositivos?|artigos?|preceitos?|'
           r'jurisprud[\wÀ-ÿ]{0,4}ia|precedentes?|acordao|julgados?|arestos?|'
           r'entend[\wÀ-ÿ]{0,6}ento|verbete|sumula|orientacao')
_ANCORA = (r'reg[êe]ncia|invocad|repetitiv|sumulad|sumular|correspondente|'
           r'mat[ée]ria|esp[ée]cie|corte|casa|turma|se[çc][ãa]o|caso|'
           r'tribuna(?:l|is)|superior(?:es)?|origem|repercuss[ãa]o|'
           r'regencia|materia|especie|secao|plenario|plen[áa]rio|competente')

# Uma referencia sem identificador so e citacao quando e um SINTAGMA NOMINAL
# fechado - termina em fronteira de oracao e nao contem verbo finito. E o que
# separa 'jurisprudencia pacifica desta Corte' (citacao) de 'a orientacao dos
# tribunais superiores e firme no ponto' (frase descritiva).
VAGA_ANAFORICA = re.compile(
    r'\b(?:recentes?\s+|reiterados?\s+|iterativos?\s+)?'
    r'(?:' + _NUCLEO + r')'
    r'(?:[ \t\n\xa0]+[a-zà-ÿA-ZÀ-Ú][\wÀ-ÿ]*){1,7}?'
    r'(?=[,.;:]|\n\s*\n|$)',
    re.I)
_TEM_ANCORA = re.compile(_ANCORA, re.I)
# Verbo finito dentro do sintagma: sinal de que a frase seguiu adiante e o
# trecho nao e mais uma referencia, e sim uma oracao.
_VERBO_FINITO = re.compile(
    r'\b(?:e|sao|foi|foram|esta|estao|ha|tem|deve|devem|conduz|conduzem|'
    r'aponta|apontam|autoriza|autorizam|impoe|impoem|permite|permitem|'
    r'revela|revelam|demonstra|demonstram|confirma|confirmam|afasta|afastam|'
    r'reconhece|reconhecem|firma|firmam|resulta|resultam|decorre|decorrem|'
    r'importa|importam|enseja|ensejam|assenta|assentam|dispoe|dispoem)\b')


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


def _norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s)
                   if not unicodedata.combining(c)).lower()


def _apara_diploma(tail, ini_tail):
    """Corta a cauda do diploma no ponto em que ele acaba de ser nomeado.

    Sem isso, 'art. 123, I, do Codigo Penal Militar (Evento 109 da APM n
    7000237-...)' vira um span so, engolindo a citacao seguinte.

    A regra e o prefixo MAIS LONGO que nomeia um diploma - nao o mais curto:
    'Codigo Penal Militar' tem que ganhar de 'Codigo Penal', que e outro codigo.
    """
    from .canon import codigo_do_diploma
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
        if AUTOS_PROPRIOS.search(esquerda) and ini < corpo_comeca:
            continue  # numero dos autos deste documento, no cabecalho
        d = digitos_de(texto[ini:fim])
        if len(d) == 4 and 1900 <= int(d) <= 2100:
            continue  # ano solto ('Rcl de 2021'), nao numero de processo
        c = (CADEIA_CLASSE.search(esquerda) or ANCORA_TST.search(esquerda)
             or ANCORA_NUCLEO.search(esquerda))
        if c is None and ini >= corpo_comeca and len(digitos_de(m.group())) >= 14:
            c = ANCORA_PROCESSO.search(esquerda)
        if c is None:
            c = ANCORA_SIGLA.search(esquerda)
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
        _add(spans, texto, ini_classe, fim, 'jurisprudencia', 'numerada')

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

    # 5. referencias anaforicas (sem qualquer identificador)
    for m in VAGA_ANAFORICA.finditer(vista):
        t = texto[m.start():m.end()]
        if any(ch.isdigit() for ch in t):
            continue
        if '\n\n' in t:
            continue  # atravessou linha em branco: e titulo de secao, nao citacao
        if t.split()[0].isupper() and len(t.split()[0]) > 3:
            continue  # 'PRECEDENTES INVOCADOS' e cabecalho de secao
        n = _norm(t)
        if not _TEM_ANCORA.search(n):
            continue
        if _VERBO_FINITO.search(n):
            continue
        nucleo = _norm(t).split()[0]
        tipo = 'lei' if nucleo.startswith(('norma', 'legisla', 'disposit',
                                           'artigo', 'artigos', 'preceito')) else 'jurisprudencia'
        _add(spans, texto, m.start(), m.end(), tipo, 'vaga_anaforica')

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
             'vaga_classe_ano_rel': 1, 'numerada': 2, 'vaga_anaforica': 3}
    spans.sort(key=lambda s: (ordem[s['forma']], -(s['fim'] - s['inicio'])))
    saida = []
    for s in spans:
        if any(s['inicio'] < t['fim'] and t['inicio'] < s['fim'] for t in saida):
            continue
        saida.append(s)
    saida.sort(key=lambda s: s['inicio'])
    return saida
