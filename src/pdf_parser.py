"""
Parser de PDF para RREO Anexo 1 — Balanço Orçamentário (PDFs oficiais do SICONFI).

Estratégia: extrai texto bruto (extract_text) das páginas que contêm
"RREO - ANEXO I" e faz parsing linha a linha via regex.
Não usa extract_tables() pois os PDFs do SICONFI não têm bordas de célula
uniformes nas linhas de dados.

Limitações:
  - Requer PDF com texto extraível (não escaneado).
  - Otimizado para PDFs exportados pelo portal SICONFI / sistemas municipais.
  - Apenas o Anexo I (Balanço Orçamentário) é processado; demais anexos são ignorados.
  - Valores percentuais (% bimestre / % acumulado) são descartados — não fazem
    parte do modelo de dados da API e são recalculados pelo report_builder.
"""

import io
import re
import unicodedata
from typing import Any

import pdfplumber

from .report_builder import _AR, _DA, _DI, _EM, _LI, _PA, _PG, _PI, _RK
from .siconfi_client import SiconfiResponse

# ── Índices de coluna nos valores extraídos de cada linha ─────────────────────
# Receitas: [PI, PA, NoBim, %(b/a), AoBim(c), %(c/a), Saldo]
_REC_IDX = {_PI: 0, _PA: 1, _AR: 4}
# Despesas: [DI, DA, NoBim, AoBim(f), Saldo(g), NoBim, AoBim(h), Saldo(i), Pago(j), RPNP(k)]
_DESP_IDX = {_DI: 0, _DA: 1, _EM: 3, _LI: 6, _PG: 8, _RK: 9}

# ── Normalização de texto ─────────────────────────────────────────────────────

def _norm(text: str) -> str:
    """Uppercase + remove acentos para comparação robusta entre fontes."""
    nfkd = unicodedata.normalize("NFKD", text.upper())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# ── Mapeamento label normalizado → cod_conta ──────────────────────────────────
# Chave: resultado de _norm(label). Valor: cod_conta da API ou None (ignorar).
# Inclui variações comuns encontradas em PDFs de diferentes sistemas municipais.

_RECEITA_LABEL_COD: dict[str, str | None] = {
    # Totais / cabeçalhos — ignorados (calculados pelo report_builder)
    "RECEITAS (EXCETO INTRA-ORCAMENTARIAS) (I)": None,
    "SUBTOTAL DAS RECEITAS (III) = (I + II)": None,
    "SUBTOTAL DAS RECEITAS (III)": None,
    "OPERACOES DE CREDITO / REFINANCIAMENTO (IV)": None,
    "SUBTOTAL COM REFINANCIAMENTO (V) = (III + IV)": None,
    "SUBTOTAL COM REFINANCIAMENTO (V)": None,
    "DEFICIT (VI)": None,
    "TOTAL (VII) = (V + VI)": None,
    "TOTAL (VII)": None,
    "SALDOS DE EXERCICIOS ANTERIORES": None,
    "RECURSOS ARRECADADOS EM EXERCICIOS ANTERIORES - RPPS": None,
    "SUPERAVIT FINANCEIRO UTILIZADO PARA CREDITOS ADICIONAIS": None,
    # Receitas Correntes
    "RECEITAS CORRENTES": "ReceitasCorrentes",
    "IMPOSTOS, TAXAS E CONTRIBUICOES DE MELHORIA": "ReceitaTributaria",
    "CONTRIBUICOES": "ReceitaDeContribuicoes",
    "RECEITA PATRIMONIAL": "ReceitaPatrimonial",
    "RECEITA AGROPECUARIA": None,
    "RECEITA INDUSTRIAL": None,
    "RECEITA DE SERVICOS": "ReceitaDeServicos",
    "TRANSFERENCIAS CORRENTES": "TransferenciasCorrentes",
    "TRANSFERENCIAS DA UNIAO E DE SUAS ENTIDADES": "TransferenciasCorrentesDaUniaoEDeSuasEntidades",
    "TRANSFERENCIAS DOS ESTADOS E DO DISTRITO FEDERAL E DE SUAS ENTIDADES": "TransferenciasCorrentesDosEstadosEDoDistritoFederalEDeSuasEntidades",
    "TRANSFERENCIAS DOS ESTADOS E DO DF E DE SUAS ENTIDADES": "TransferenciasCorrentesDosEstadosEDoDistritoFederalEDeSuasEntidades",
    "TRANSFERENCIAS DOS MUNICIPIOS E DE SUAS ENTIDADES": None,
    "TRANSFERENCIAS DE OUTRAS INSTITUICOES PUBLICAS": "TransferenciasCorrentesDeOutrasInstituicoesPublicas",
    "DEMAIS TRANSFERENCIAS CORRENTES": "OutrasTransferenciasCorrentes",
    "OUTRAS TRANSFERENCIAS CORRENTES": "OutrasTransferenciasCorrentes",
    "OUTRAS RECEITAS CORRENTES": "OutrasReceitasCorrentes",
    # Receitas de Capital
    "RECEITAS DE CAPITAL (IV)": "ReceitasDeCapital",
    "RECEITAS DE CAPITAL": "ReceitasDeCapital",
    "OPERACOES DE CREDITO": "ReceitasDeOperacoesDeCredito",
    "OPERACOES DE CREDITO - MERCADO INTERNO": None,
    "OPERACOES DE CREDITO - MERCADO EXTERNO": None,
    "ALIENACAO DE BENS": None,
    "AMORTIZACAO DE EMPRESTIMOS": None,
    "TRANSFERENCIAS DE CAPITAL": "TransferenciasDeCapital",
    "OUTRAS RECEITAS DE CAPITAL": None,
    # Intra-orçamentárias
    "RECEITAS (INTRA-ORCAMENTARIAS) (II)": None,  # total — calculado
    "RECEITAS INTRA-ORCAMENTARIAS": None,
}

# Para a seção intra, "RECEITAS CORRENTES" mapeia para ReceitasCorrentesIntra
_RECEITA_INTRA_LABEL_COD: dict[str, str | None] = {
    "RECEITAS CORRENTES": "ReceitasCorrentesIntra",
    "RECEITAS DE CAPITAL": None,  # ReceitasDeCapitalIntra — ignorado (None em _BLOCO_A)
}

_DESPESA_LABEL_COD: dict[str, str | None] = {
    # Totais / cabeçalhos — ignorados
    "DESPESAS (EXCETO INTRA-ORCAMENTARIAS) (VIII)": None,
    "DESPESAS (EXCETO INTRA-ORCAMENTARIAS) (VII)": None,
    "SUBTOTAL DAS DESPESAS (X) = (VIII + IX)": None,
    "SUBTOTAL DAS DESPESAS (X)": None,
    "AMORTIZACAO DA DIV. / REFINANCIAMENTO (XI)": None,
    "SUBTOTAL C/ REFINANCIAMENTO (XII) = (X + XI)": None,
    "SUBTOTAL C/ REFINANCIAMENTO (XII)": None,
    "SUPERAVIT (XIII)": None,
    "TOTAL (XIV) = (XII + XIII)": None,
    "TOTAL (XIV)": None,
    "RESERVA DO RPPS": None,
    "OPERACOES DE CREDITO - MERCADO INTERNO": None,
    "OPERACOES DE CREDITO - MERCADO EXTERNO": None,
    # Despesas Correntes
    "DESPESAS CORRENTES": "DespesasCorrentes",
    "PESSOAL E ENCARGOS SOCIAIS": "PessoalEEncargosSociais",
    "JUROS E ENCARGOS DA DIVIDA": "JurosEEncargosDaDivida",
    "OUTRAS DESPESAS CORRENTES": "OutrasDespesasCorrentes",
    # Despesas de Capital
    "DESPESAS DE CAPITAL": "DespesasDeCapital",
    "INVESTIMENTOS": "Investimentos",
    "INVERSOES FINANCEIRAS": None,
    "AMORTIZACAO DA DIVIDA": "AmortizacaoDaDivida",
    "RESERVA DE CONTINGENCIA": "ReservaDeContingencia",
}

# Para a seção intra, mapeamentos distintos
_DESPESA_INTRA_LABEL_COD: dict[str, str | None] = {
    "DESPESAS CORRENTES": "DespesasCorrentesIntra",
    "DESPESAS DE CAPITAL": "DespesasDeCapitalIntra",
    "PESSOAL E ENCARGOS SOCIAIS": None,
    "JUROS E ENCARGOS DA DIVIDA": None,
    "OUTRAS DESPESAS CORRENTES": None,
    "INVESTIMENTOS": None,
    "INVERSOES FINANCEIRAS": None,
    "AMORTIZACAO DA DIVIDA": None,
    "RESERVA DE CONTINGENCIA": None,
}


# ── Extração de valores de uma linha ─────────────────────────────────────────

def _parse_num(text: str | None) -> float:
    if not text:
        return 0.0
    s = text.strip()
    if not s or s == "-":
        return 0.0
    try:
        return float(s.replace(".", "").replace(",", "."))
    except ValueError:
        return 0.0


def _split_line(line: str) -> tuple[str, list[float]] | None:
    """
    Divide 'LABEL  1.234,56  2.345,67  ...' em (label, [valores]).
    Retorna None se a linha não tiver valores numéricos.
    """
    # Primeiro número BRL ou traço isolado na linha
    m = re.search(r'(?<!\S)(-?\d{1,3}(?:\.\d{3})*,\d+|-(?=\s|$))', line)
    if not m:
        return None
    label = line[:m.start()].strip().rstrip(".")
    if not label:
        return None
    values_part = line[m.start():]
    values: list[float] = []
    for tok in values_part.split():
        t = tok.strip()
        if t == "-":
            values.append(0.0)
        elif re.match(r'^-?\d{1,3}(?:\.\d{3})*,\d+$', t):
            values.append(_parse_num(t))
    return label, values


def _make_item(nome_ente: str, exercicio: int, cod_conta: str,
               coluna: str, valor: float) -> dict[str, Any]:
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


# ── Parser das seções ─────────────────────────────────────────────────────────

def _parse_receitas(text: str, nome_ente: str, exercicio: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    in_intra = False
    # Detecta início da seção intra pelo cabeçalho "RECEITAS INTRA-ORÇAMENTÁRIAS"
    intra_trigger = _norm("RECEITAS INTRA-OR")

    for line in text.splitlines():
        result = _split_line(line)
        if not result:
            # Detecta entrada na seção intra mesmo sem valores na linha
            if intra_trigger in _norm(line):
                in_intra = True
            continue
        label, values = result
        label_n = _norm(label)

        # Detecta seção intra (a linha pode ou não ter valores)
        if intra_trigger in label_n:
            in_intra = True

        mapping = _RECEITA_INTRA_LABEL_COD if in_intra else _RECEITA_LABEL_COD

        # Busca exata primeiro, depois prefixo
        cod = mapping.get(label_n)
        if cod is None and label_n not in mapping:
            # Tenta correspondência por prefixo (para variações como "RECEITAS CORRENTES.")
            cod = next(
                (v for k, v in mapping.items() if label_n.startswith(k[:30])),
                "NOT_FOUND",
            )
            if cod == "NOT_FOUND":
                continue  # linha desconhecida
        if cod is None:
            continue  # linha mapeada explicitamente para None (ignorar)

        for col, idx in _REC_IDX.items():
            if idx < len(values):
                items.append(_make_item(nome_ente, exercicio, cod, col, values[idx]))

    return items


def _parse_despesas(text: str, nome_ente: str, exercicio: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    in_intra = False
    intra_trigger = _norm("DESPESAS (INTRA-OR")
    intra_trigger2 = _norm("DESPESAS INTRA-OR")

    for line in text.splitlines():
        result = _split_line(line)
        if not result:
            ln = _norm(line)
            if intra_trigger in ln or intra_trigger2 in ln:
                in_intra = True
            continue
        label, values = result
        label_n = _norm(label)

        if intra_trigger in label_n or intra_trigger2 in label_n:
            in_intra = True

        mapping = _DESPESA_INTRA_LABEL_COD if in_intra else _DESPESA_LABEL_COD

        cod = mapping.get(label_n)
        if cod is None and label_n not in mapping:
            cod = next(
                (v for k, v in mapping.items() if label_n.startswith(k[:30])),
                "NOT_FOUND",
            )
            if cod == "NOT_FOUND":
                continue
        if cod is None:
            continue

        for col, idx in _DESP_IDX.items():
            if idx < len(values):
                items.append(_make_item(nome_ente, exercicio, cod, col, values[idx]))

    return items


# ── Identificação das páginas do Anexo I ─────────────────────────────────────

def _is_anexo1_page(text: str) -> bool:
    n = _norm(text)
    return (
        "RREO - ANEXO I" in n
        or "BALANCO ORCAMENTARIO" in n
        # Página de continuação (despesas): tem o marcador de saldo "(G)=(E-F)"
        # que é exclusivo do Anexo I — não aparece em outros anexos do RREO.
        or "(G)=(E-F)" in n
    )


def _page_has_receitas(text: str) -> bool:
    n = _norm(text)
    return bool(re.search(r'RECEITAS\s+INICIAL', n))


def _page_has_despesas(text: str) -> bool:
    n = _norm(text)
    return bool(re.search(r'DESPESAS\s+INICIAL', n))


# ── Ponto de entrada público ──────────────────────────────────────────────────

def parse_pdf(pdf_bytes: bytes, nome_ente: str, exercicio: int) -> SiconfiResponse:
    """
    Lê um PDF do RREO e extrai os dados do Anexo I (Balanço Orçamentário),
    retornando um SiconfiResponse compatível com fetch_rreo_anexo1().

    Args:
        pdf_bytes: Bytes do arquivo PDF.
        nome_ente: Nome do ente fiscal informado pelo usuário.
        exercicio: Ano do exercício fiscal.

    Returns:
        SiconfiResponse com items no mesmo formato retornado pela API.

    Raises:
        ValueError: Se o PDF estiver protegido por senha.
        ValueError: Se nenhuma página do Anexo I for encontrada.
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

    receitas_text = ""
    despesas_text = ""

    with pdf_file:
        for page in pdf_file.pages:
            text = page.extract_text() or ""
            if not _is_anexo1_page(text):
                continue
            if _page_has_receitas(text):
                receitas_text += "\n" + text
            if _page_has_despesas(text):
                despesas_text += "\n" + text

    if not receitas_text and not despesas_text:
        raise ValueError(
            "Nenhuma página do RREO Anexo I (Balanço Orçamentário) encontrada no PDF. "
            "Verifique se o arquivo contém o demonstrativo correto "
            "e se não é um PDF escaneado (imagem)."
        )

    items: list[dict[str, Any]] = []
    if receitas_text:
        items.extend(_parse_receitas(receitas_text, nome_ente, exercicio))
    if despesas_text:
        items.extend(_parse_despesas(despesas_text, nome_ente, exercicio))

    return SiconfiResponse(
        items=items,
        instituicao=nome_ente,
        exercicio=exercicio,
        periodo=6,
        url_chamada="pdf_upload",
        metadados={"fonte": "pdf_upload"},
        data_status=None,
    )
