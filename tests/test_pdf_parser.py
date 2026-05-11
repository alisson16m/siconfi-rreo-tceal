"""Testes do parser de PDF para RREO Anexo 1 (PDFs oficiais do SICONFI)."""

import io
import pathlib

import pytest
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate

from src.pdf_parser import parse_pdf
from src.report_builder import _AR, _EM, _g, _pivot_items, build_xlsx, build_pdf
from src.siconfi_client import SiconfiResponse

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"
_PDF_PATH = FIXTURES_DIR / "RREO-Agua Branca.pdf"
_NOME_ENTE = "Prefeitura Municipal de Água Branca - AL"
_EXERCICIO = 2025

_PDF_ANADIA = FIXTURES_DIR / "RREO-Anadia.pdf"
_NOME_ANADIA = "Prefeitura Municipal de Anadia - AL"


@pytest.fixture(scope="module")
def agua_branca_pdf() -> bytes:
    return _PDF_PATH.read_bytes()


@pytest.fixture(scope="module")
def agua_branca_resp(agua_branca_pdf) -> SiconfiResponse:
    return parse_pdf(agua_branca_pdf, _NOME_ENTE, _EXERCICIO)


@pytest.fixture(scope="module")
def anadia_pdf() -> bytes:
    return _PDF_ANADIA.read_bytes()


@pytest.fixture(scope="module")
def anadia_resp(anadia_pdf) -> SiconfiResponse:
    return parse_pdf(anadia_pdf, _NOME_ANADIA, _EXERCICIO)


class TestParsePdf:
    def test_retorna_siconfi_response(self, agua_branca_resp):
        assert isinstance(agua_branca_resp, SiconfiResponse)

    def test_items_nao_vazio(self, agua_branca_resp):
        assert len(agua_branca_resp.items) > 0

    def test_todos_items_tem_cod_conta_e_coluna(self, agua_branca_resp):
        for item in agua_branca_resp.items:
            assert item.get("cod_conta"), f"item sem cod_conta: {item}"
            assert item.get("coluna"), f"item sem coluna: {item}"

    def test_todos_items_tem_valor_float(self, agua_branca_resp):
        for item in agua_branca_resp.items:
            assert isinstance(item["valor"], float)

    def test_exercicio_correto(self, agua_branca_resp):
        assert agua_branca_resp.exercicio == _EXERCICIO

    def test_periodo_fixo_6(self, agua_branca_resp):
        assert agua_branca_resp.periodo == 6

    def test_instituicao_e_nome_informado(self, agua_branca_resp):
        assert agua_branca_resp.instituicao == _NOME_ENTE

    def test_data_status_none(self, agua_branca_resp):
        assert agua_branca_resp.data_status is None

    def test_contem_receitas_correntes(self, agua_branca_resp):
        codigos = {item["cod_conta"] for item in agua_branca_resp.items}
        assert "ReceitasCorrentes" in codigos

    def test_contem_despesas_correntes(self, agua_branca_resp):
        codigos = {item["cod_conta"] for item in agua_branca_resp.items}
        assert "DespesasCorrentes" in codigos

    def test_receitas_realizadas_valor_correto(self, agua_branca_resp):
        pivot = _pivot_items(agua_branca_resp.items)
        contas = ("ReceitasCorrentes", "ReceitasCorrentesIntra", "ReceitasDeCapital")
        total = sum(_g(pivot, c, _AR) for c in contas)
        assert total == pytest.approx(154_468_191.85, rel=1e-4)

    def test_despesas_empenhadas_valor_correto(self, agua_branca_resp):
        pivot = _pivot_items(agua_branca_resp.items)
        contas = ("DespesasCorrentes", "DespesasDeCapital")
        total = sum(_g(pivot, c, _EM) for c in contas)
        assert total == pytest.approx(143_293_988.46, rel=1e-4)

    def test_bytes_invalidos_levanta_value_error(self):
        with pytest.raises(ValueError):
            parse_pdf(b"nao e um pdf", "Ente Teste", 2025)

    def test_pdf_sem_anexo1_levanta_value_error(self):
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf)
        doc.build([Paragraph("Texto sem Anexo I", getSampleStyleSheet()["Normal"])])
        with pytest.raises(ValueError, match="Anexo I"):
            parse_pdf(buf.getvalue(), "Ente Teste", 2025)

    def test_resultado_pode_gerar_xlsx(self, agua_branca_resp):
        xlsx_bytes = build_xlsx(agua_branca_resp)
        assert isinstance(xlsx_bytes, bytes) and len(xlsx_bytes) > 0

    def test_resultado_pode_gerar_pdf(self, agua_branca_resp):
        pdf_bytes = build_pdf(agua_branca_resp)
        assert pdf_bytes[:4] == b"%PDF"


class TestParsePdfAnadia:
    """Testa o parser com PDF extraído do portal SICONFI (formato Anadia)."""

    def test_retorna_siconfi_response(self, anadia_resp):
        assert isinstance(anadia_resp, SiconfiResponse)

    def test_items_nao_vazio(self, anadia_resp):
        assert len(anadia_resp.items) > 0

    def test_todos_items_tem_cod_conta_e_coluna(self, anadia_resp):
        for item in anadia_resp.items:
            assert item.get("cod_conta"), f"item sem cod_conta: {item}"
            assert item.get("coluna"), f"item sem coluna: {item}"

    def test_todos_items_tem_valor_float(self, anadia_resp):
        for item in anadia_resp.items:
            assert isinstance(item["valor"], float)

    def test_contem_receitas_correntes(self, anadia_resp):
        codigos = {item["cod_conta"] for item in anadia_resp.items}
        assert "ReceitasCorrentes" in codigos

    def test_contem_despesas_correntes(self, anadia_resp):
        codigos = {item["cod_conta"] for item in anadia_resp.items}
        assert "DespesasCorrentes" in codigos

    def test_receitas_realizadas_valor_correto(self, anadia_resp):
        pivot = _pivot_items(anadia_resp.items)
        contas = ("ReceitasCorrentes", "ReceitasCorrentesIntra", "ReceitasDeCapital")
        total = sum(_g(pivot, c, _AR) for c in contas)
        assert total == pytest.approx(108_929_496.47, rel=1e-4)

    def test_despesas_empenhadas_valor_correto(self, anadia_resp):
        pivot = _pivot_items(anadia_resp.items)
        contas = ("DespesasCorrentes", "DespesasDeCapital")
        total = sum(_g(pivot, c, _EM) for c in contas)
        assert total == pytest.approx(111_335_084.01, rel=1e-4)

    def test_resultado_pode_gerar_xlsx(self, anadia_resp):
        xlsx_bytes = build_xlsx(anadia_resp)
        assert isinstance(xlsx_bytes, bytes) and len(xlsx_bytes) > 0

    def test_resultado_pode_gerar_pdf(self, anadia_resp):
        pdf_bytes = build_pdf(anadia_resp)
        assert pdf_bytes[:4] == b"%PDF"
