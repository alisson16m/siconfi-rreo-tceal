"""Constantes LRF e classificador de situação fiscal — RGF Despesa com Pessoal."""

from enum import Enum
from typing import NamedTuple


class Situacao(Enum):
    NORMAL = "normal"
    ALERTA = "alerta"
    PRUDENCIAL = "prudencial"
    MAXIMO = "maximo"
    SEM_DADOS = "sem_dados"


class _Limite(NamedTuple):
    maximo: float
    prudencial: float
    alerta: float


# Limites por (esfera, poder) — LC 101/2000, Arts. 19, 20, 22
_LIMITES: dict[tuple[str, str], _Limite] = {
    ("M", "E"): _Limite(54.00, 51.30, 48.60),
    ("M", "L"): _Limite(6.00, 5.70, 5.40),
    ("E", "E"): _Limite(49.00, 46.55, 44.10),
    ("E", "L"): _Limite(3.00, 2.85, 2.70),
}

_ORDINAL = {1: "1º", 2: "2º", 3: "3º", 4: "4º", 5: "5º", 6: "6º"}


def classificar(percentual: float, esfera: str, poder: str) -> Situacao:
    """Classifica situação do ente conforme limites LRF.

    Args:
        percentual: % DTP/RCL (ex: 52.34 para 52,34%).
        esfera: 'M' municipal | 'E' estadual.
        poder: 'E' executivo | 'L' legislativo.

    Returns:
        Situacao correspondente ao percentual informado.
    """
    limite = _LIMITES.get((esfera, poder))
    if limite is None:
        return Situacao.NORMAL
    if percentual >= limite.maximo:
        return Situacao.MAXIMO
    if percentual >= limite.prudencial:
        return Situacao.PRUDENCIAL
    if percentual >= limite.alerta:
        return Situacao.ALERTA
    return Situacao.NORMAL


def get_limite_maximo(esfera: str, poder: str) -> float:
    """Retorna limite máximo LRF (%) para esfera e poder informados."""
    limite = _LIMITES.get((esfera, poder))
    return limite.maximo if limite else 0.0


def label_periodo_completo(
    nr_quadrimestre: int, nr_semestre: int, tipo_periodo: str = "A"
) -> str:
    """Retorna label do período consultado, conforme o tipo de período selecionado.

    Args:
        nr_quadrimestre: Número do quadrimestre consultado.
        nr_semestre: Número do semestre consultado.
        tipo_periodo: 'Q' só quadrimestral | 'S' só semestral | 'A' ambos (padrão).

    Exemplo: label_periodo_completo(3, 2, "A") → '3º Quadrimestre e 2º Semestre'
    Exemplo: label_periodo_completo(3, 2, "Q") → '3º Quadrimestre'
    Exemplo: label_periodo_completo(3, 2, "S") → '2º Semestre'
    """
    q = _ORDINAL.get(nr_quadrimestre, f"{nr_quadrimestre}º")
    s = _ORDINAL.get(nr_semestre, f"{nr_semestre}º")
    if tipo_periodo == "Q":
        return f"{q} Quadrimestre"
    if tipo_periodo == "S":
        return f"{s} Semestre"
    return f"{q} Quadrimestre e {s} Semestre"
