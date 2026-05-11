# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

---

## [1.5.0] - 2026-05-11

### Added
- Novos módulos `src/siconfi_rgf_client.py` e `src/rgf_report_builder.py`: cliente paralelo e gerador de relatório para o RGF Anexo 01 (Despesa Total com Pessoal).
- Novo módulo `src/rgf_limites.py`: classificador de situação fiscal conforme limites LRF (Arts. 19, 20 e 22 da LC 101/2000) com categorias Normal, Alerta, Prudencial e Máximo.
- Fixtures de PDF para testes: `tests/fixtures/RREO-Agua Branca.pdf` e `tests/fixtures/RREO-Anadia.pdf`.

### Changed
- Aba **Upload de PDF** (Prestações de Contas): campo de texto livre substituído por `st.selectbox` com lista de entes, gerando o nome formal automaticamente (ex.: "Prefeitura Municipal de Maceió - AL").
- Ordem das abas alterada: **📄 Upload de PDF** passa a ser a primeira aba; **📡 Consulta SICONFI** passa para segunda posição.
- Título da aba **Painel de Entregas** renomeado para "🗺️ Painel de Entregas — SICONFI".
- Cabeçalho de `pages/prestacoes_de_contas.py` simplificado para `### 📊 Prestações de Contas` com subtítulo via `st.caption`.
- `app.py`: links de navegação explícitos no sidebar via `st.page_link` (position="hidden" na navegação); título da página RGF renomeado para "Alerta de Despesas com Pessoal".
- Cabeçalho de `pages/02_RGF_Despesa_Pessoal.py` simplificado (removida versão inline do cabeçalho).
- Aviso "Data de envio não disponível" removido da aba de Upload (informação redundante).
- CSS: removida regra `padding-top` do `block-container`.

---

## [1.4.0] - 2026-05-11

### Added
- Nova aba **Upload de PDF**: permite enviar um PDF do RREO Anexo 1 (gerado por sistemas municipais ou extraído do portal SICONFI) e gerar o Apêndice I em XLSX e PDF sem consultar a API.
- Novo módulo `src/pdf_parser.py` com parser linha a linha via `pdfplumber.extract_text()`, suportando dois formatos:
  - PDFs gerados por sistemas municipais (cabeçalho "RREO - ANEXO I").
  - PDFs extraídos do portal SICONFI (cabeçalho "RREO-Anexo 01 | Tabela 1.0").
- Identificação algébrica do AoBim (`AoBim = PA - Saldo`) para lidar com PDFs SICONFI que omitem colunas percentuais quando `NoBim=0`.
- 10 novos testes cobrindo os dois formatos de PDF (89 testes no total).

### Changed
- Sidebar de navegação migrada para `st.navigation()` (Streamlit 1.36+ API):
  - Página principal renomeada de "app" para **Prestações de Contas** na sidebar.
  - Cabeçalho **🏛️ Gerador de Relatórios** com versão exibido no topo da sidebar em todas as páginas.
  - Conteúdo de `app.py` movido para `pages/prestacoes_de_contas.py`; `app.py` agora é entrypoint fino.
- Arquivo `pages/01_Prestacoes_de_Contas.py` removido (era duplicata do conteúdo principal).
- `st.set_page_config()` centralizado em `app.py`; removido de `pages/02_RGF_Despesa_Pessoal.py`.

---

## [1.3.0] - 2026-05-08

### Added
- Nova aba **Painel de Entregas**: tabela-pivot exibindo o status de entrega do RREO 6º Bimestre para todos os 103 entes de Alagoas (Estado + 102 municípios) nos últimos 5 exercícios.
- Filtro de ente fiscal no painel (todos os entes ou ente específico) e filtro de exercícios (multiselect com todos os anos disponíveis pré-selecionados).
- Linha de totais ao fim da tabela indicando quantos entes entregaram por exercício, com destaque visual em azul `#1f4e79`.
- Nova função `fetch_status_todos_entes_ano()` em `siconfi_client.py`: consultas paralelas (10 workers via `ThreadPoolExecutor`) ao endpoint `/extrato_entregas` para todos os entes de um exercício.
- Dependência `pandas==2.3.3` adicionada a `requirements.txt`.

### Changed
- Estrutura do `app.py` migrada para `st.tabs` com duas abas: **📊 Relatório** e **🗺️ Painel de Entregas**.
- CSS das abas reforçado com `!important` para evitar truncamento do texto dos títulos.

---

## [1.2.0] - 2026-05-06

### Added
- Cache de `fetch_data_status()` via `_cached_fetch_status` com `@st.cache_data(ttl=300)`, evitando chamadas redundantes ao endpoint de entregas na mesma sessão.
- Log de tempo total da operação de consulta com `time.perf_counter()` (nível INFO, formato `tempo_total=%.2fs`).

### Changed
- Geração de XLSX e PDF migrada para `io.BytesIO`: `build_xlsx` e `build_pdf` retornam `bytes` diretamente, sem gravação em disco.
- Fluxo de geração de arquivos alterado para sob demanda: o `SiconfiResponse` é armazenado no `session_state`; XLSX e PDF são gerados apenas ao clicar nos botões correspondentes (`st.button` → `st.download_button`), sem nova consulta à API.
- Testes de `build_xlsx` e `build_pdf` atualizados para a nova API que retorna `bytes` (removidas referências a `tmp_path`).

---

## [1.1.0] - 2026-05-06

### Added
- Cache de consultas à API com `@st.cache_data(ttl=300)` para evitar chamadas redundantes na mesma sessão Streamlit.
- Handler global de erros com mensagens institucionais sem exposição de traceback ao usuário; bloco `except Exception` de fallback para erros não previstos.
- Logging estruturado em `app.py` (formato: timestamp, nível, módulo, mensagem) com eventos nos pontos-chave do fluxo (consulta iniciada, itens retornados, XLSX/PDF gerados, erros).
- Documentação das constantes em `report_builder.py`: aliases de coluna da API, sentinelas de linhas calculadas (`__SUM_*`) e linhas de negrito com correspondência ao layout do Anexo 1 STN.
- Arquivo `CLAUDE.md` com guia de contexto e boas práticas para uso do Claude Code no projeto.
- Configurações do Claude Code (`.claude/settings.json` e `.claude/commands/validar-api.md`).

### Changed
- PDF gerado com fonte Times New Roman 10pt; valores zero exibidos como "0,00"; totais e subtotais em negrito; diferenças negativas destacadas em vermelho.
- Ajustes visuais no layout: padding do cabeçalho e sidebar alinhados no modo `wide`.
- Mensagens de erro do Streamlit atualizadas para linguagem institucional.

### Fixed
- Subtítulo da página sem referência redundante ao TCE-AL.
- Direção do indicador de déficit (delta negativo) no widget de métrica do Streamlit.

---

## [1.0.0] - 2026-05-03

### Added
- Cliente HTTP para a API SICONFI com retry exponencial e backoff (`siconfi_client.py`).
- Busca da data de entrega/homologação do RREO via endpoint `/extrato_entregas` (`fetch_data_status`).
- Lista de 102 municípios de Alagoas e Estado de Alagoas com códigos IBGE (`municipios_al.py`).
- Geração de XLSX preenchido via `openpyxl` a partir do template oficial TCE-AL.
- Geração de PDF com ReportLab: Bloco A (Receitas), Bloco B (Despesas) e Bloco C (Resultado Orçamentário).
- Interface Streamlit com sidebar de parâmetros (ente fiscal e exercício), métricas de resumo e botões de download XLSX/PDF.
- Exibição da data de entrega do RREO no SICONFI na interface.
- Seletor de ente com ordenação alfabética e busca; Estado de Alagoas fixo no topo.
- 63 testes automatizados com pytest cobrindo cliente, gerador de relatórios e módulo de municípios.
- Pipeline de CI com GitHub Actions.
- Deploy configurado no Streamlit Cloud.

---

## [0.1.0] - 2026-05-03

### Added
- Project structure initialized.
- `.gitignore`, `VERSION`, `CHANGELOG.md`, `requirements.txt`, `README.md`.
