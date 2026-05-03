# Gerador de Relatório SICONFI — RREO Anexo 1

**Tribunal de Contas do Estado de Alagoas (TCE-AL)**

Ferramenta de apoio à auditoria que automatiza a consulta à [API pública do SICONFI](https://apidatalake.tesouro.gov.br/docs/siconfi/) e gera o **Apêndice I — Balanço Orçamentário (RREO Anexo 1, 6º Bimestre)** em XLSX e PDF para todos os 102 municípios de Alagoas e o Estado.

---

## Funcionalidades

- Consulta automática ao SICONFI via API pública (Secretaria do Tesouro Nacional)
- Seleção do ente fiscal (Estado de Alagoas ou qualquer município alagoano) e do exercício
- Geração de relatório XLSX a partir do modelo oficial do TCE-AL
- Geração de relatório PDF com tabelas de receitas e despesas formatadas
- Exibição de métricas resumo: Receitas Realizadas, Despesas Empenhadas e Resultado Orçamentário
- Data de entrega do RREO no SICONFI
- Download dos arquivos gerados com um clique

## Uso local

### Pré-requisitos

- Python 3.11+
- `pip`

### Instalação

```bash
# 1. Clone o repositório
git clone <URL_DO_REPOSITORIO>
cd siconfi-rreo-tceal

# 2. Crie e ative o ambiente virtual
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt

# Para rodar os testes, instale também as dependências de desenvolvimento:
pip install -r dev-requirements.txt
```

### Executar o app

```bash
python -m streamlit run app.py
```

Acesse `http://localhost:8501` no navegador.

### Executar os testes

```bash
python -m pytest --tb=short -q
```

## Deploy no Streamlit Community Cloud

1. Faça um fork deste repositório ou envie para um repositório público no GitHub.
2. Acesse [share.streamlit.io](https://share.streamlit.io) e clique em **New app**.
3. Selecione o repositório, a branch `main` e o arquivo `app.py`.
4. Clique em **Deploy**. O Streamlit Cloud instalará as dependências de `requirements.txt` automaticamente com Python 3.11.

## Estrutura do projeto

```
siconfi-rreo-tceal/
├── app.py                        # Aplicação Streamlit (ponto de entrada)
├── requirements.txt              # Dependências de produção
├── dev-requirements.txt          # Dependências de desenvolvimento (inclui pytest)
├── .python-version               # Versão do Python (3.11)
├── .streamlit/
│   └── config.toml               # Tema e configurações do Streamlit
├── .github/
│   └── workflows/
│       └── ci.yml                # Pipeline de CI (GitHub Actions)
├── src/
│   ├── siconfi_client.py         # Cliente da API SICONFI com retry
│   ├── report_builder.py         # Geração de XLSX e PDF
│   └── municipios_al.py          # Lista de entes de Alagoas (102 municípios + estado)
├── templates/
│   ├── Modelo_Relatorio_Apendice_1.xlsx          # Template vazio
│   └── Modelo_Relatorio_Apendice_1_Arapiraca.xlsx # Template de referência preenchido
└── tests/
    ├── fixtures/
    │   └── arapiraca_2025.json   # Fixture de resposta da API (Arapiraca/2025)
    ├── test_siconfi_client.py
    ├── test_municipios_al.py
    └── test_report_builder.py
```

## API utilizada

`GET https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo`

Parâmetros fixos: `nr_periodo=6`, `co_tipo_demonstrativo=RREO`, `no_anexo=RREO-Anexo 01`, `co_poder=E`.

---

> **Aviso**: Esta ferramenta consome dados públicos da API do SICONFI (Secretaria do Tesouro Nacional). Não substitui análise técnica nem constitui fonte oficial para fins legais.
