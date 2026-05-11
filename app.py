"""Gerador de Relatórios do SICONFI — TCE-AL · Entrypoint de navegação"""

import pathlib

import streamlit as st

_VERSION = pathlib.Path(__file__).parent.joinpath("VERSION").read_text(encoding="utf-8").strip()

st.set_page_config(
    page_title="Gerador de Relatórios · TCE-AL",
    page_icon="🏛️",
    layout="wide",
)

with st.sidebar:
    st.markdown(f"## 🏛️ Gerador de Relatórios")
    st.caption(f"v{_VERSION} · DCT/TCE-AL")
    st.divider()

pg = st.navigation([
    st.Page("pages/prestacoes_de_contas.py", title="Prestações de Contas", icon="📊"),
    st.Page("pages/02_RGF_Despesa_Pessoal.py", title="RGF Despesa Pessoal", icon="📋"),
])
pg.run()
