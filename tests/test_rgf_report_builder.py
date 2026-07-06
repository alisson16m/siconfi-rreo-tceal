"""Testes para src/rgf_report_builder.py — geração do Termo de Alerta."""

import io

from docx import Document

from src.rgf_report_builder import gerar_alerta_docx
from src.rgf_limites import Situacao
from src.siconfi_rgf_client import ResultadoConsultaRGF, ResultadoEnteRGF


def _resultado(entes_sem_dados: list[str]) -> ResultadoConsultaRGF:
    ente_critico = ResultadoEnteRGF(
        id_ente="2700102",
        nome="Arapiraca",
        percentual_dtp=55.0,
        situacao=Situacao.ALERTA,
        periodo_tipo="Q",
        nr_periodo=1,
    )
    return ResultadoConsultaRGF(
        entes_com_dados=[ente_critico],
        entes_sem_dados=entes_sem_dados,
        exercicio=2025,
        esfera="M",
        poder="E",
    )


def _paragraphs_texto(doc_bytes: bytes) -> list[str]:
    doc = Document(io.BytesIO(doc_bytes))
    return [p.text for p in doc.paragraphs]


def test_alerta_com_entes_sem_dados_inclui_texto_e_lista_numerada():
    resultado = _resultado(["Maceió", "Palmeira dos Índios"])

    doc_bytes = gerar_alerta_docx(
        resultado,
        nr_quadrimestre=1,
        nr_semestre=1,
        data_extracao="05/07/2026",
        tipo_periodo="A",
    )

    textos = _paragraphs_texto(doc_bytes)

    assert any(
        "não haviam enviado ao SICONFI" in t and "05/07/2026" in t
        for t in textos
    )
    assert "1. Maceió" in textos
    assert "2. Palmeira dos Índios" in textos


def test_alerta_sem_entes_sem_dados_nao_inclui_secao():
    resultado = _resultado([])

    doc_bytes = gerar_alerta_docx(
        resultado,
        nr_quadrimestre=1,
        nr_semestre=1,
        data_extracao="05/07/2026",
        tipo_periodo="A",
    )

    textos = _paragraphs_texto(doc_bytes)

    assert not any("não haviam enviado ao SICONFI" in t for t in textos)
