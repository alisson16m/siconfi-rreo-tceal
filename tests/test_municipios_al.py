"""Testes de integridade da lista de entes de Alagoas."""

from src.municipios_al import ENTES_AL, Ente


class TestEntesAL:
    def test_total_de_entes(self):
        assert len(ENTES_AL) == 103

    def test_um_ente_estadual(self):
        estaduais = [e for e in ENTES_AL if e.esfera == "E"]
        assert len(estaduais) == 1

    def test_102_municipios(self):
        municipais = [e for e in ENTES_AL if e.esfera == "M"]
        assert len(municipais) == 102

    def test_estado_alagoas_presente(self):
        estado = next((e for e in ENTES_AL if e.id_ente == "27"), None)
        assert estado is not None
        assert estado.nome == "Alagoas"
        assert estado.esfera == "E"

    def test_arapiraca_presente(self):
        arapiraca = next((e for e in ENTES_AL if e.id_ente == "2700300"), None)
        assert arapiraca is not None
        assert "Arapiraca" in arapiraca.nome
        assert arapiraca.esfera == "M"

    def test_id_ente_sao_strings(self):
        for e in ENTES_AL:
            assert isinstance(e.id_ente, str), f"id_ente não é str: {e}"

    def test_todos_campos_preenchidos(self):
        for e in ENTES_AL:
            assert e.id_ente, f"id_ente vazio: {e}"
            assert e.nome, f"nome vazio: {e}"
            assert e.esfera in ("M", "E"), f"esfera inválida: {e}"
            assert e.populacao > 0, f"populacao inválida: {e}"

    def test_ids_unicos(self):
        ids = [e.id_ente for e in ENTES_AL]
        assert len(ids) == len(set(ids)), "IDs duplicados encontrados"

    def test_ente_e_namedtuple(self):
        e = ENTES_AL[0]
        assert isinstance(e, Ente)
        assert hasattr(e, "id_ente")
        assert hasattr(e, "nome")
        assert hasattr(e, "esfera")
        assert hasattr(e, "populacao")
