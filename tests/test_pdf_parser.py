"""Testes básicos do parser de PDF para RREO Anexo 1."""

import io
import json
import pathlib

import pytest
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate

from src.pdf_parser import parse_pdf
from src.report_builder import build_pdf
from src.siconfi_client import SiconfiResponse

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture()
def arapiraca_response():
    with open(FIXTURES_DIR / "arapiraca_2025.json", encoding="utf-8") as f:
        data = json.load(f)
    items = data["items"]
    return SiconfiResponse(
        items=items,
        instituicao=items[0]["instituicao"],
        exercicio=2025,
        periodo=6,
        url_chamada="https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo?...",
        metadados={"count": data["count"]},
        data_status="2026-01-30T11:34:12Z",
    )


@pytest.fixture()
def arapiraca_pdf(arapiraca_response):
    """PDF gerado a partir da fixture de Arapiraca, usado como entrada do parser."""
    return build_pdf(arapiraca_response)


class TestParsePdf:
    def test_retorna_siconfi_response(self, arapiraca_pdf):
        result = parse_pdf(arapiraca_pdf, "Prefeitura Municipal de Arapiraca - AL", 2025)
        assert isinstance(result, SiconfiResponse)

    def test_items_nao_vazio(self, arapiraca_pdf):
        result = parse_pdf(arapiraca_pdf, "Prefeitura Municipal de Arapiraca - AL", 2025)
        assert len(result.items) > 0

    def test_todos_items_tem_cod_conta_e_coluna(self, arapiraca_pdf):
        result = parse_pdf(arapiraca_pdf, "Prefeitura Municipal de Arapiraca - AL", 2025)
        for item in result.items:
            assert item.get("cod_conta"), f"item sem cod_conta: {item}"
            assert item.get("coluna"), f"item sem coluna: {item}"

    def test_todos_items_tem_valor_float(self, arapiraca_pdf):
        result = parse_pdf(arapiraca_pdf, "Prefeitura Municipal de Arapiraca - AL", 2025)
        for item in result.items:
            assert isinstance(item["valor"], float), f"valor não é float: {item}"

    def test_exercicio_correto(self, arapiraca_pdf):
        result = parse_pdf(arapiraca_pdf, "Prefeitura Municipal de Arapiraca - AL", 2025)
        assert result.exercicio == 2025

    def test_periodo_fixo_6(self, arapiraca_pdf):
        result = parse_pdf(arapiraca_pdf, "Prefeitura Municipal de Arapiraca - AL", 2025)
        assert result.periodo == 6

    def test_instituicao_e_nome_ente_informado(self, arapiraca_pdf):
        nome = "Prefeitura Municipal de Arapiraca - AL"
        result = parse_pdf(arapiraca_pdf, nome, 2025)
        assert result.instituicao == nome

    def test_data_status_none(self, arapiraca_pdf):
        result = parse_pdf(arapiraca_pdf, "Prefeitura Municipal de Arapiraca - AL", 2025)
        assert result.data_status is None

    def test_contem_receitas_correntes(self, arapiraca_pdf):
        result = parse_pdf(arapiraca_pdf, "Prefeitura Municipal de Arapiraca - AL", 2025)
        codigos = {item["cod_conta"] for item in result.items}
        assert "ReceitasCorrentes" in codigos

    def test_contem_despesas_correntes(self, arapiraca_pdf):
        result = parse_pdf(arapiraca_pdf, "Prefeitura Municipal de Arapiraca - AL", 2025)
        codigos = {item["cod_conta"] for item in result.items}
        assert "DespesasCorrentes" in codigos

    def test_bytes_invalidos_levanta_value_error(self):
        with pytest.raises(ValueError):
            parse_pdf(b"nao e um pdf", "Ente Teste", 2025)

    def test_pdf_sem_tabelas_levanta_value_error(self):
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf)
        doc.build([Paragraph("Texto sem tabela", getSampleStyleSheet()["Normal"])])
        with pytest.raises(ValueError, match="tabela"):
            parse_pdf(buf.getvalue(), "Ente Teste", 2025)

    def test_resultado_pode_gerar_xlsx(self, arapiraca_pdf):
        from src.report_builder import build_xlsx
        result = parse_pdf(arapiraca_pdf, "Prefeitura Municipal de Arapiraca - AL", 2025)
        xlsx_bytes = build_xlsx(result)
        assert isinstance(xlsx_bytes, bytes) and len(xlsx_bytes) > 0

    def test_resultado_pode_gerar_pdf(self, arapiraca_pdf):
        result = parse_pdf(arapiraca_pdf, "Prefeitura Municipal de Arapiraca - AL", 2025)
        pdf_bytes = build_pdf(result)
        assert pdf_bytes[:4] == b"%PDF"
