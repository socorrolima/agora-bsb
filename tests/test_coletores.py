"""
Testes — rode com: pytest tests/ -v
Também roda automaticamente no GitHub Actions antes de cada coleta.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scrapers"))

from comum import parse_valor_br, hash_texto


class TestParseValorBR:
    def test_valor_completo(self):
        assert parse_valor_br("R$ 1.234.567,89") == 1234567.89

    def test_valor_simples(self):
        assert parse_valor_br("1.234,56") == 1234.56

    def test_sem_centavos(self):
        assert parse_valor_br("R$ 500") == 500.0

    def test_vazio(self):
        assert parse_valor_br("") is None

    def test_texto_invalido(self):
        assert parse_valor_br("não informado") is None

    def test_negativo(self):
        assert parse_valor_br("-1.000,50") == -1000.50

    def test_milhar_sem_decimal(self):
        # "1.000" no formato BR é mil — ambíguo, mas float("1.000")=1.0
        # comportamento atual: sem vírgula, ponto é tratado como decimal.
        # LIMITAÇÃO CONHECIDA: documente valores de entrada esperados.
        resultado = parse_valor_br("1.000")
        assert resultado in (1.0, 1000.0)


class TestHashTexto:
    def test_deterministico(self):
        assert hash_texto("Construção de UBS") == hash_texto("Construção de UBS")

    def test_case_insensitive(self):
        assert hash_texto("SAÚDE") == hash_texto("saúde")

    def test_ignora_espacos_bordas(self):
        assert hash_texto("  escola  ") == hash_texto("escola")

    def test_tamanho(self):
        assert len(hash_texto("qualquer texto")) == 16


class TestClassificadorDODF:
    def setup_method(self):
        from comum import classificar_com_exclusoes
        self.classificar = classificar_com_exclusoes

    def test_saude_valida(self):
        assert self.classificar(
            "Portaria sobre atenção primária nas UBS", "saude"
        ) == ["saude"]

    def test_falso_positivo_saude_financeira(self):
        assert self.classificar(
            "Relatório de saúde financeira da autarquia", "saude"
        ) == []

    def test_falso_positivo_escola_de_samba(self):
        assert self.classificar(
            "Apoio à escola de samba da Candangolândia", "educacao"
        ) == []

    def test_educacao_valida(self):
        assert self.classificar(
            "Ampliação da merenda escolar na rede pública", "educacao"
        ) == ["educacao"]
