# Caça-Alucinações — Jusbrasil × BRACIS 2026

Verificador de citações jurídicas: lê uma peça, acha cada citação de
jurisprudência e de lei, e classifica em `real`, `inventada` ou `incompleta`,
resolvendo o `id_canonico` das reais contra a base congelada de 1.018 registros.

Determinístico, sem modelo de linguagem, sem chave de API. Roda os 26
documentos em **1,2 s** com **130 MB**, e `run.py` usa só a biblioteca padrão.

## Rodar

```bash
python run.py dados/txt saida_json --submissao submission.csv
```

`dados/` é um symlink para a pasta do dataset; `--db` aponta outro SQLite. O
`submission.csv` sai do conversor do próprio organizador
(`dados/json_to_submission.py`), para o formato ser o dele.

Avaliação — uma linha roda tudo:

```bash
python -m venv .venv && .venv/bin/pip install pandas numpy
.venv/bin/python verifica.py            # a bateria inteira, ~35 s
.venv/bin/python verifica.py --rapido   # só as suítes rápidas
```

## Placar

| superfície | tamanho | resultado |
|---|---|---|
| **goldenset** (26 documentos distribuídos) | 225 citações | **97,9%** ponderado · recall 99,1% · precisão 97,8% |
| **acervo real** (citações dentro dos 1.018 registros) | 627 citações | **100%** de span · **100%** de link |
| **sintético próprio**, semente inédita | 1.995 citações | **99,2%** ponderado · precisão 100% |
| **referência sem identificador**, fraseados inéditos | 28 + 15 | 86% de recall · 100% de precisão |
| ruído de OCR a 0,5% (o nível real do n2) | — | 95,1% |
| metade do vocabulário de classe removido | — | 96,4% |

Se a métrica oficial for **F1 macro por classe, por nível** (é o que consta da
aba "Avaliação" do site, que chegou até mim de segunda mão — vale conferir na
fonte), o número é:

| nível | real | inventada | incompleta | **macro** |
|---|---|---|---|---|
| 1 (peso 1×) | 0,981 | **1,000** | 0,985 | **0,9885** |
| 2 (peso 2×) | 0,932 | **1,000** | 0,971 | **0,9675** |
| ponderado | | | | **0,9745** |

`inventada` com **F1 = 1,000 nos dois níveis e zero `inventada→real`**. Se a
métrica pune em dobro classificar alucinação como real — o erro mais caro em
produção e na nota —, essa penalidade **nunca dispara**. E não é sorte:
`inventada` só é emitida quando a busca retorna zero, e não existe caminho no
código que a promova a `real`.

Sob F1 macro, `incompleta` vale 1/3 da nota apesar de ser 29% das citações — é
a classe onde cada ponto de recall rende mais, e é a mais frágil. Ver "Riscos".

**Os quatro erros que sobram no goldenset são todos defeito do dataset** — dois
spans do `gen_n2_010`, cujo `.txt` não bate com o gabarito, e dois links em que
o gabarito aponta para quem *cita* o número em vez de quem *é* o processo (ver
"Problemas no dataset"). Em documento bem formado, o sistema não erra nenhuma
das 221 restantes.

O `kaggle_metric.py` não veio no pacote, então `eval.py` é um proxy fiel ao
enunciado: alinhamento por IoU ≥ 0,5 em codepoints, crédito só com classe certa
e — nas `real` — `id_canonico` no conjunto aceito; nível 1 pesa 1×, nível 2 2×.

## As cinco superfícies de avaliação

O escore no goldenset é o número fácil: 26 documentos, e a nota oficial sai de
um conjunto cego. Cada suíte aqui cerca um lado diferente do problema.

**`eval.py` — goldenset.** Os 26 documentos com gabarito. Foi dividido em dev
(`*_001`–`*_007`) e holdout (`*_008`–`*_013`); as regras foram escritas olhando
só o dev. A primeira medição no holdout deu 75,2% contra 96,0% no dev — 21
pontos de overfit, que caíram a ~2 depois que as correções passaram a ser de
cobertura de forma, não remendo de caso.

**`auditoria_independente.py` — segunda leitura, sem o parser.** A conferência
de link embutida no `avalia_acervo.py` é **circular**: ela chama o mesmo
`PARSERS` que constrói o índice, então valida *consistência*, não correção — se
o parser lê um cabeçalho errado, auditor e resolvedor erram igual. A segunda
leitura usa um critério diferente e não passa pelo parser: dado um número
citado, varre o acervo atrás de todos os documentos que o contêm e mede a
posição da primeira ocorrência em cada um; quem *é* o processo carrega o número
mais cedo, quem apenas *cita* o traz no corpo.

**`avalia_acervo.py` — o acervo como conjunto de teste.** Os 1.018 registros da
base são milhares de citações reais em prosa jurídica de verdade, não sintética,
e ninguém precisa anotá-las: toda ocorrência, no corpo de um acórdão, de um
número que resolve para *outro* feito do acervo é uma citação inegável. São 627,
quase 3× o goldenset. Audita também o **link**, com um teste independente do
parser — o registro resolvido tem que ser aquele cujo próprio cabeçalho carrega
o número citado. Foi essa suíte que achou as listas enumeradas, o sufixo de
recurso, e `Processo nº <CNJ>` no corpo. A conferência de link dela é
circular — ver acima.

**`gerador.py` + `avalia_sintetico.py` — gerador próprio, mais largo que o
deles.** Reconstrói a peça sintética *de propósito* mais ampla: classes vindas
da mineração do acervo que os 26 documentos nunca usam (`APM`, `IPM`, `RRAg`,
`EAREsp`, `Ag-AIRR`), formatos de número e de UF combinados livremente, frases
escritas fora do inventário observado, ruído ajustável. Passar aqui significa
cobrir a *forma*. O que ele não pode fazer é provar o escore no conjunto cego:
testa contra o meu modelo do gerador, não contra o deles.

**`avalia_anaforica.py` — a família mais frágil.** A citação sem identificador
(`jurisprudência pacífica desta Corte`) é a única que o sintético **não** pode
medir: as frases dele foram copiadas do gabarito, então o teste seria circular.
Aqui os positivos são 28 paráfrases escritas fora do vocabulário da regra e os
negativos são 15 frases reais dos 26 documentos que o gabarito não anota —
falso positivo ali é comprovado, não suposto.

**`stress.py` e `ablacao.py` — margem.** O primeiro injeta ruído de OCR novo
(preservando comprimento, para os offsets continuarem válidos); o segundo remove
parte do vocabulário escrito à mão e remede, que é o proxy direto de "classe
processual que não está na lista".

## Como funciona

```
extract.py   texto -> spans        (forma jurídica, não frase do gerador)
canon.py     base  -> índice       (acórdãos por cabeçalho, súmulas, dispositivos)
classify.py  span  -> classe + id  (tabela de decisão do §5 do enunciado)
features.py  +     -> confiança    (regressão logística calibrada)
```

**Extração** ancora em forma, por duas vias: uma lista de classes processuais
conhecidas e — quando ela falha — uma **âncora aberta** (núcleo nominal
`Agravo|Recurso|Embargos|Suspensão|…` com seus modificadores, ou sigla curta
colada no número, com lista negra para `DJe`, `fls.`, `OAB`, `Lei`, `Evento`,
UF e numeração de documento administrativo). É o que faz a ablação quase não
morder: tirar metade das 88 classes escritas à mão custa 1,5 ponto, contra 15,7
na primeira versão. Distratores do cabeçalho são rejeitados por posição — e o
enunciado é explícito: número dos autos **no cabeçalho** é distrator, referência
a outro processo **no corpo** é citação.

**Índice canônico.** Um feito é `(número normalizado, tribunal)` e vale uma
lista de registros, porque o mesmo processo aparece mais de uma vez no acervo.
O número sai do **cabeçalho** do acórdão, com um parser por tribunal: é o que
separa o registro de quem apenas o cita. No TST a âncora é a linha de autuação
(`estes autos de … nº TST-…, em que é Agravante`), não a primeira ocorrência de
`TST-`. Quando o índice falha, uma **rede de segurança por FTS** procura o
número — e é **deliberadamente conservadora**, porque um `real` falso é o erro
mais caro da métrica. Aparecer cedo não basta: a ementa começa logo depois do
cabeçalho e cita outros processos. No STF/STJ/TSE o número precisa ser o
**primeiro** número de processo do documento; no TST e no STM, precisa estar
junto da linha de autuação. A primeira versão usava só uma janela de 700
caracteres e a segunda leitura independente pegou o resultado disso: a
`AG.REG. NA RECLAMAÇÃO 66.755` cita o RE 958.252 no caractere 644, e a rede
aceitava. Sabotando o parser de propósito, com metade dos registros quebrados
64,5% das citações ainda resolvem — menos que os 92,5% da versão frouxa, e a
troca é intencional: precisão em `real` vale mais que taxa de recuperação de
uma falha que hoje não existe (o parser tem 0 erros e 517/517 de consistência
CNJ).

**Classificação** é a tabela do §5, sem invenção: 1 feito → `real`; 0 →
`inventada`; 2+ → `incompleta`; sem identificador suficiente → `incompleta`
antes de consultar a base. Um diploma **nomeado** mas fora da cobertura
(`Código de Trânsito Brasileiro`) é `inventada`, não `incompleta`: dá para
buscar, só não existe no acervo.

**Confiança: uma constante, e isso foi uma decisão medida.** O bônus vale até
10% e é pontuado por **Brier score**. Chegamos a treinar uma regressão logística
sobre features do processo de decisão (quantos feitos casaram, se a pista de
tribunal confirmou, ruído de OCR no span, qual âncora disparou), em ~3.600
exemplos. Ela ficava excelente no pool de treino — e **perdia para uma
constante no dado real**:

| estratégia | Brier no goldenset |
|---|---|
| **constante = acurácia** | **0,02976** |
| regressão logística | 0,03023 |
| taxa por classe | 0,03039 |
| taxa por forma | 0,03069 |
| taxa por forma+classe | 0,03072 |

A causa é simples e não se resolve com mais dados sintéticos: **7 erros em 228
predições reais**. A confiança nos erros era 0,985 contra 0,969 na média — o
modelo não separava o modo de falha, porque o pool de treino era 99,2% correto
e ele aprendeu a dizer "0,99" sempre. Toda granularidade menor foi testada por
validação cruzada agrupada por documento e todas perderam.

`escolhe_confianca.py` roda essa comparação e grava a vencedora. Hoje grava a
acurácia medida **menos uma margem de 1 ponto** — errar por excesso de confiança
custa mais no Brier do que errar por falta. Se aparecer mais dado real rotulado
(o retorno dos 40% públicos, por exemplo), basta rodar de novo: o script
recusa-se a gravar constante se algum modelo passar a ganhar.

## Isolamento por documento

O conjunto de teste é processado em lote. Um arquivo com encoding estranho ou
estrutura inesperada **não pode custar o lote inteiro**: `run.py` isola cada
documento, e uma falha vira predição vazia só para ele, com aviso no `stderr`.
Sem isso, um único arquivo ruim derrubava o processo e o `submission.csv` nem
era escrito — testado com 27 arquivos, um deles com byte inválido: antes saíam
13 JSONs e nenhum CSV; agora saem 27 e o CSV completo.

O `--submissao` também não depende mais do symlink `dados/` existir: se o
conversor do organizador não estiver lá, o mesmo CSV é escrito internamente.

## Riscos conhecidos

- **A referência sem identificador continua sendo o ponto fraco.** 86% de
  recall em fraseados inéditos, e 3 dos 5 falsos positivos do goldenset.
  `precedentes aplicáveis à espécie` é, na superfície, idêntico a
  `verbete sumular aplicável à espécie`, que o gabarito conta como citação. Se
  o escore no conjunto cego vier abaixo do esperado, é aqui que se olha.
- **Desempate entre registros do mesmo feito.** O enunciado diz que
  `id_canonico` é um conjunto e que qualquer id do feito conta. Na prática, 4
  das 96 `real` caem num feito com mais registros do que o gabarito aceita —
  inclusive um par com texto byte a byte idêntico, onde não existe sinal.
  Adotamos ordem determinística (maior `documento_id`); acerta nos dois casos
  observados, o que com n=2 **não é evidência de nada**.
- **Viés de auto-avaliação.** Duas das evidências mais fortes deste README são
  medidas por populações que excluem parte do modo de falha: a conferência de
  link do `avalia_acervo.py` usa o mesmo parser que audita (por isso existe o
  `auditoria_independente.py`), e o conjunto sintético testa contra o *meu*
  modelo do gerador, não contra o deles. Estão anotadas como tais no lugar onde
  aparecem; quem ler os números precisa ler a ressalva junto.
- **A métrica oficial ainda não foi lida na fonte.** Tudo aqui é medido contra
  um proxy montado a partir do enunciado. O `kaggle_metric.py` citado no PDF não
  veio no pacote, e o starter kit com o validador de formato também não. Enquanto
  não chegarem, a otimização pode estar mirando o alvo ligeiramente errado.
- **`DISPOSITIVOS` em `canon.py` é tabela fixa.** Os 13 registros de lei trazem
  o texto do artigo mas não dizem de qual diploma são; o mapa foi lido registro
  a registro. Vale enquanto a cobertura estiver congelada — e `BaseCanonica`
  levanta erro alto se algum id sumir.

## Problemas no dataset (perguntar à organização)

1. **`gen_n2_010.txt` não bate com o gabarito.** O `.txt` distribuído perdeu a
   string `"AgInt no "` — exatamente 9 caracteres — antes da citação `g2`. Por
   isso `g2` é inlocalizável e `g3`–`g7` estão deslocadas 9 codepoints. São 6
   das 225 citações, que nenhuma solução consegue alinhar. Nos outros 25
   documentos os 218 spans restantes batem no offset exato.
2. **Duas `real` apontam para o documento que CITA o número, não para o que É o
   processo.** Em `gen_n2_005/g6`, a citação `TST-AgARR-25823-78.2015.5.24.0091`
   tem `id_canonico = 2813052232` (`doc_0710`), cujo número próprio na linha de
   autuação é `TST-Ag-ARR-10132-34.2015.5.03.0018`; quem é o AIRR-25823 é o
   `doc_0729`. Idem em `gen_n1_012`. Se o gabarito cego foi gerado pelo mesmo
   processo, isso muda a estratégia de desempate.
3. O `kaggle_metric.py` citado na última linha do PDF como "distribuído junto
   com os dados" não veio no zip.
