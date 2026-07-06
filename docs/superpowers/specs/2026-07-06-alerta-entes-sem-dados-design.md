# Design: seção de entes sem dados no Termo de Alerta

## Contexto

`gerar_alerta_docx` (em `src/rgf_report_builder.py`) gera o Termo de Alerta de
Despesa com Pessoal (Executivo/Legislativo) a partir de um template `.docx`
institucional, populando a tabela de entes críticos (situação Alerta,
Prudencial ou Máximo). O documento não informa, atualmente, quais entes
deixaram de enviar dados ao SICONFI no período consultado — essa informação
já existe em `resultado.entes_sem_dados`, mas só é usada em
`gerar_relatorio_docx` (Seção 3).

## Objetivo

Adicionar ao final do Termo de Alerta (após a tabela de entes críticos) um
parágrafo introdutório seguido da lista numerada dos entes que não enviaram
dados ao SICONFI até a data de extração.

## Comportamento

- Se `resultado.entes_sem_dados` estiver vazio, nenhuma seção é adicionada
  (não há texto alternativo).
- Se houver entes sem dados, adicionar:
  1. Um parágrafo com o texto:
     `"Relacionam-se abaixo os entes que, até a data de extração dos dados
     ({data_str}), não haviam enviado ao SICONFI as informações referentes à
     Despesa com Pessoal (RGF Anexo 01) no período consultado:"`
     — usando a mesma `data_str` já calculada em `gerar_alerta_docx` (parâmetro
     `data_extracao` ou data atual).
  2. Uma lista numerada, uma linha por ente: `"{n}. {nome}"`, na ordem em que
     aparecem em `resultado.entes_sem_dados`.

## Localização da alteração

Inserir a nova lógica em `gerar_alerta_docx`, logo após o laço que popula a
tabela de entes críticos (`src/rgf_report_builder.py`, após a linha do `for
ente in sorted(criticos, ...)`) e antes de `doc.save(buf)`. O documento de
alerta não possui rodapé legal (`_rodape_legal` só é chamado em
`gerar_relatorio_docx`), então a nova seção fica no final do documento.

## Testes

Atualizar/criar testes em `tests/test_rgf_report_builder.py` (ou arquivo
equivalente) cobrindo:
- Alerta gerado com `entes_sem_dados` não vazio → parágrafo introdutório e
  lista numerada presentes no `.docx` resultante, com os nomes corretos.
- Alerta gerado com `entes_sem_dados` vazio → nenhuma seção extra adicionada.

## Fora de escopo

- Não altera `gerar_relatorio_docx` nem sua Seção 3 existente.
- Não altera os templates `.docx` em `templates/alertas/`.
