"""
Parser de PDF para RREO Anexo 1.

Extrai tabelas de um PDF e retorna um SiconfiResponse compatível com o retornado
por fetch_rreo_anexo1(), permitindo que o objeto seja usado diretamente em
build_xlsx() e build_pdf().

Limitações:
  - Requer PDF com texto extraível. PDFs escaneados (imagens) não são suportados.
  - Otimizado para PDFs gerados por esta aplicação (build_pdf). PDFs exportados
    diretamente do portal SICONFI ou de outros sistemas podem ter colunas em ordem
    diferente e precisar de ajustes no mapeamento posicional.
  - Tabelas que se estendem por múltiplas páginas podem não ser reassociadas
    corretamente — nesse caso o bloco ficará incompleto.
  - Valores percentuais (A.V.%, A.H.%) são ignorados, pois não são armazenados
    nos items da API e são recalculados em build_pdf().
"""

import io
from typing import Any

import pdfplumber

from .report_builder import (
    _AR,
    _BLOCO_A,
    _BLOCO_B,
    _DA,
    _DI,
    _EM,
    _LI,
    _PA,
    _PG,
    _PI,
    _RK,
)
from .siconfi_client import SiconfiResponse

# Sequência esperada no PDF para Bloco A: exclui __HEADER e a linha 7
# ("Receitas Orçamentárias"), que _build_table_a() omite do PDF.
_BLOCO_A_PDF = [
    (row_num, label, conta)
    for row_num, label, conta in _BLOCO_A
    if conta != "__HEADER" and row_num != 7
]

# Sequência esperada no PDF para Bloco B: exclui __HEADER e linhas com label vazio.
_BLOCO_B_PDF = [
    (row_num, label, conta)
    for row_num, label, conta in _BLOCO_B
    if conta != "__HEADER" and label != ""
]

# Mapeamento posicional de índice de coluna (após a coluna de label) → nome da coluna da API
# Bloco A: [PI, PA, AR, diff(ignorar), AV%(ignorar), AH%(ignorar)]
_COL_MAP_A = [(_PI, 0), (_PA, 1), (_AR, 2)]
# Bloco B: [DI, DA, EM, LI, PG, RK]
_COL_MAP_B = [(_DI, 0), (_DA, 1), (_EM, 2), (_LI, 3), (_PG, 4), (_RK, 5)]


def _parse_num(text: str | None) -> float:
    """Converte texto em formato BRL (ex: '1.267.662.215,61') para float."""
    if not text:
        return 0.0
    s = text.strip()
    if not s or s in ("-", "—", "N/A", "n/a"):
        return 0.0
    s = s.replace(".", "").replace(",", ".").rstrip("%")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _make_item(
    nome_ente: str, exercicio: int, cod_conta: str, coluna: str, valor: float
) -> dict[str, Any]:
    return {
        "exercicio": exercicio,
        "demonstrativo": "RREO",
        "periodo": 6,
        "periodicidade": "B",
        "instituicao": nome_ente,
        "anexo": "RREO-Anexo 01",
        "cod_conta": cod_conta,
        "coluna": coluna,
        "valor": valor,
    }


def _parse_bloco(
    table: list[list[str | None]],
    nome_ente: str,
    exercicio: int,
    expected_rows: list[tuple[int, str, str | None]],
    col_map: list[tuple[str, int]],
) -> list[dict[str, Any]]:
    """Extrai items de um bloco de tabela usando correspondência posicional."""
    items: list[dict[str, Any]] = []
    data_rows = table[1:]  # primeira linha é cabeçalho

    for pdf_row, (_row_num, _label, conta) in zip(data_rows, expected_rows):
        if conta is None or conta.startswith("__SUM"):
            continue
        vals = pdf_row[1:]  # primeira célula é o rótulo da linha
        for col_name, idx in col_map:
            cell = vals[idx] if idx < len(vals) else None
            items.append(_make_item(nome_ente, exercicio, conta, col_name, _parse_num(cell)))

    return items


def parse_pdf(pdf_bytes: bytes, nome_ente: str, exercicio: int) -> SiconfiResponse:
    """
    Lê um PDF do RREO Anexo 1 e retorna um SiconfiResponse pronto para uso em
    build_xlsx() e build_pdf().

    Args:
        pdf_bytes: Bytes do arquivo PDF.
        nome_ente: Nome do ente fiscal informado pelo usuário.
        exercicio: Ano do exercício fiscal.

    Returns:
        SiconfiResponse com items no mesmo formato retornado por fetch_rreo_anexo1().

    Raises:
        ValueError: Se o PDF estiver protegido por senha.
        ValueError: Se nenhuma tabela reconhecível do RREO Anexo 1 for encontrada.
    """
    try:
        pdf_file = pdfplumber.open(io.BytesIO(pdf_bytes))
    except Exception as exc:
        msg = str(exc).lower()
        if "password" in msg or "encrypt" in msg:
            raise ValueError(
                "PDF protegido por senha. Remova a proteção antes de fazer o upload."
            ) from exc
        raise ValueError(f"Não foi possível abrir o PDF: {exc}") from exc

    all_tables: list[list[list[str | None]]] = []
    with pdf_file:
        for page in pdf_file.pages:
            tables = page.extract_tables()
            if tables:
                all_tables.extend(tables)

    items: list[dict[str, Any]] = []
    found_a = False
    found_b = False

    for table in all_tables:
        if not table or not table[0]:
            continue
        first_cell = str(table[0][0] or "").strip().lower()
        if first_cell.startswith("receita"):
            items.extend(
                _parse_bloco(table, nome_ente, exercicio, _BLOCO_A_PDF, _COL_MAP_A)
            )
            found_a = True
        elif first_cell.startswith("despesa"):
            items.extend(
                _parse_bloco(table, nome_ente, exercicio, _BLOCO_B_PDF, _COL_MAP_B)
            )
            found_b = True

    if not found_a and not found_b:
        raise ValueError(
            "Nenhuma tabela de RREO Anexo 1 encontrada no PDF. "
            "Verifique se o arquivo contém o demonstrativo correto "
            "e se não é um PDF escaneado (imagem)."
        )

    return SiconfiResponse(
        items=items,
        instituicao=nome_ente,
        exercicio=exercicio,
        periodo=6,
        url_chamada="pdf_upload",
        metadados={"fonte": "pdf_upload"},
        data_status=None,
    )
