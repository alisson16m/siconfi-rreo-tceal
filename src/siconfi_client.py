"""
Cliente HTTP para a API SICONFI — RREO Anexo 1.

Nomes de coluna retornados pela API (verificados em 2026-05 com Arapiraca/2025,
id_ente=2700300):

  Receitas:
    'PREVISÃO INICIAL'                        → Previsão Inicial
    'PREVISÃO ATUALIZADA (a)'                 → Previsão Atualizada
    'No Bimestre (b)'                         → Receita arrecadada no bimestre
    'Até o Bimestre (c)'                      → Receita arrecadada acumulada (ano)
    '% (b/a)'                                 → % no bimestre s/ previsão atualizada
    '% (c/a)'                                 → % acumulado s/ previsão atualizada
    'SALDO (a-c)'                             → Saldo (previsão atualizada − arrecadado)

  Despesas:
    'DOTAÇÃO INICIAL (d)'                           → Dotação Inicial
    'DOTAÇÃO ATUALIZADA (e)'                        → Dotação Atualizada
    'DESPESAS EMPENHADAS NO BIMESTRE'               → Empenhado no bimestre
    'DESPESAS EMPENHADAS ATÉ O BIMESTRE (f)'        → Empenhado acumulado
    'DESPESAS LIQUIDADAS NO BIMESTRE'               → Liquidado no bimestre
    'DESPESAS LIQUIDADAS ATÉ O BIMESTRE (h)'        → Liquidado acumulado
    'DESPESAS PAGAS ATÉ O BIMESTRE (j)'             → Pago acumulado
    'INSCRITAS EM RESTOS A PAGAR NÃO PROCESSADOS (k)' → RPNP
    'SALDO (g) = (e-f)'                             → Saldo empenho
    'SALDO (i) = (e-h)'                             → Saldo liquidação

Divergências em relação ao briefing original:
  - 'PREVISÃO ATUALIZADA' → API retorna 'PREVISÃO ATUALIZADA (a)'
  - 'RECEITAS REALIZADAS - Até o Bimestre' → API retorna 'Até o Bimestre (c)'
  - 'DOTAÇÃO INICIAL' → API retorna 'DOTAÇÃO INICIAL (d)'
  - 'DOTAÇÃO ATUALIZADA' → API retorna 'DOTAÇÃO ATUALIZADA (e)'
  - 'DESPESAS EMPENHADAS - Até o Bimestre' → API retorna 'DESPESAS EMPENHADAS ATÉ O BIMESTRE (f)'
  - 'DESPESAS LIQUIDADAS - Até o Bimestre' → API retorna 'DESPESAS LIQUIDADAS ATÉ O BIMESTRE (h)'
  - 'DESPESAS PAGAS - Até o Bimestre' → API retorna 'DESPESAS PAGAS ATÉ O BIMESTRE (j)'
  - Campo 'data_publicacao' não existe na resposta da API.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo"
_TIMEOUT = 60
_MAX_RETRIES = 3
_RETRY_BASE_WAIT = 2.0


class SiconfiError(Exception):
    """Erro base do cliente SICONFI."""


class SiconfiNetworkError(SiconfiError):
    """Falha de rede ou HTTP ao consultar a API."""


class SiconfiEmptyResponseError(SiconfiError):
    """A API retornou lista de itens vazia para o ente/exercício informados."""


class SiconfiInvalidJsonError(SiconfiError):
    """A resposta da API não é JSON válido ou tem estrutura inesperada."""


@dataclass
class SiconfiResponse:
    items: list[dict[str, Any]]
    instituicao: str
    exercicio: int
    periodo: int
    url_chamada: str
    metadados: dict[str, Any] = field(default_factory=dict)


def fetch_rreo_anexo1(id_ente: str, exercicio: int, esfera: str) -> SiconfiResponse:
    """
    Consulta RREO Anexo 1 na API do SICONFI para o 6º bimestre.

    Args:
        id_ente: Código IBGE de 7 dígitos (município) ou '27' (estado AL).
        exercicio: Ano do exercício (ex: 2025).
        esfera: 'M' para município, 'E' para estado.

    Returns:
        SiconfiResponse com lista de itens e metadados.

    Raises:
        SiconfiEmptyResponseError: quando a API retorna lista vazia.
        SiconfiNetworkError: em falhas de rede após esgotadas as retentativas.
        SiconfiInvalidJsonError: quando a resposta não é JSON válido.
    """
    params = {
        "an_exercicio": exercicio,
        "nr_periodo": 6,
        "co_tipo_demonstrativo": "RREO",
        "no_anexo": "RREO-Anexo 01",
        "id_ente": str(id_ente),
        "co_esfera": esfera,
        "co_poder": "E",
    }

    last_exception: Exception | None = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.get(_BASE_URL, params=params, timeout=_TIMEOUT)
            resp.raise_for_status()

            try:
                data = resp.json()
            except ValueError as exc:
                raise SiconfiInvalidJsonError(
                    f"Resposta da API não é JSON válido: {exc}"
                ) from exc

            items = data.get("items")
            if items is None:
                raise SiconfiInvalidJsonError(
                    "Campo 'items' ausente na resposta da API."
                )
            if len(items) == 0:
                raise SiconfiEmptyResponseError(
                    f"A API não retornou dados para o ente {id_ente} "
                    f"no 6º bimestre de {exercicio}."
                )

            instituicao = items[0].get("instituicao", "")
            metadados = {
                k: data[k]
                for k in ("hasMore", "count", "limit", "offset")
                if k in data
            }

            return SiconfiResponse(
                items=items,
                instituicao=instituicao,
                exercicio=exercicio,
                periodo=6,
                url_chamada=resp.url,
                metadados=metadados,
            )

        except SiconfiEmptyResponseError:
            raise
        except SiconfiInvalidJsonError:
            raise
        except requests.HTTPError as exc:
            raise SiconfiNetworkError(
                f"Erro HTTP {exc.response.status_code} ao consultar a API."
            ) from exc
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_exception = exc
            if attempt < _MAX_RETRIES:
                wait = _RETRY_BASE_WAIT * (2 ** (attempt - 1))
                logger.warning(
                    "Tentativa %d/%d falhou (%s). Aguardando %.0fs antes de retry...",
                    attempt,
                    _MAX_RETRIES,
                    type(exc).__name__,
                    wait,
                )
                time.sleep(wait)

    raise SiconfiNetworkError(
        f"Falha na conexão com a API do SICONFI após {_MAX_RETRIES} tentativas. "
        f"Último erro: {last_exception}"
    ) from last_exception
