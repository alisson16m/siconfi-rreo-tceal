"""Gerador de Apêndice I — RREO Anexo 1 · TCE-AL"""

import logging
import pathlib
import tempfile
import unicodedata
from datetime import datetime

import streamlit as st

from src.municipios_al import ENTES_AL, Ente
from src.report_builder import _AR, _EM, _g, _pivot_items, build_pdf, build_xlsx
from src.siconfi_client import (
    SiconfiEmptyResponseError,
    SiconfiInvalidJsonError,
    SiconfiNetworkError,
    SiconfiResponse,
    fetch_data_status,
    fetch_rreo_anexo1,
)

_VERSION = pathlib.Path(__file__).parent.joinpath("VERSION").read_text(encoding="utf-8").strip()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Constantes internas da API usadas para calcular as métricas de resumo ─────
_CONTAS_RECEITA = ("ReceitasCorrentes", "ReceitasCorrentesIntra", "ReceitasDeCapital")
_CONTAS_DESPESA = ("DespesasCorrentes", "DespesasDeCapital")

# ── Chaves de session_state ────────────────────────────────────────────────────
_SK_XLSX     = "xlsx_bytes"
_SK_PDF      = "pdf_bytes"
_SK_NOME     = "report_nome"
_SK_ANO      = "report_ano"
_SK_RECEITAS = "metric_receitas"
_SK_DESPESAS = "metric_despesas"
_SK_DATA     = "metric_data_status"


def _slug(nome: str) -> str:
    normalizado = unicodedata.normalize("NFKD", nome)
    ascii_nome = normalizado.encode("ascii", "ignore").decode("ascii")
    return ascii_nome.replace(" ", "_").replace("/", "-")


def _fmt_brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_data_status(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%d/%m/%Y às %H:%M:%S")
    except ValueError:
        return iso


# TTL de 300s: evita chamadas redundantes na mesma sessão sem risco de dados desatualizados
@st.cache_data(ttl=300)
def _cached_fetch(id_ente: str, exercicio: int, esfera: str) -> SiconfiResponse:
    return fetch_rreo_anexo1(id_ente=id_ente, exercicio=exercicio, esfera=esfera)


# ── Configuração da página ────────────────────────────────────────────────────

st.set_page_config(
    page_title="Gerador de Relatórios do SICONFI",
    page_icon="🏛️",
    layout="wide",
)

st.markdown(
    """<style>
    div.block-container { padding-top: 1.5rem; }
    section[data-testid="stSidebar"] > div:first-child { padding-top: 3rem; }
    </style>""",
    unsafe_allow_html=True,
)

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### Gerador de Relatórios do SICONFI")
    st.caption("Diretoria de Coordenação de Técnicos (DCT)")
    st.caption(f"Versão {_VERSION}")
    st.divider()
    st.markdown("**⚙️ Parâmetros**")

    estado = next(e for e in ENTES_AL if e.esfera == "E")
    municipios = sorted((e for e in ENTES_AL if e.esfera == "M"), key=lambda e: e.nome)
    entes_ordenados: list[Ente] = [estado] + municipios

    ente: Ente = st.selectbox(
        "Ente fiscal",
        options=entes_ordenados,
        format_func=lambda e: e.nome,
        index=0,
    )

    ano_atual = datetime.now().year
    exercicio: int = st.selectbox(
        "Exercício",
        options=list(range(ano_atual - 1, 2019, -1)),
        index=0,
    )

    gerar = st.button("🔄 Gerar Relatório", type="primary", use_container_width=True)

# ── Cabeçalho ─────────────────────────────────────────────────────────────────

st.title("Dados de Execução Orçamentária")
st.caption(
    "Dados com base no Balanço Orçamentário — Anexo I do Relatório Resumido "
    "de Execução Orçamentária (RREO) do 6º Bimestre"
)
st.divider()

# ── Invalida cache quando os parâmetros mudam ─────────────────────────────────

if (
    st.session_state.get(_SK_NOME) != ente.nome
    or st.session_state.get(_SK_ANO) != exercicio
):
    for k in (_SK_XLSX, _SK_PDF, _SK_RECEITAS, _SK_DESPESAS, _SK_DATA):
        st.session_state.pop(k, None)

# ── Geração do relatório ──────────────────────────────────────────────────────

if gerar:
    with st.spinner(f"Consultando SICONFI — {ente.nome} / {exercicio}..."):
        try:
            logger.info("Consulta iniciada: ente=%s, exercicio=%d", ente.id_ente, exercicio)
            response = _cached_fetch(
                id_ente=ente.id_ente,
                exercicio=exercicio,
                esfera=ente.esfera,
            )
            logger.info("Consulta concluída: %d itens retornados", len(response.items))
        except SiconfiEmptyResponseError:
            st.warning(
                "Nenhum dado encontrado para o ente e exercício selecionados. "
                "Verifique se o demonstrativo foi publicado no SICONFI."
            )
            st.stop()
        except SiconfiNetworkError as e:
            st.error("Falha na comunicação com a API do SICONFI. Verifique sua conexão e tente novamente.")
            logger.error("SiconfiNetworkError: %s", e)
            st.stop()
        except SiconfiInvalidJsonError as e:
            st.error("A API do SICONFI retornou uma resposta inesperada. Tente novamente em instantes.")
            logger.error("SiconfiInvalidJsonError: %s", e)
            st.stop()
        except Exception as e:
            st.error("Ocorreu um erro inesperado. Tente novamente ou entre em contato com o suporte técnico.")
            logger.exception("Erro não tratado: %s", e)
            st.stop()

        response.data_status = fetch_data_status(ente.id_ente, exercicio)

        pivot = _pivot_items(response.items)
        total_receitas = sum(_g(pivot, c, _AR) for c in _CONTAS_RECEITA)
        total_despesas = sum(_g(pivot, c, _EM) for c in _CONTAS_DESPESA)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            xlsx_path = build_xlsx(response, tmp_path / "report.xlsx")
            logger.info("Relatório XLSX gerado: %s", xlsx_path.name)
            pdf_path  = build_pdf(response, tmp_path / "report.pdf")
            logger.info("Relatório PDF gerado: %s", pdf_path.name)
            st.session_state[_SK_XLSX] = xlsx_path.read_bytes()
            st.session_state[_SK_PDF]  = pdf_path.read_bytes()

        st.session_state[_SK_NOME]     = ente.nome
        st.session_state[_SK_ANO]      = exercicio
        st.session_state[_SK_RECEITAS] = total_receitas
        st.session_state[_SK_DESPESAS] = total_despesas
        st.session_state[_SK_DATA]     = response.data_status

# ── Resultados ────────────────────────────────────────────────────────────────

if _SK_XLSX in st.session_state:
    nome = st.session_state[_SK_NOME]
    ano  = st.session_state[_SK_ANO]
    data = st.session_state[_SK_DATA]
    rec  = st.session_state[_SK_RECEITAS]
    desp = st.session_state[_SK_DESPESAS]
    res  = rec - desp

    st.success(f"✅ Relatório gerado: **{nome}** — exercício **{ano}**")

    if data:
        st.info(f"📅 Data de envio dos dados ao SICONFI: `{_fmt_data_status(data)}`")
    else:
        st.warning("⚠️ Data de envio dos dados não encontrada no SICONFI.")

    col_r, col_d, col_res = st.columns(3)
    col_r.metric("Receitas Realizadas", _fmt_brl(rec))
    col_d.metric("Despesas Empenhadas", _fmt_brl(desp))
    col_res.metric(
        "Resultado Orçamentário",
        _fmt_brl(abs(res)),
        delta="SUPERÁVIT" if res >= 0 else "DÉFICIT",
        delta_color="normal",
    )

    st.divider()

    file_slug = _slug(nome)
    col_xlsx, col_pdf = st.columns(2)
    with col_xlsx:
        st.download_button(
            label="📥 Baixar XLSX",
            data=st.session_state[_SK_XLSX],
            file_name=f"Apendice_I_{file_slug}_{ano}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with col_pdf:
        st.download_button(
            label="📥 Baixar PDF",
            data=st.session_state[_SK_PDF],
            file_name=f"Apendice_I_{file_slug}_{ano}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

else:
    st.info(
        "👈 Selecione o **ente fiscal** e o **exercício** na barra lateral "
        "e clique em **Gerar Relatório**."
    )

st.divider()
st.caption(
    "Dados obtidos da [API pública do SICONFI](https://apidatalake.tesouro.gov.br/docs/siconfi/) "
    "(Secretaria do Tesouro Nacional)."
)
