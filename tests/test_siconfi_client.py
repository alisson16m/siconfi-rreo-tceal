"""Testes do cliente SICONFI (sem chamadas reais à API)."""

import json
import pathlib
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.siconfi_client import (
    SiconfiEmptyResponseError,
    SiconfiInvalidJsonError,
    SiconfiNetworkError,
    SiconfiResponse,
    fetch_data_status,
    fetch_rreo_anexo1,
)

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture()
def arapiraca_payload():
    with open(FIXTURES_DIR / "arapiraca_2025.json", encoding="utf-8") as f:
        return json.load(f)


def _make_mock_response(payload: dict, status_code: int = 200):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.url = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo?..."
    mock_resp.json.return_value = payload
    mock_resp.raise_for_status.return_value = None
    return mock_resp


class TestFetchRreoAnexo1:
    def test_retorna_siconfi_response_com_itens(self, arapiraca_payload):
        with patch("src.siconfi_client.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(arapiraca_payload)
            result = fetch_rreo_anexo1("2700300", 2025, "M")

        assert isinstance(result, SiconfiResponse)
        assert len(result.items) == arapiraca_payload["count"]
        assert result.exercicio == 2025
        assert result.periodo == 6
        assert "Arapiraca" in result.instituicao

    def test_parametros_corretos_enviados_a_api(self, arapiraca_payload):
        with patch("src.siconfi_client.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(arapiraca_payload)
            fetch_rreo_anexo1("2700300", 2025, "M")

        call_kwargs = mock_get.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs.args[1]
        assert params["nr_periodo"] == 6
        assert params["co_tipo_demonstrativo"] == "RREO"
        assert params["no_anexo"] == "RREO-Anexo 01"
        assert params["co_poder"] == "E"
        assert params["co_esfera"] == "M"
        assert params["id_ente"] == "2700300"

    def test_items_contem_campos_esperados(self, arapiraca_payload):
        with patch("src.siconfi_client.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(arapiraca_payload)
            result = fetch_rreo_anexo1("2700300", 2025, "M")

        item = result.items[0]
        for campo in ("coluna", "cod_conta", "conta", "valor"):
            assert campo in item, f"Campo '{campo}' ausente no item"

    def test_colunas_api_incluem_campos_esperados(self, arapiraca_payload):
        with patch("src.siconfi_client.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(arapiraca_payload)
            result = fetch_rreo_anexo1("2700300", 2025, "M")

        colunas = {i["coluna"] for i in result.items}
        esperadas = {
            "PREVISÃO INICIAL",
            "PREVISÃO ATUALIZADA (a)",
            "Até o Bimestre (c)",
            "DOTAÇÃO INICIAL (d)",
            "DOTAÇÃO ATUALIZADA (e)",
            "DESPESAS EMPENHADAS ATÉ O BIMESTRE (f)",
            "DESPESAS LIQUIDADAS ATÉ O BIMESTRE (h)",
            "DESPESAS PAGAS ATÉ O BIMESTRE (j)",
            "INSCRITAS EM RESTOS A PAGAR NÃO PROCESSADOS (k)",
        }
        ausentes = esperadas - colunas
        assert not ausentes, f"Colunas ausentes na resposta: {ausentes}"

    def test_levanta_empty_response_quando_items_vazio(self):
        payload = {"items": [], "hasMore": False, "count": 0, "limit": 5000, "offset": 0}
        with patch("src.siconfi_client.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(payload)
            with pytest.raises(SiconfiEmptyResponseError):
                fetch_rreo_anexo1("9999999", 2025, "M")

    def test_levanta_invalid_json_quando_campo_items_ausente(self):
        payload = {"data": "sem campo items"}
        with patch("src.siconfi_client.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(payload)
            with pytest.raises(SiconfiInvalidJsonError, match="'items'"):
                fetch_rreo_anexo1("2700300", 2025, "M")

    def test_levanta_network_error_em_http_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        http_error = requests.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = http_error

        with patch("src.siconfi_client.requests.get") as mock_get:
            mock_get.return_value = mock_resp
            with pytest.raises(SiconfiNetworkError, match="500"):
                fetch_rreo_anexo1("2700300", 2025, "M")

    def test_retry_em_timeout_e_levanta_apos_max_tentativas(self):
        with patch("src.siconfi_client.requests.get") as mock_get, \
             patch("src.siconfi_client.time.sleep") as mock_sleep:
            mock_get.side_effect = requests.Timeout("timeout simulado")
            with pytest.raises(SiconfiNetworkError, match="3 tentativas"):
                fetch_rreo_anexo1("2700300", 2025, "M")

        assert mock_get.call_count == 3
        # Deve ter dormido 2 vezes (entre as 3 tentativas)
        assert mock_sleep.call_count == 2
        # Backoff: 2s na 1a espera, 4s na 2a
        waits = [call.args[0] for call in mock_sleep.call_args_list]
        assert waits == [2.0, 4.0]

    def test_retry_em_connection_error(self):
        with patch("src.siconfi_client.requests.get") as mock_get, \
             patch("src.siconfi_client.time.sleep"):
            mock_get.side_effect = requests.ConnectionError("sem conexão")
            with pytest.raises(SiconfiNetworkError):
                fetch_rreo_anexo1("2700300", 2025, "M")

        assert mock_get.call_count == 3

    def test_sem_retry_em_empty_response(self):
        payload = {"items": [], "hasMore": False, "count": 0, "limit": 5000, "offset": 0}
        with patch("src.siconfi_client.requests.get") as mock_get, \
             patch("src.siconfi_client.time.sleep") as mock_sleep:
            mock_get.return_value = _make_mock_response(payload)
            with pytest.raises(SiconfiEmptyResponseError):
                fetch_rreo_anexo1("9999999", 2025, "M")

        assert mock_get.call_count == 1
        mock_sleep.assert_not_called()

    def test_metadados_presentes(self, arapiraca_payload):
        with patch("src.siconfi_client.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(arapiraca_payload)
            result = fetch_rreo_anexo1("2700300", 2025, "M")

        assert "count" in result.metadados
        assert result.metadados["count"] == arapiraca_payload["count"]


_EXTRATO_PAYLOAD = {
    "items": [
        {
            "exercicio": 2025, "cod_ibge": 2700300, "populacao": 235085,
            "instituicao": "Prefeitura Municipal de Arapiraca - AL",
            "entregavel": "Relatório de Gestão Fiscal",
            "periodo": 6, "periodicidade": "B",
            "status_relatorio": None,
            "data_status": "2026-01-15T10:00:00Z",
            "forma_envio": "CSV", "tipo_relatorio": "P",
        },
        {
            "exercicio": 2025, "cod_ibge": 2700300, "populacao": 235085,
            "instituicao": "Prefeitura Municipal de Arapiraca - AL",
            "entregavel": "Relatório Resumido de Execução Orçamentária",
            "periodo": 5, "periodicidade": "B",
            "status_relatorio": None,
            "data_status": "2025-11-28T12:00:00Z",
            "forma_envio": "CSV", "tipo_relatorio": "P",
        },
        {
            "exercicio": 2025, "cod_ibge": 2700300, "populacao": 235085,
            "instituicao": "Prefeitura Municipal de Arapiraca - AL",
            "entregavel": "Relatório Resumido de Execução Orçamentária",
            "periodo": 6, "periodicidade": "B",
            "status_relatorio": None,
            "data_status": "2026-01-30T11:34:12Z",
            "forma_envio": "CSV", "tipo_relatorio": "P",
        },
    ],
    "hasMore": False, "count": 3, "limit": 5000, "offset": 0,
}


class TestFetchDataStatus:
    def test_retorna_data_status_do_rreo_sexto_bimestre(self):
        with patch("src.siconfi_client.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(_EXTRATO_PAYLOAD)
            result = fetch_data_status("2700300", 2025)

        assert result == "2026-01-30T11:34:12Z"

    def test_ignora_outros_entregaveis_e_periodos(self):
        payload = {
            "items": [
                {**_EXTRATO_PAYLOAD["items"][0]},  # RGF período 6 — deve ignorar
                {**_EXTRATO_PAYLOAD["items"][1]},  # RREO período 5 — deve ignorar
            ],
            "hasMore": False, "count": 2, "limit": 5000, "offset": 0,
        }
        with patch("src.siconfi_client.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(payload)
            result = fetch_data_status("2700300", 2025)

        assert result is None

    def test_retorna_none_quando_lista_vazia(self):
        payload = {"items": [], "hasMore": False, "count": 0, "limit": 5000, "offset": 0}
        with patch("src.siconfi_client.requests.get") as mock_get:
            mock_get.return_value = _make_mock_response(payload)
            result = fetch_data_status("2700300", 2025)

        assert result is None

    def test_retorna_none_em_falha_de_rede_sem_excecao(self):
        with patch("src.siconfi_client.requests.get") as mock_get:
            mock_get.side_effect = requests.ConnectionError("sem rede")
            result = fetch_data_status("2700300", 2025)

        assert result is None

    def test_retorna_none_em_http_error_sem_excecao(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("500")
        with patch("src.siconfi_client.requests.get") as mock_get:
            mock_get.return_value = mock_resp
            result = fetch_data_status("2700300", 2025)

        assert result is None

    def test_propaga_erro_de_rede_quando_raise_on_error(self):
        with patch("src.siconfi_client.requests.get") as mock_get:
            mock_get.side_effect = requests.ConnectionError("sem rede")
            with pytest.raises(requests.ConnectionError):
                fetch_data_status("2700300", 2025, raise_on_error=True)


class TestFetchStatusTodosEntesAno:
    """Painel de Entregas: falha de consulta (None) não pode virar 'não entregou' (False)."""

    @staticmethod
    def _fake_get(url, params=None, timeout=None):
        eid = params["id_ente"]
        if eid == "1111111":  # entregou
            return _make_mock_response(_EXTRATO_PAYLOAD)
        if eid == "2222222":  # API OK, sem entrega
            return _make_mock_response({"items": [], "count": 0})
        raise requests.ConnectionError("sem rede")  # 3333333 — falha

    def test_tres_estados_distintos(self):
        from src.siconfi_client import fetch_status_todos_entes_ano

        with patch("src.siconfi_client.requests.get", side_effect=self._fake_get):
            resultado = fetch_status_todos_entes_ano(
                2025, frozenset({"1111111", "2222222", "3333333"})
            )

        assert resultado["1111111"] is True
        assert resultado["2222222"] is False
        assert resultado["3333333"] is None  # inconclusivo, não "não entregou"
