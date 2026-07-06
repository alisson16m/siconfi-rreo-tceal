"""Página Streamlit — RGF Despesa Total com Pessoal · TCE-AL"""

import logging
import pathlib
from datetime import datetime

import pandas as pd
import streamlit as st

from src.municipios_al import ENTES_AL
from src.rgf_limites import Situacao, label_periodo_completo
from src.rgf_report_builder import gerar_alerta_docx, gerar_relatorio_docx
from src.siconfi_rgf_client import ResultadoConsultaRGF, consultar_todos_entes

_VERSION = (
    pathlib.Path(__file__).parent.parent.joinpath("VERSION")
    .read_text(encoding="utf-8")
    .strip()
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

_COR_SITUACAO: dict[Situacao, str] = {
    Situacao.NORMAL:     "#d4edda",
    Situacao.ALERTA:     "#fff3cd",
    Situacao.PRUDENCIAL: "#ffe0b2",
    Situacao.MAXIMO:     "#f8d7da",
    Situacao.SEM_DADOS:  "#e2e3e5",
}

_LABEL_SITUACAO: dict[Situacao, str] = {
    Situacao.NORMAL:     "Dentro do Limite",
    Situacao.ALERTA:     "Alerta",
    Situacao.PRUDENCIAL: "Prudencial",
    Situacao.MAXIMO:     "Acima do Máximo",
    Situacao.SEM_DADOS:  "Sem dados",
}

_SK_RESULTADO = "rgf_resultado"
_SK_PARAMS    = "rgf_params"


def _fmt_pct(valor: float) -> str:
    return f"{valor:.2f}%".replace(".", ",")


st.markdown("### 🏛️ RGF — Despesa Total com Pessoal")
st.caption(
    "Consulta o Demonstrativo da Despesa com Pessoal (RGF Anexo 01) via API do SICONFI "
    "e classifica os entes conforme os limites da Lei de Responsabilidade Fiscal (LC 101/2000)."
)
st.divider()

# ── Filtros ────────────────────────────────────────────────────────────────────

col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 2, 2, 1, 1])

ano_atual = datetime.now().year

with col1:
    exercicio: int = st.selectbox("Exercício", list(range(ano_atual, 2019, -1)), index=0)

with col2:
    esfera_label: str = st.selectbox("Esfera", ["Municipal", "Estadual"], index=0)
    esfera_cod = "M" if esfera_label == "Municipal" else "E"

with col3:
    poder_label: str = st.selectbox("Poder", ["Executivo", "Legislativo"], index=0)
    poder_cod = "E" if poder_label == "Executivo" else "L"

with col4:
    tipo_periodo_label: str = st.selectbox(
        "Tipo de Período",
        ["Ambos (Quadrimestral e Semestral)", "Só Quadrimestral", "Só Semestral"],
        index=0,
    )
    _TIPO_MAP = {
        "Ambos (Quadrimestral e Semestral)": "A",
        "Só Quadrimestral": "Q",
        "Só Semestral": "S",
    }
    tipo_periodo_cod = _TIPO_MAP[tipo_periodo_label]

with col5:
    nr_quad: int = st.selectbox("Quadrimestre", [1, 2, 3], index=2, format_func=lambda x: f"{x}º")

with col6:
    nr_sem: int = st.selectbox("Semestre", [1, 2], index=1, format_func=lambda x: f"{x}º")

st.divider()

# ── Limpa resultado quando parâmetros mudam ────────────────────────────────────

params_atuais = (exercicio, esfera_cod, poder_cod, tipo_periodo_cod, nr_quad, nr_sem)

if st.session_state.get(_SK_PARAMS) != params_atuais:
    st.session_state.pop(_SK_RESULTADO, None)

# ── Botão de consulta ─────────────────────────────────────────────────────────

consultar = st.button(
    "🔍 Consultar SICONFI e gerar documentos",
    type="primary",
)

if consultar:
    total_entes = sum(1 for e in ENTES_AL if e.esfera == esfera_cod)
    label_periodo = label_periodo_completo(nr_quad, nr_sem, tipo_periodo_cod)

    logger.info(
        "Consulta RGF iniciada: exercicio=%d, esfera=%s, poder=%s, periodo=%s (%d entes)",
        exercicio, esfera_cod, poder_cod, label_periodo, total_entes,
    )

    progresso = st.progress(0, text=f"Consultando {total_entes} entes em paralelo...")

    def _on_progress(concluidos: int, total: int) -> None:
        try:
            progresso.progress(
                concluidos / total,
                text=f"Consultando... {concluidos}/{total} entes",
            )
        except Exception:
            pass

    resultado = consultar_todos_entes(
        exercicio=exercicio,
        nr_quadrimestre=nr_quad,
        nr_semestre=nr_sem,
        esfera=esfera_cod,
        poder=poder_cod,
        tipo_periodo=tipo_periodo_cod,
        on_progress=_on_progress,
    )

    progresso.empty()

    st.session_state[_SK_RESULTADO] = resultado
    st.session_state[_SK_PARAMS] = params_atuais

    logger.info(
        "Consulta RGF concluída: %d com dados, %d sem dados",
        len(resultado.entes_com_dados),
        len(resultado.entes_sem_dados),
    )

# ── Resultados ─────────────────────────────────────────────────────────────────

resultado: ResultadoConsultaRGF | None = st.session_state.get(_SK_RESULTADO)

if resultado is None:
    st.info(
        "Configure os filtros acima e clique em **Consultar SICONFI e gerar documentos**."
    )
    st.stop()

# Métricas resumo
contagem: dict[Situacao, int] = {s: 0 for s in Situacao}
for ente in resultado.entes_com_dados:
    contagem[ente.situacao] += 1

col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
col_m1.metric("Dentro do Limite", contagem[Situacao.NORMAL])
col_m2.metric("Alerta", contagem[Situacao.ALERTA])
col_m3.metric("Prudencial", contagem[Situacao.PRUDENCIAL])
col_m4.metric("Acima do Máximo", contagem[Situacao.MAXIMO])
col_m5.metric("Sem dados (não enviaram)", len(resultado.entes_sem_dados))

st.divider()

# Tabela com highlight por situação
_pop_por_nome = {e.nome: e.populacao for e in ENTES_AL}

rows = []
for ente in resultado.entes_com_dados:
    rows.append({
        "Ente Fiscal": ente.nome,
        "População": ente.populacao,
        "% DTP/RCL": ente.percentual_dtp,
        "Período": f"{ente.nr_periodo}º {'Quad.' if ente.periodo_tipo == 'Q' else 'Sem.'}",
        "Situação": _LABEL_SITUACAO.get(ente.situacao, ente.situacao.value),
    })
for nome in resultado.entes_sem_dados:
    rows.append({
        "Ente Fiscal": nome,
        "População": _pop_por_nome.get(nome, 0),
        "% DTP/RCL": None,
        "Período": "—",
        "Situação": _LABEL_SITUACAO[Situacao.SEM_DADOS],
    })

if rows:
    df = pd.DataFrame(rows)
    _cor_por_label = {v: _COR_SITUACAO[k] for k, v in _LABEL_SITUACAO.items()}

    def _highlight(row: pd.Series) -> list[str]:
        cor = _cor_por_label.get(row["Situação"], "")
        return [f"background-color: {cor}" if cor else "" for _ in row]

    styler = (
        df.style
        .apply(_highlight, axis=1)
        .format({"% DTP/RCL": lambda v: _fmt_pct(v) if v is not None else "—"})
    )
    altura = min(800, max(200, 38 + len(df) * 35))
    st.dataframe(styler, use_container_width=True, height=altura)
else:
    st.warning("Nenhum dado retornado para os filtros selecionados.")

st.divider()

# ── Botões de download ─────────────────────────────────────────────────────────

_params = st.session_state.get(_SK_PARAMS, params_atuais)
_tipo_periodo_dl = _params[3]
_nr_quad_dl, _nr_sem_dl = _params[4], _params[5]

col_dl1, col_dl2 = st.columns(2)

with col_dl1:
    if st.button("⬇ Gerar Termo de Alerta (.docx)", use_container_width=True, key="btn_alerta"):
        with st.spinner("Gerando Termo de Alerta..."):
            docx_bytes = gerar_alerta_docx(
                resultado, _nr_quad_dl, _nr_sem_dl,
                tipo_periodo=_tipo_periodo_dl,
            )
        st.download_button(
            label="📥 Baixar Termo de Alerta",
            data=docx_bytes,
            file_name=f"Termo_Alerta_DTP_{resultado.exercicio}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )

with col_dl2:
    if st.button("⬇ Gerar Relatório de Gestão Fiscal (.docx)", use_container_width=True, key="btn_relatorio"):
        with st.spinner("Gerando Relatório..."):
            docx_bytes = gerar_relatorio_docx(
                resultado, _nr_quad_dl, _nr_sem_dl, tipo_periodo=_tipo_periodo_dl
            )
        st.download_button(
            label="📥 Baixar Relatório de Gestão Fiscal",
            data=docx_bytes,
            file_name=f"RGF_Despesa_Pessoal_{resultado.exercicio}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )

st.divider()
st.caption(
    "Dados obtidos da [API pública do SICONFI](https://apidatalake.tesouro.gov.br/docs/siconfi/) "
    "(Secretaria do Tesouro Nacional). "
    "Limites LRF: LC nº 101/2000, Arts. 19, 20, 22 e 59, §1º, II."
)
