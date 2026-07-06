# Termo de Alerta — Seção de Entes Sem Dados Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a paragraph plus a numbered list of entes that have not sent data to SICONFI at the end of the Termo de Alerta (`gerar_alerta_docx`).

**Architecture:** `gerar_alerta_docx` in `src/rgf_report_builder.py` already builds a `python-docx` `Document` from an institutional template and appends a table of critical entes. This plan adds one more block appended to the same `doc` object, right after the critical-entes table loop and before `doc.save(buf)`. No new files, no template changes.

**Tech Stack:** Python 3.11, `python-docx`, `pytest`.

Spec reference: `docs/superpowers/specs/2026-07-06-alerta-entes-sem-dados-design.md`

---

### Task 1: Write failing tests for the new section

**Files:**
- Create: `tests/test_rgf_report_builder.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_rgf_report_builder.py -v`
Expected: `test_alerta_com_entes_sem_dados_inclui_texto_e_lista_numerada` FAILS (assertion — no matching paragraph found); `test_alerta_sem_entes_sem_dados_nao_inclui_secao` PASSES trivially (nothing to assert against yet, but confirm no import errors).

- [ ] **Step 3: Commit**

```bash
git add tests/test_rgf_report_builder.py
git commit -m "test: add coverage for entes-sem-dados section in Termo de Alerta"
```

---

### Task 2: Implement the section in `gerar_alerta_docx`

**Files:**
- Modify: `src/rgf_report_builder.py:263-276`

- [ ] **Step 1: Add the new block right after the critical-entes loop, before `buf = io.BytesIO()`**

Current code at the end of `gerar_alerta_docx` (`src/rgf_report_builder.py:263-276`):

```python
    for ente in sorted(criticos, key=lambda e: (-e.percentual_dtp, e.nome)):
        situacao_label = _LABEL_SITUACAO_MODELO.get(ente.situacao, ente.situacao.value)
        percentual_fmt = f"     {_fmt_pct(ente.percentual_dtp).replace('%', '')} "
        _adicionar_linha_tabela_modelo(
            tabela,
            unidade_gestora=f"{unidade_gestora_label} ",
            municipio=ente.nome,
            percentual=percentual_fmt,
            situacao=situacao_label,
        )

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
```

Replace with:

```python
    for ente in sorted(criticos, key=lambda e: (-e.percentual_dtp, e.nome)):
        situacao_label = _LABEL_SITUACAO_MODELO.get(ente.situacao, ente.situacao.value)
        percentual_fmt = f"     {_fmt_pct(ente.percentual_dtp).replace('%', '')} "
        _adicionar_linha_tabela_modelo(
            tabela,
            unidade_gestora=f"{unidade_gestora_label} ",
            municipio=ente.nome,
            percentual=percentual_fmt,
            situacao=situacao_label,
        )

    # ── Entes sem dados no SICONFI ────────────────────────────────────────────
    if resultado.entes_sem_dados:
        doc.add_paragraph()
        doc.add_paragraph(
            "Relacionam-se abaixo os entes que, até a data de extração dos "
            f"dados ({data_str}), não haviam enviado ao SICONFI as "
            "informações referentes à Despesa com Pessoal (RGF Anexo 01) "
            "no período consultado:"
        )
        for i, nome in enumerate(resultado.entes_sem_dados, start=1):
            doc.add_paragraph(f"{i}. {nome}")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
```

Note: `data_str` is already defined earlier in the same function (`src/rgf_report_builder.py:219`, `data_str = data_extracao or datetime.now().strftime('%d/%m/%Y')`) — no new variable needed.

- [ ] **Step 2: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest tests/test_rgf_report_builder.py -v`
Expected: both tests PASS.

- [ ] **Step 3: Run full test suite**

Run: `.venv\Scripts\python.exe -m pytest --tb=short -q`
Expected: all tests pass, no regressions.

- [ ] **Step 4: Commit**

```bash
git add src/rgf_report_builder.py
git commit -m "feat: list entes sem dados no Termo de Alerta de Despesa com Pessoal"
```

---

### Task 3: Update VERSION and CHANGELOG

**Files:**
- Modify: `VERSION`
- Modify: `CHANGELOG.md:8-10`

- [ ] **Step 1: Bump VERSION**

Current content of `VERSION`:
```
1.5.3
```

Replace with:
```
1.5.4
```

- [ ] **Step 2: Add changelog entry**

Current top of `CHANGELOG.md`:

```markdown
## [Unreleased]

---

## [1.5.3] - 2026-07-06
```

Replace with:

```markdown
## [Unreleased]

---

## [1.5.4] - 2026-07-06

### Added
- Termo de Alerta de Despesa com Pessoal agora lista, ao final do documento, os entes que não enviaram dados ao SICONFI até a data de extração, com um parágrafo introdutório seguido de lista numerada. Antes, essa informação só aparecia no Relatório de Gestão Fiscal completo.

---

## [1.5.3] - 2026-07-06
```

- [ ] **Step 3: Commit**

```bash
git add VERSION CHANGELOG.md
git commit -m "chore: bump version to 1.5.4"
```

---

## Self-Review Notes

- **Spec coverage:** paragraph text (Task 2), numbered list (Task 2), placement after critical-entes table before save (Task 2), empty-list-skips-section behavior (Task 1 test + Task 2 `if` guard) — all covered.
- **Placeholder scan:** none found — all code blocks are complete and copy-pasteable.
- **Type consistency:** `resultado.entes_sem_dados` is `list[str]` per `ResultadoConsultaRGF` (`src/siconfi_rgf_client.py`), matches usage in both test fixture and implementation.
