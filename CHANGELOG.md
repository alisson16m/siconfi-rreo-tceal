# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
