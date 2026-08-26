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

**`avalia_acervo.py` — o acervo como conjunto de teste.** Os 1.018 registros da
base são milhares de citações reais em prosa jurídica de verdade, não sintética,
e ninguém precisa anotá-las: toda ocorrência, no corpo de um acórdão, de um
número que resolve para *outro* feito do acervo é uma citação inegável. São 627,
quase 3× o goldenset. Audita também o **link**, com um teste independente do
parser — o registro resolvido tem que ser aquele cujo próprio cabeçalho carrega
o número citado. Foi essa suíte que achou as listas enumeradas, o sufixo de
recurso, e `Processo nº <CNJ>` no corpo.

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
número e aceita só o documento em que ele aparece na região do cabeçalho —
janela por tribunal, porque no TST e no STM a autuação fica a milhares de
caracteres do início. Sabotando o parser de cabeçalho de propósito: com metade
dos registros quebrados, 92,5% das citações ainda resolvem.

**Classificação** é a tabela do §5, sem invenção: 1 feito → `real`; 0 →
`inventada`; 2+ → `incompleta`; sem identificador suficiente → `incompleta`
antes de consultar a base. Um diploma **nomeado** mas fora da cobertura
(`Código de Trânsito Brasileiro`) é `inventada`, não `incompleta`: dá para
buscar, só não existe no acervo.

**Confiança** vale até 10% do escore e não é chute. `calibra.py` treina uma
regressão logística sobre features do próprio processo de decisão — quantos
feitos casaram, se a pista de tribunal confirmou, formato do número, ruído de
OCR no span, e qual âncora reconheceu a citação — em ~3.600 exemplos, com
validação cruzada agrupada por documento:

|  | ECE | Brier | logloss | AUC |
|---|---|---|---|---|
| constante 0,90 | 0,0915 | 0,0168 | 0,1241 | 0,305 |
| tabela por forma+classe | 0,0026 | 0,0080 | 0,0426 | 0,765 |
| regressão logística | **0,0009** | 0,0081 | **0,0416** | **0,767** |

O treino usa numpy; a inferência é um produto interno, então `run.py` continua
só com biblioteca padrão.

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
