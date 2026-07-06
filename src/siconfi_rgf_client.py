"""
Cliente paralelo para o endpoint /tt/rgf da API SICONFI — RGF Anexo 01.

Estrutura dos itens retornados pela API (verificar campo 'rotulo' e 'coluna' se a
API mudar — use o snippet de diagnóstico no README para inspecionar valores reais):

  Linha-chave: rotulo contém "DESPESA TOTAL COM PESSOAL" e "DTP"
  Coluna-chave: coluna contém "%" e "RCL"
  Valor: percentual DTP/RCL (ex: 52.34 para 52,34%)

Constante _ROTULO_DTP pode ser ajustada se o rótulo da API mudar entre versões.
"""

import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

import requests

from .municipios_al import ENTES_AL, Ente
from .rgf_limites import Situacao, classificar

logger = logging.getLogger(__name__)

_BASE_URL_RGF = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rgf"
_TIMEOUT = 60
_MAX_RETRIES = 3
_RETRY_BASE_WAIT = 2.0
_MAX_WORKERS = 8

# Rótulo da linha DTP — ajustar aqui se a API usar nomenclatura diferente
_ROTULO_DTP = "DESPESA TOTAL COM PESSOAL - DTP"


@dataclass
class ResultadoEnteRGF:
    """Resultado da consulta RGF para um único ente."""

    id_ente: str
    nome: str
    percentual_dtp: float
    situacao: Situacao
    periodo_tipo: str  # "Q" quadrimestral | "S" semestral
    nr_periodo: int
    populacao: int = 0


@dataclass
class ResultadoConsultaRGF:
    """Resultado agregado da consulta RGF para todos os entes do esfera."""

    entes_com_dados: list[ResultadoEnteRGF]
    entes_sem_dados: list[str]  # nomes dos entes sem dados disponíveis
    exercicio: int
    esfera: str
    poder: str


def _extrair_percentual_dtp(items: list[dict]) -> float | None:
    """Extrai percentual DTP/RCL dos itens da API.

    A API retorna o campo 'conta' (não 'rotulo') com a descrição da linha.
    Linha DTP: conta contém 'DESPESA TOTAL COM PESSOAL' e 'DTP'.
    Coluna percentual: coluna contém '% sobre a RCL' (case-insensitive).
    """
    for item in items:
        conta  = (item.get("conta")  or "").upper().strip()
        coluna = (item.get("coluna") or "").upper().strip()
        valor  = item.get("valor")

        if valor is None:
            continue
        if not ("DESPESA TOTAL COM PESSOAL" in conta and "DTP" in conta):
            continue
        if not ("%" in coluna and "RCL" in coluna):
            continue

        try:
            pct = float(valor)
            if pct >= 0.0:
                return pct
        except (TypeError, ValueError):
            pass

    return None


def _fetch_rgf_ente(
    ente: Ente,
    exercicio: int,
    nr_periodo: int,
    periodicidade: str,
    poder: str,
) -> list[dict] | None:
    """Busca itens RGF para um ente/período. Retorna lista de itens ou None.

    Args:
        periodicidade: 'Q' quadrimestral | 'S' semestral (parâmetro obrigatório da API).
    """
    params = {
        "an_exercicio": exercicio,
        "in_periodicidade": periodicidade,
        "nr_periodo": nr_periodo,
        "co_tipo_demonstrativo": "RGF",
        "no_anexo": "RGF-Anexo 01",
        "co_poder": poder,
        "id_ente": ente.id_ente,
    }
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.get(_BASE_URL_RGF, params=params, timeout=_TIMEOUT)
            resp.raise_for_status()
            items = resp.json().get("items", [])
            return items if items else None
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_BASE_WAIT * (2 ** (attempt - 1)))
        except Exception as exc:
            logger.warning("Erro ao consultar RGF ente %s período %d: %s", ente.id_ente, nr_periodo, exc)
            return None
    logger.warning(
        "Falha após %d tentativas ente %s período %d: %s",
        _MAX_RETRIES, ente.id_ente, nr_periodo, last_exc,
    )
    return None


def consultar_todos_entes(
    exercicio: int,
    nr_quadrimestre: int,
    nr_semestre: int,
    esfera: str,
    poder: str,
    tipo_periodo: str,
    on_progress: Callable[[int, int], None] | None = None,
) -> ResultadoConsultaRGF:
    """Consulta RGF Anexo 01 para todos os entes da esfera em paralelo.

    Args:
        exercicio: Ano do exercício (ex: 2024).
        nr_quadrimestre: Número do quadrimestre (1, 2 ou 3).
        nr_semestre: Número do semestre (1 ou 2).
        esfera: 'M' municipal | 'E' estadual.
        poder: 'E' executivo | 'L' legislativo.
        tipo_periodo: 'Q' só quadrimestral, 'S' só semestral, 'A' ambos (Q com fallback S).
        on_progress: Callback opcional chamado com (concluídos, total) a cada ente processado.

    Returns:
        ResultadoConsultaRGF com entes com e sem dados, ordenados por nome.
    """
    entes_alvo = [e for e in ENTES_AL if e.esfera == esfera]
    total = len(entes_alvo)

    entes_com_dados: list[ResultadoEnteRGF] = []
    entes_sem_dados: list[str] = []
    concluidos = 0

    def _processar(ente: Ente) -> ResultadoEnteRGF | None:
        if tipo_periodo == "Q":
            periodos: list[tuple[int, str]] = [(nr_quadrimestre, "Q")]
        elif tipo_periodo == "S":
            periodos = [(nr_semestre, "S")]
        else:  # "A" — tenta Q primeiro, S como fallback
            periodos = [(nr_quadrimestre, "Q"), (nr_semestre, "S")]

        for nr_periodo, tipo in periodos:
            items = _fetch_rgf_ente(ente, exercicio, nr_periodo, tipo, poder)
            if items is None:
                continue
            pct = _extrair_percentual_dtp(items)
            if pct is None:
                continue
            return ResultadoEnteRGF(
                id_ente=ente.id_ente,
                nome=ente.nome,
                percentual_dtp=pct,
                situacao=classificar(pct, esfera, poder),
                periodo_tipo=tipo,
                nr_periodo=nr_periodo,
                populacao=ente.populacao,
            )
        return None

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        futures = {executor.submit(_processar, e): e for e in entes_alvo}
        for future in as_completed(futures):
            ente = futures[future]
            try:
                resultado = future.result()
            except Exception as exc:
                logger.warning("Erro não tratado ente %s: %s", ente.nome, exc)
                resultado = None

            concluidos += 1
            if on_progress:
                try:
                    on_progress(concluidos, total)
                except Exception:
                    pass

            if resultado is not None:
                entes_com_dados.append(resultado)
            else:
                entes_sem_dados.append(ente.nome)

    entes_com_dados.sort(key=lambda r: r.nome)
    entes_sem_dados.sort()

    return ResultadoConsultaRGF(
        entes_com_dados=entes_com_dados,
        entes_sem_dados=entes_sem_dados,
        exercicio=exercicio,
        esfera=esfera,
        poder=poder,
    )
