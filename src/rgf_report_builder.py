"""Gerador de documentos .docx institucionais para RGF Despesa com Pessoal — TCE-AL."""

import io
from datetime import datetime

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

from .rgf_limites import Situacao, get_limite_maximo, label_periodo_completo
from .siconfi_rgf_client import ResultadoConsultaRGF

_AZUL_TCE = RGBColor(0x1F, 0x4E, 0x79)

_LABEL_SITUACAO: dict[Situacao, str] = {
    Situacao.NORMAL:     "Dentro do Limite",
    Situacao.ALERTA:     "Alerta (Art. 59, §1º, II)",
    Situacao.PRUDENCIAL: "Prudencial (Art. 22)",
    Situacao.MAXIMO:     "Excede Limite Máximo (Arts. 19/20)",
    Situacao.SEM_DADOS:  "Sem dados",
}

_ESFERA_LABEL = {"M": "Municipal", "E": "Estadual"}
_PODER_LABEL  = {"E": "Executivo", "L": "Legislativo"}


def _fmt_pct(valor: float) -> str:
    return f"{valor:.2f}%".replace(".", ",")


def _cabecalho(doc: Document, titulo: str, subtitulo: str) -> None:
    """Adiciona cabeçalho institucional TCE-AL ao documento."""
    h1 = doc.add_heading(level=1)
    h1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = h1.add_run("TRIBUNAL DE CONTAS DO ESTADO DE ALAGOAS — TCE-AL")
    run.font.color.rgb = _AZUL_TCE
    run.font.size = Pt(13)

    h2 = doc.add_heading(level=2)
    h2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run2 = h2.add_run("Diretoria de Coordenação de Técnicos — DCT")
    run2.font.color.rgb = _AZUL_TCE
    run2.font.size = Pt(11)

    doc.add_paragraph()

    ht = doc.add_heading(level=2)
    ht.alignment = WD_ALIGN_PARAGRAPH.CENTER
    ht.add_run(titulo).font.size = Pt(12)

    ps = doc.add_paragraph()
    ps.alignment = WD_ALIGN_PARAGRAPH.CENTER
    ps.add_run(subtitulo).font.size = Pt(10)

    doc.add_paragraph()


def _rodape_legal(doc: Document) -> None:
    """Adiciona nota de rodapé com base legal e data de geração."""
    doc.add_paragraph()
    p1 = doc.add_paragraph()
    r1 = p1.add_run(
        "Base legal: Lei Complementar nº 101/2000 (LRF) — Arts. 19, 20, 22 e 59, §1º, II. "
        "Resolução Normativa TCE-AL nº 5/2024."
    )
    r1.font.size = Pt(8)
    r1.italic = True

    p2 = doc.add_paragraph()
    r2 = p2.add_run(
        f"Documento gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')} "
        "pela ferramenta SICONFI-TCE-AL (DCT)."
    )
    r2.font.size = Pt(8)
    r2.italic = True


def _subtitulo_padrao(resultado: ResultadoConsultaRGF, nr_quadrimestre: int, nr_semestre: int) -> str:
    label_periodo = label_periodo_completo(nr_quadrimestre, nr_semestre)
    esfera = _ESFERA_LABEL.get(resultado.esfera, resultado.esfera)
    poder = _PODER_LABEL.get(resultado.poder, resultado.poder)
    return (
        f"Despesa Total com Pessoal — {esfera} / {poder} · "
        f"{label_periodo} / {resultado.exercicio}"
    )


def gerar_alerta_docx(
    resultado: ResultadoConsultaRGF,
    nr_quadrimestre: int,
    nr_semestre: int,
) -> bytes:
    """Gera Termo de Alerta .docx com entes que extrapolaram os limites LRF.

    Args:
        resultado: Resultado da consulta RGF.
        nr_quadrimestre: Número do quadrimestre consultado.
        nr_semestre: Número do semestre consultado.

    Returns:
        Bytes do documento .docx.
    """
    doc = Document()
    _cabecalho(doc, "TERMO DE ALERTA — DESPESA COM PESSOAL", _subtitulo_padrao(resultado, nr_quadrimestre, nr_semestre))

    criticos = [
        e for e in resultado.entes_com_dados
        if e.situacao in (Situacao.ALERTA, Situacao.PRUDENCIAL, Situacao.MAXIMO)
    ]

    if not criticos:
        doc.add_paragraph(
            "Não foram identificados entes em situação de alerta, prudencial ou "
            "acima do limite máximo no período consultado."
        )
    else:
        doc.add_paragraph(
            "O Tribunal de Contas do Estado de Alagoas, com fundamento no Art. 59, §1º, II "
            "da Lei de Responsabilidade Fiscal (LC nº 101/2000), alerta os seguintes entes "
            "fiscais sobre o comprometimento da Despesa Total com Pessoal (DTP) em relação "
            "à Receita Corrente Líquida (RCL):"
        )
        doc.add_paragraph()

        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        hdr = table.rows[0].cells
        for i, texto in enumerate(["Ente Fiscal", "% DTP/RCL", "Período", "Situação"]):
            hdr[i].text = texto
            hdr[i].paragraphs[0].runs[0].bold = True

        for ente in sorted(criticos, key=lambda e: (-e.percentual_dtp, e.nome)):
            row = table.add_row().cells
            row[0].text = ente.nome
            row[1].text = _fmt_pct(ente.percentual_dtp)
            row[2].text = f"{ente.nr_periodo}º {'Quad.' if ente.periodo_tipo == 'Q' else 'Sem.'}"
            row[3].text = _LABEL_SITUACAO.get(ente.situacao, ente.situacao.value)

    _rodape_legal(doc)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def gerar_relatorio_docx(
    resultado: ResultadoConsultaRGF,
    nr_quadrimestre: int,
    nr_semestre: int,
) -> bytes:
    """Gera Relatório de Gestão Fiscal .docx com todos os entes e análise LC 178/2021.

    Args:
        resultado: Resultado da consulta RGF.
        nr_quadrimestre: Número do quadrimestre consultado.
        nr_semestre: Número do semestre consultado.

    Returns:
        Bytes do documento .docx.
    """
    doc = Document()
    _cabecalho(doc, "RELATÓRIO DE GESTÃO FISCAL — DESPESA COM PESSOAL", _subtitulo_padrao(resultado, nr_quadrimestre, nr_semestre))

    # Seção 1 — Resumo por situação
    doc.add_heading("1. Resumo por Situação", level=2)

    contagem: dict[Situacao, int] = {s: 0 for s in Situacao}
    for ente in resultado.entes_com_dados:
        contagem[ente.situacao] += 1

    t_resumo = doc.add_table(rows=1, cols=2)
    t_resumo.style = "Table Grid"
    hdr = t_resumo.rows[0].cells
    hdr[0].text, hdr[1].text = "Situação", "Quantidade de Entes"
    for cell in hdr:
        cell.paragraphs[0].runs[0].bold = True

    for sit in (Situacao.MAXIMO, Situacao.PRUDENCIAL, Situacao.ALERTA, Situacao.NORMAL):
        row = t_resumo.add_row().cells
        row[0].text = _LABEL_SITUACAO.get(sit, sit.value)
        row[1].text = str(contagem[sit])

    row_sd = t_resumo.add_row().cells
    row_sd[0].text = "Sem dados (inadimplentes)"
    row_sd[1].text = str(len(resultado.entes_sem_dados))

    doc.add_paragraph()

    # Seção 2 — Tabela completa
    doc.add_heading("2. Situação de Todos os Entes", level=2)

    if resultado.entes_com_dados:
        t_entes = doc.add_table(rows=1, cols=4)
        t_entes.style = "Table Grid"
        hdr2 = t_entes.rows[0].cells
        for i, texto in enumerate(["Ente Fiscal", "% DTP/RCL", "Período", "Situação"]):
            hdr2[i].text = texto
            hdr2[i].paragraphs[0].runs[0].bold = True

        for ente in resultado.entes_com_dados:
            row = t_entes.add_row().cells
            row[0].text = ente.nome
            row[1].text = _fmt_pct(ente.percentual_dtp)
            row[2].text = f"{ente.nr_periodo}º {'Quad.' if ente.periodo_tipo == 'Q' else 'Sem.'}"
            row[3].text = _LABEL_SITUACAO.get(ente.situacao, ente.situacao.value)
    else:
        doc.add_paragraph("Nenhum ente com dados disponíveis no período consultado.")

    doc.add_paragraph()

    # Seção 3 — Inadimplentes
    doc.add_heading("3. Entes sem Dados no SICONFI (Inadimplentes)", level=2)

    if resultado.entes_sem_dados:
        doc.add_paragraph(
            f"Os {len(resultado.entes_sem_dados)} entes a seguir não publicaram o "
            "Demonstrativo da Despesa com Pessoal (RGF Anexo 01) no período consultado:"
        )
        for nome in resultado.entes_sem_dados:
            doc.add_paragraph(f"• {nome}")
    else:
        doc.add_paragraph("Todos os entes consultados publicaram os dados no SICONFI.")

    doc.add_paragraph()

    # Seção 4 — Análise LC 178/2021
    doc.add_heading("4. Análise LC 178/2021 — Regime de Recuperação Fiscal", level=2)

    acima_limite = [e for e in resultado.entes_com_dados if e.situacao == Situacao.MAXIMO]
    limite_max = get_limite_maximo(resultado.esfera, resultado.poder)

    if acima_limite:
        doc.add_paragraph(
            "Os entes abaixo ultrapassaram o limite máximo de despesa com pessoal. "
            "Nos termos da Lei Complementar nº 178/2021 (PATF), esses entes podem estar "
            "sujeitos a restrições na obtenção de crédito e transferências voluntárias:"
        )
        for ente in sorted(acima_limite, key=lambda e: -e.percentual_dtp):
            excesso = ente.percentual_dtp - limite_max
            doc.add_paragraph(
                f"• {ente.nome}: {_fmt_pct(ente.percentual_dtp)} "
                f"(excede o limite máximo em {_fmt_pct(excesso)})"
            )
    else:
        doc.add_paragraph(
            "Nenhum ente ultrapassou o limite máximo de despesa com pessoal no período "
            "consultado. Não se aplica o Regime de Recuperação Fiscal previsto na LC 178/2021."
        )

    _rodape_legal(doc)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
