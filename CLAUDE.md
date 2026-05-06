# CLAUDE.md — siconfi-rreo-tceal

## Contexto institucional

Ferramenta de apoio à auditoria externa do Tribunal de Contas do Estado de
Alagoas (TCE-AL), desenvolvida pela Diretoria de Coordenação de Técnicos (DCT).
Automatiza a consulta à API pública do SICONFI e gera o Apêndice I —
Balanço Orçamentário (RREO Anexo 1) em XLSX e PDF para os 102 municípios de
Alagoas e o Estado.

## Stack e dependências

- Python 3.11
- Streamlit — interface web
- openpyxl — geração e preenchimento de XLSX a partir do template oficial
- reportlab — geração de PDF com tabelas formatadas
- requests — cliente HTTP com retry para a API do SICONFI
- pytest — testes automatizados

## Estrutura do projeto

```
siconfi-rreo-tceal/
├── app.py                    # Ponto de entrada Streamlit
├── src/
│   ├── siconfi_client.py     # Cliente da API SICONFI (fetch + exceções)
│   ├── report_builder.py     # Geração de XLSX e PDF
│   └── municipios_al.py      # Lista de entes (102 municípios + Estado)
├── templates/                # Templates XLSX oficiais do TCE-AL
├── tests/
│   ├── fixtures/             # Respostas mockadas da API (JSON)
│   └── test_*.py             # Testes unitários por módulo
├── .claude/
│   └── commands/             # Skills (comandos personalizados) do Claude Code
├── .github/workflows/ci.yml  # Pipeline de CI (GitHub Actions)
└── VERSION                   # Versão atual do app
```

## Parâmetros fixos da API SICONFI

Endpoint: `GET https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo`

Parâmetros fixos:
- `nr_periodo=6` (6º Bimestre)
- `co_tipo_demonstrativo=RREO`
- `no_anexo=RREO-Anexo 01`
- `co_poder=E`

Parâmetros variáveis:
- `an_exercicio` — ano do exercício (fornecido pelo usuário)
- `id_ente` — código do ente fiscal (extraído de `municipios_al.py`)

## Convenções de código

- **Nunca** hardcode `id_ente`: sempre usar a lista `ENTES_AL` em `municipios_al.py`
- **Nunca** hardcode caminhos de arquivo: usar `pathlib.Path`
- Exceções da API devem usar exclusivamente as classes em `siconfi_client.py`:
  `SiconfiEmptyResponseError`, `SiconfiNetworkError`, `SiconfiInvalidJsonError`
- Tipagem estrita com type hints em todas as funções públicas
- Docstrings obrigatórias em funções e classes públicas
- Formatação monetária sempre via `_fmt_brl()` em `app.py`

## Regras para alterações no código

1. Antes de qualquer edição, rodar `.venv\Scripts\python.exe -m pytest --tb=short -q` e confirmar que todos os testes passam
2. Após qualquer edição em `src/`, rodar os testes novamente
3. Ao adicionar suporte a novo demonstrativo: seguir o padrão de `fetch_rreo_anexo1` e `build_xlsx`/`build_pdf` como referência
4. Ao adicionar novo município ou ente: editar apenas `municipios_al.py`
5. Não modificar os arquivos de template XLSX em `templates/` — eles são modelos oficiais do TCE-AL

## Checklist antes de commit

- [ ] `.venv\Scripts\python.exe -m pytest --tb=short -q` passa sem erros
- [ ] Sem valores numéricos ou strings de configuração hardcoded
- [ ] Sem imports não utilizados
- [ ] Docstrings presentes em funções públicas novas ou modificadas
- [ ] `VERSION` atualizado se houver mudança funcional relevante
- [ ] `CHANGELOG.md` atualizado com resumo da alteração

## Fixture de referência

O município de **Arapiraca** (fixture em `tests/fixtures/arapiraca_2025.json`)
é o caso de teste de referência para o exercício 2025. Use-o para validações
e como base ao criar novas fixtures.

## Escopo de leitura por tipo de tarefa

Leia **apenas** os arquivos relevantes para a tarefa em execução.
Nunca carregue o projeto inteiro sem necessidade explícita.

| Tipo de tarefa | Arquivos a ler |
|---|---|
| Alteração na integração com a API | `src/siconfi_client.py`, `tests/test_siconfi_client.py` |
| Alteração na geração de relatórios | `src/report_builder.py`, `tests/test_report_builder.py` |
| Alteração na interface (UI) | `app.py` |
| Alteração na lista de municípios | `src/municipios_al.py`, `tests/test_municipios_al.py` |
| Validação geral / CI | Todos os arquivos de `tests/` |

Nunca ler os arquivos em `templates/` salvo solicitação explícita —
são modelos binários XLSX que não contribuem para o entendimento do código.

## Boas práticas para uso eficiente de contexto

- Prefira sessões curtas e escopadas a sessões longas com múltiplas tarefas
- Ao receber uma tarefa pontual, confirme o escopo antes de ler arquivos:
  pergunte "qual arquivo ou módulo está envolvido?" se não estiver claro
- Ao exibir resultados de scripts Python, mostre apenas contagens e status —
  nunca imprima o conteúdo completo de listas, dicionários ou respostas da API
- Ao reportar erros, inclua apenas as linhas relevantes do traceback (máximo 10 linhas)
- Evite repetir no texto de resposta o conteúdo de arquivos já lidos —
  referencie pelo nome do arquivo e linha, não transcreva
