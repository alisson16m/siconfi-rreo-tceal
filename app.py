"""Gerador de Relatórios do SICONFI — TCE-AL · Entrypoint de navegação"""

import pathlib

import streamlit as st

_VERSION = pathlib.Path(__file__).parent.joinpath("VERSION").read_text(encoding="utf-8").strip()

st.set_page_config(
    page_title="Gerador de Relatórios · TCE-AL",
    page_icon="🏛️",
    layout="wide",
)

_pages = [
    st.Page("pages/prestacoes_de_contas.py", title="Prestações de Contas", icon="📊"),
    st.Page("pages/02_RGF_Despesa_Pessoal.py", title="Alerta de Despesas com Pessoal", icon="📋"),
]

pg = st.navigation(_pages, position="hidden")

with st.sidebar:
    st.markdown("## 🏛️ Gerador de Relatórios")
    st.caption(f"v{_VERSION} · DCT/TCE-AL")
    st.divider()
    for page in _pages:
        st.page_link(page, label=f"{page.icon} {page.title}")

pg.run()
