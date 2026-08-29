# Manifesto do modelo

**Modelos de linguagem utilizados: nenhum.**

A solução é simbólica. Não há pesos a declarar, nenhum identificador do Hugging
Face, nenhuma revisão a fixar, e nenhum modelo *gated*. O caminho de inferência
é composto de expressões regulares que reconhecem forma jurídica, um índice
construído sobre a base canônica fornecida pela organização, e a tabela de
decisão do enunciado.

Duas consequências para a verificação:

- **Execução offline.** O container não faz nenhuma chamada de rede, nem para
  baixar pesos nem em tempo de execução. Ele pode rodar com `--network none`.
- **Determinismo.** Não há amostragem, temperatura ou semente no caminho de
  inferência: a mesma entrada produz a mesma saída, byte a byte. `PYTHONHASHSEED`
  está fixado na imagem para eliminar a única fonte de variação restante, que
  seria a ordem de iteração de conjuntos.

O único componente ajustado a partir de dados é a constante de confiança, um
número escalar versionado em `cacador/calibracao.py` e regenerável com
`python -m ferramentas.confianca`.

## Envelope de execução

| recurso | teto do desafio | uso medido |
|---|---|---|
| GPU | 24 GB | nenhuma |
| RAM | 32 GB | ~130 MB |
| tempo por documento | 60 s (média) | ~0,05 s |
| tempo total do teste | 4 h | segundos |
