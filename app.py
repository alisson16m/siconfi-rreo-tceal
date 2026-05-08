"""Gerador de Apêndice I — RREO Anexo 1 · TCE-AL"""

import logging
import pathlib
import time
import unicodedata
from datetime import datetime

import pandas as pd
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
    fetch_status_todos_entes_ano,
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
_SK_RESP     = "siconfi_response"
_SK_NOME     = "report_nome"
_SK_ANO      = "report_ano"
_SK_RECEITAS = "metric_receitas"
_SK_DESPESAS = "metric_despesas"
_SK_DATA     = "metric_data_status"

# ── Painel de entregas ─────────────────────────────────────────────────────────
_ID_ENTES_AL = frozenset(e.id_ente for e in ENTES_AL)
_ANOS_PAINEL = 5  # últimos N exercícios completos exibidos no painel


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


# TTL de 300s: evita chamadas redundantes na mesma sessão sem risco de dados desatualizados
@st.cache_data(ttl=300)
def _cached_fetch_status(id_ente: str, exercicio: int) -> str | None:
    return fetch_data_status(id_ente=id_ente, exercicio=exercicio)


@st.cache_data(ttl=3600)
def _cached_fetch_painel(exercicio: int) -> dict[str, bool]:
    return fetch_status_todos_entes_ano(exercicio=exercicio, id_entes=_ID_ENTES_AL)


# ── Painel de Entregas ────────────────────────────────────────────────────────

def _render_painel(entes_ordenados: list[Ente]) -> None:
    st.subheader("Painel de Entregas ao SICONFI — RREO 6º Bimestre")
    st.caption(
        "Indica se cada ente fiscal entregou os dados do RREO 6º Bimestre "
        "ao SICONFI no exercício correspondente."
    )

    ano_ref = datetime.now().year - 1
    anos_disponiveis = list(range(ano_ref, ano_ref - _ANOS_PAINEL, -1))

    if st.button("🔄 Carregar Dados", key="btn_painel"):
        painel_raw: dict[int, dict[str, bool]] = {}
        prog = st.progress(0, text="Carregando...")
        for i, ano in enumerate(anos_disponiveis, 1):
            prog.progress(i / len(anos_disponiveis), text=f"Consultando exercício {ano}...")
            painel_raw[ano] = _cached_fetch_painel(ano)
        prog.empty()
        st.session_state["painel_raw"] = painel_raw

    painel_raw = st.session_state.get("painel_raw")
    if not painel_raw:
        st.info("Clique em **Carregar Dados** para consultar o SICONFI.")
        return

    # ── Filtros ───────────────────────────────────────────────────────────────
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        _TODOS = "Todos os entes"
        opcoes_entes = [_TODOS] + [e.nome for e in entes_ordenados]
        filtro_ente = st.selectbox("Ente fiscal", opcoes_entes, key="filtro_ente_painel")
    with col_f2:
        filtro_anos = st.multiselect(
            "Exercícios",
            options=anos_disponiveis,
            default=anos_disponiveis,
            key="filtro_anos_painel",
        )

    if not filtro_anos:
        st.warning("Selecione ao menos um exercício.")
        return

    # ── Aplica filtros ────────────────────────────────────────────────────────
    entes_filtrados = (
        entes_ordenados if filtro_ente == _TODOS
        else [e for e in entes_ordenados if e.nome == filtro_ente]
    )
    anos_filtrados = sorted(filtro_anos, reverse=True)

    rows: dict[str, dict[str, str]] = {}
    for ente in entes_filtrados:
        rows[ente.nome] = {
            str(ano): "✅" if painel_raw.get(ano, {}).get(ente.id_ente) else "❌"
            for ano in anos_filtrados
        }
    df = pd.DataFrame.from_dict(rows, orient="index")
    df.index.name = "Ente Fiscal"

    if filtro_ente == _TODOS:
        totais: dict[str, int] = {
            str(ano): sum(1 for v in painel_raw.get(ano, {}).values() if v)
            for ano in anos_filtrados
        }
        df_total = pd.DataFrame([totais], index=["Total entregaram"])
        df_total.index.name = "Ente Fiscal"
        df_completo = pd.concat([df, df_total])
    else:
        df_completo = df

    _PRIMARY = "#1f4e79"
    _styler = (
        df_completo.style
        .apply(
            lambda row: [
                f"background-color: {_PRIMARY}; color: white; font-weight: bold"
                if row.name == "Total entregaram"
                else ""
                for _ in row
            ],
            axis=1,
        )
        .set_table_styles([
            {"selector": "th", "props": [
                ("background-color", _PRIMARY),
                ("color", "white"),
                ("font-weight", "bold"),
                ("text-align", "center"),
            ]},
            {"selector": "th.row_heading", "props": [
                ("background-color", _PRIMARY),
                ("color", "white"),
                ("font-weight", "bold"),
            ]},
        ])
    )
    n_linhas = len(df_completo)
    altura = min(900, max(200, 38 + n_linhas * 35)) if filtro_ente != _TODOS else 900
    st.dataframe(_styler, use_container_width=True, height=altura)

    st.divider()
    st.caption(
        "Dados obtidos da [API pública do SICONFI](https://apidatalake.tesouro.gov.br/docs/siconfi/) "
        "(Secretaria do Tesouro Nacional)."
    )


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
    div[data-baseweb="tab-list"] { overflow-x: auto !important; flex-wrap: nowrap !important; gap: 4px; }
    button[data-baseweb="tab"] { white-space: nowrap !important; flex-shrink: 0 !important; min-width: max-content !important; }
    button[data-baseweb="tab"] p { white-space: nowrap !important; }
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

# ── Abas principais ───────────────────────────────────────────────────────────

tab_relatorio, tab_painel = st.tabs(["📊 Relatório", "🗺️ Painel de Entregas"])

# ── Aba 1: Relatório ──────────────────────────────────────────────────────────

with tab_relatorio:
    st.title("Dados de Execução Orçamentária")
    st.caption(
        "Dados com base no Balanço Orçamentário — Anexo I do Relatório Resumido "
        "de Execução Orçamentária (RREO) do 6º Bimestre"
    )
    st.divider()

    # Invalida cache quando os parâmetros mudam
    if (
        st.session_state.get(_SK_NOME) != ente.nome
        or st.session_state.get(_SK_ANO) != exercicio
    ):
        for k in (_SK_RESP, _SK_RECEITAS, _SK_DESPESAS, _SK_DATA):
            st.session_state.pop(k, None)

    # Geração do relatório
    if gerar:
        _t0 = time.perf_counter()
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

            response.data_status = _cached_fetch_status(ente.id_ente, exercicio)

            pivot = _pivot_items(response.items)
            total_receitas = sum(_g(pivot, c, _AR) for c in _CONTAS_RECEITA)
            total_despesas = sum(_g(pivot, c, _EM) for c in _CONTAS_DESPESA)

            st.session_state[_SK_RESP]     = response
            st.session_state[_SK_NOME]     = ente.nome
            st.session_state[_SK_ANO]      = exercicio
            st.session_state[_SK_RECEITAS] = total_receitas
            st.session_state[_SK_DESPESAS] = total_despesas
            st.session_state[_SK_DATA]     = response.data_status

        _elapsed = time.perf_counter() - _t0
        logger.info(
            "Operação concluída: ente=%s, exercicio=%d, tempo_total=%.2fs",
            ente.id_ente,
            exercicio,
            _elapsed,
        )

    # Resultados
    if _SK_RESP in st.session_state:
        response  = st.session_state[_SK_RESP]
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
            if st.button("⬇ Gerar XLSX", use_container_width=True, key="btn_xlsx"):
                with st.spinner("Gerando XLSX..."):
                    _xlsx_data = build_xlsx(response)
                    logger.info("Relatório XLSX gerado: Apendice_I_%s_%d.xlsx", file_slug, ano)
                st.download_button(
                    label="📥 Baixar XLSX",
                    data=_xlsx_data,
                    file_name=f"Apendice_I_{file_slug}_{ano}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
        with col_pdf:
            if st.button("⬇ Gerar PDF", use_container_width=True, key="btn_pdf"):
                with st.spinner("Gerando PDF..."):
                    _pdf_data = build_pdf(response)
                    logger.info("Relatório PDF gerado: Apendice_I_%s_%d.pdf", file_slug, ano)
                st.download_button(
                    label="📥 Baixar PDF",
                    data=_pdf_data,
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

# ── Aba 2: Painel de Entregas ─────────────────────────────────────────────────

with tab_painel:
    _render_painel(entes_ordenados)
