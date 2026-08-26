# Caça-Alucinações — Jusbrasil × BRACIS 2026

Verificador de citações jurídicas: lê uma peça, acha cada citação de
jurisprudência e de lei, e classifica em `real`, `inventada` ou `incompleta`,
resolvendo o `id_canonico` das reais contra a base congelada de 1.018 registros.

## Como rodar

```bash
python -m venv .venv && .venv/bin/pip install pandas
.venv/bin/python run.py dados/txt saida_json --submissao submission.csv
```

`dados/` é um symlink para a pasta do dataset. Passe `--db` para apontar outro
SQLite. O `submission.csv` é gerado chamando o conversor do próprio organizador
(`dados/json_to_submission.py`), para o formato ser o dele e não o nosso.

Avaliação local:

```bash
.venv/bin/python eval.py --conjunto tudo      # dev | holdout | tudo
.venv/bin/python debug_spans.py tudo          # o que perdeu e o que inventou
.venv/bin/python calibra.py                   # regenera cacador/calibracao.py
```

## Resultado

O `kaggle_metric.py` não veio no pacote de dados, então `eval.py` é um proxy
fiel ao enunciado: alinhamento por IoU ≥ 0,5 em codepoints, crédito só com
classe certa — e, nas `real`, com `id_canonico` dentro do conjunto aceito;
nível 1 pesa 1×, nível 2 pesa 2×.

| conjunto | docs | citações | recall de span | precisão | escore ponderado |
|---|---|---|---|---|---|
| dev (`*_001`–`*_007`) | 14 | 119 | 99,2% | 99,2% | **97,7%** |
| holdout (`*_008`–`*_013`) | 12 | 106 | 97,2% | 96,3% | **95,5%** |
| tudo | 26 | 225 | 98,2% | 97,8% | **96,7%** |

Mediana por documento: 100%. 22 dos 26 documentos saem sem nenhum erro.

### Sobre o holdout

As regras foram escritas olhando **só** os 14 documentos de dev. A primeira
medição no holdout deu **75,2%** contra 96,0% no dev — 21 pontos de diferença,
ou seja, overfit. A distância caiu para ~2 pontos depois de três correções, e o
que importa é que nenhuma delas foi remendo de caso: todas eram falta de
cobertura de **forma**.

1. **Vocabulário de classe processual.** Faltavam as formas por extenso
   (`Embargos de Declaração no Recurso em Mandado de Segurança`,
   `Agravo Interno na Suspensão de Liminar e de Sentença`) e o prefixo ordinal
   (`Terceiro AG.REG na Rcl`). É inventário de direito processual, não frase do
   gerador.
2. **Ruído de OCR dentro do número.** `21737l8`, `1.528.4S5`, `170076O`,
   `6G.838`. O enunciado descreve exatamente esse ruído; o extrator é que não
   aceitava letra no meio do run de dígitos.
3. **Núcleo anafórico e âncora de referência.** Faltava `lei` como núcleo, e a
   exigência de "qualificador" foi trocada por **âncora de referência**: uma
   citação vaga ainda aponta para algo (a Corte, a matéria, a origem, a
   espécie). `orientação hoje pacificada` não aponta e deixou de ser extraída.

Depois disso o holdout deixou de ser cego — ele entrou no ciclo de correção. O
número honesto de generalização é a combinação dos dois: as correções subiram
**os dois** conjuntos ao mesmo tempo, que é o sinal de que cobriram forma e não
instância.

## Robustez (é isto que decide o conjunto cego)

O escore acima é o número fácil: o conjunto cego tem o mesmo gerador, mas não
as mesmas superfícies. Dois experimentos medem a margem.

**`stress.py` — ruído de OCR novo.** Injeta ruído do tipo que o enunciado
descreve (dígito nunca vira outro dígito), preservando o comprimento para os
offsets do gabarito continuarem válidos. Os documentos de nível 2 têm ~0,4% de
caracteres corrompidos, então a coluna de 0,5% é o ponto de operação real.

| ruído | escore |
|---|---|
| 0% | 96,7% |
| 0,5% | 93,4% |
| 1% | 92,6% |
| 2% | 90,9% |
| 5% | 79,2% |

**`ablacao.py` — dependência do vocabulário fechado.** Remove uma fração das
88 entradas de `CLASSES` e remede. É o proxy direto do risco "classe processual
que não está na lista".

| removido | com lista fechada apenas | com âncora aberta (atual) |
|---|---|---|
| 10% | 94,9% | **96,2%** |
| 20% | 91,6% | **94,9%** |
| 30% | 89,6% | **94,1%** |
| 50% | 81,0% | **91,4%** |

A âncora aberta corta a perda por vocabulário faltante em ~3×, com o mesmo
escore e a mesma precisão no goldenset. A motivação foi empírica: minerando os
1.018 registros da base, aparecem classes reais que **nem o dev nem o holdout
continham** — `APM` (1.898 ocorrências), `IPM` (890), `IRDR`, `EAREsp`, `RRAg`.
Uma lista escrita à mão é sempre incompleta; o formato, não.

**Auditoria do índice.** A base é congelada e é a mesma do conjunto cego, então
a metade de resolução do problema é verificável hoje, por inteiro. O segmento J
do número CNJ (o ramo da Justiça) é um sinal independente do parser de
cabeçalho: das 517 chaves em formato CNJ, **517 batem com a coluna `tribunal`,
zero divergem**, e os 1.000 acórdãos são alcançáveis pelo índice.

## Como funciona

```
extract.py   texto -> spans        (forma jurídica, não frase do gerador)
canon.py     base  -> índice       (acórdãos por cabeçalho, súmulas, dispositivos)
classify.py  span  -> classe + id  (tabela de decisão do §5 do enunciado)
```

**Extração** ancora em forma, não em frase, e por duas vias: uma lista de
classes processuais conhecidas e — quando ela falha — uma **âncora aberta**
(núcleo nominal `Agravo|Recurso|Embargos|Suspensão|…` com seus modificadores,
ou sigla curta colada no número, com lista negra para `DJe`, `fls.`, `OAB`,
`Lei`, UF). Acha os números primeiro e depois
pergunta se à esquerda há uma classe processual; em paralelo casa súmulas e
dispositivos; por último as referências vagas. Distratores do cabeçalho
(`Processo nº`, `fls.`, OAB, protocolo, `R$`, `%`) são rejeitados por contexto,
e o número dos autos só é distrator dentro do cabeçalho — no corpo, é citação.

**Índice canônico.** Um feito é `(número normalizado, tribunal)` e vale uma
lista de registros, porque o mesmo processo aparece mais de uma vez no acervo.
O número sai do **cabeçalho** do acórdão, com um parser por tribunal: é o que
separa o registro de quem apenas o cita. No TST a âncora é a linha de autuação
(`estes autos de … nº TST-…, em que é Agravante`), não a primeira ocorrência de
`TST-` — as outras são processos citados.

**Classificação** é a tabela do §5, sem invenção: 1 feito → `real`; 0 →
`inventada`; 2+ → `incompleta`; sem identificador suficiente → `incompleta`
antes de consultar a base.

**Calibração.** `confianca` não é chute: `calibra.py` mede a taxa de acerto de
cada par (forma de extração, classe) no goldenset, com suavização de Laplace, e
grava a tabela. Alimenta o bônus de até 10%.

## Riscos conhecidos

- **A parte mais frágil é a referência anafórica** (`vaga_anaforica`), o
  reconhecimento de citações sem nenhum identificador. A regra é sintagma
  nominal fechado + âncora de referência + sem verbo finito. Ela responde por
  3 dos 5 falsos positivos que sobraram: `precedentes aplicáveis à espécie` e
  `acórdão que manteve a condenação imposta na origem` são, na superfície,
  idênticos a citações vagas verdadeiras. Se o escore no conjunto cego vier
  abaixo do esperado, é aqui que se olha primeiro.
- **Desempate entre registros do mesmo feito.** O enunciado diz que
  `id_canonico` é um conjunto e que qualquer id do feito conta. Na prática, 4
  das 96 `real` caem num feito com mais registros do que o gabarito aceita —
  inclusive um par com texto byte a byte idêntico, onde não existe sinal
  nenhum. Adotamos ordem determinística (maior `documento_id`). Ela acerta nos
  dois casos observados, o que com n=2 **não é evidência de nada**.
- **`DISPOSITIVOS` em `canon.py` é uma tabela fixa.** Os 13 registros de lei da
  base trazem o texto do artigo mas não dizem de qual diploma são; o mapa foi
  lido registro a registro. Vale enquanto a cobertura estiver congelada — e
  `BaseCanonica` levanta erro alto se algum id sumir.

## Dois problemas no dataset (perguntar à organização)

1. **`gen_n2_010.txt` não bate com o gabarito.** O `.txt` distribuído perdeu a
   string `"AgInt no "` — exatamente 9 caracteres — antes da citação `g2`. Por
   isso `g2` não é localizável e `g3`–`g7` estão deslocadas 9 codepoints. São 6
   das 225 citações, e nenhuma solução consegue alinhá-las. Nos outros 25
   documentos os 218 spans restantes batem no offset exato.
2. **Duas `real` apontam para o documento que CITA o número, não para o que É o
   processo.** Em `gen_n2_005/g6`, a citação `TST-AgARR-25823-78.2015.5.24.0091`
   tem `id_canonico = 2813052232` (`doc_0710`), cujo número próprio na linha de
   autuação é `TST-Ag-ARR-10132-34.2015.5.03.0018`; quem é o AIRR-25823 é o
   `doc_0729`. Se o gabarito cego foi gerado pelo mesmo processo, isso muda a
   estratégia de desempate.

3. Menor: o `kaggle_metric.py` citado na última linha do PDF como "distribuído
   junto com os dados" não veio no zip.
