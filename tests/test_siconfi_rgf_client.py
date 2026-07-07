"""Testes do cliente RGF — distinção entre 'sem dados' e 'falha de consulta'."""

from unittest.mock import MagicMock, patch

import requests

import src.siconfi_rgf_client as rgf
from src.municipios_al import Ente
from src.siconfi_rgf_client import _fetch_rgf_ente, consultar_todos_entes

_ENTE_TESTE = Ente("2700300", "Arapiraca", "M", 243906)

_ITEM_DTP = {
    "conta": "DESPESA TOTAL COM PESSOAL - DTP (VIII) = (IIIa + IIIb)",
    "coluna": "% sobre a RCL Ajustada",
    "valor": 52.34,
}


def _make_mock_response(payload: dict):
    mock_resp = MagicMock()
    mock_resp.json.return_value = payload
    mock_resp.raise_for_status.return_value = None
    return mock_resp


class TestFetchRgfEnte:
    def test_resposta_vazia_retorna_lista_vazia_nao_none(self):
        """API respondeu OK sem itens: ente não enviou (≠ falha de consulta)."""
        with patch("src.siconfi_rgf_client.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response({"items": []})
            result = _fetch_rgf_ente(_ENTE_TESTE, 2024, 3, "Q", "E")
        assert result == []

    def test_falha_de_rede_retorna_none(self):
        """Falha após todas as tentativas: consulta inconclusiva (None)."""
        with (
            patch("src.siconfi_rgf_client.requests.get", side_effect=requests.ConnectionError("down")),
            patch("src.siconfi_rgf_client.time.sleep"),
        ):
            result = _fetch_rgf_ente(_ENTE_TESTE, 2024, 3, "Q", "E")
        assert result is None

    def test_resposta_com_itens_retorna_itens(self):
        with patch("src.siconfi_rgf_client.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response({"items": [_ITEM_DTP]})
            result = _fetch_rgf_ente(_ENTE_TESTE, 2024, 3, "Q", "E")
        assert result == [_ITEM_DTP]


class TestConsultarTodosEntes:
    """Um ente com falha de consulta NÃO pode ser listado como 'sem dados',
    pois entes_sem_dados é publicado no Termo de Alerta oficial."""

    _ENTES_FAKE = (
        Ente("0000001", "Ente Com Dados", "M", 1000),
        Ente("0000002", "Ente Sem Dados", "M", 2000),
        Ente("0000003", "Ente Com Falha", "M", 3000),
    )

    def _consultar(self, fake_fetch):
        with (
            patch.object(rgf, "ENTES_AL", self._ENTES_FAKE),
            patch.object(rgf, "_fetch_rgf_ente", side_effect=fake_fetch),
        ):
            return consultar_todos_entes(
                exercicio=2024,
                nr_quadrimestre=3,
                nr_semestre=2,
                esfera="M",
                poder="E",
                tipo_periodo="Q",
            )

    @staticmethod
    def _fake_fetch(ente, exercicio, nr_periodo, periodicidade, poder):
        return {
            "0000001": [_ITEM_DTP],
            "0000002": [],     # API OK, sem itens → não enviou
            "0000003": None,   # falha de rede → inconclusivo
        }[ente.id_ente]

    def test_ente_com_dados_classificado(self):
        resultado = self._consultar(self._fake_fetch)
        assert [e.nome for e in resultado.entes_com_dados] == ["Ente Com Dados"]

    def test_ente_sem_dados_apenas_quando_api_respondeu_vazio(self):
        resultado = self._consultar(self._fake_fetch)
        assert resultado.entes_sem_dados == ["Ente Sem Dados"]

    def test_falha_de_consulta_separada_de_sem_dados(self):
        resultado = self._consultar(self._fake_fetch)
        assert resultado.entes_falha_consulta == ["Ente Com Falha"]
        assert "Ente Com Falha" not in resultado.entes_sem_dados
