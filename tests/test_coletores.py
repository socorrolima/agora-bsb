import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scrapers"))
from comum import parse_valor_br, hash_texto, classificar_com_exclusoes

class TestParseValorBR:
    def test_valor_completo(self): assert parse_valor_br("R$ 1.234.567,89") == 1234567.89
    def test_valor_simples(self): assert parse_valor_br("1.234,56") == 1234.56
    def test_sem_centavos(self): assert parse_valor_br("R$ 500") == 500.0
    def test_vazio(self): assert parse_valor_br("") is None
    def test_texto_invalido(self): assert parse_valor_br("nao informado") is None
    def test_negativo(self): assert parse_valor_br("-1.000,50") == -1000.50
    def test_milhar_sem_decimal(self):
        resultado = parse_valor_br("1.000")
        assert resultado in (1.0, 1000.0)

class TestHashTexto:
    def test_deterministico(self): assert hash_texto("Construcao de UBS") == hash_texto("Construcao de UBS")
    def test_case_insensitive(self): assert hash_texto("SAUDE") == hash_texto("saude")
    def test_ignora_espacos_bordas(self): assert hash_texto("  escola  ") == hash_texto("escola")
    def test_tamanho(self): assert len(hash_texto("qualquer texto")) == 16

class TestClassificadorDODF:
    def setup_method(self):
        self.classificar = classificar_com_exclusoes
    def test_saude_valida(self): assert self.classificar("Portaria sobre atencao primaria nas UBS", "saude") == ["saude"]
    def test_falso_positivo_escola_de_samba(self): assert self.classificar("Apoio a escola de samba", "educacao") == []
    def test_educacao_valida(self): assert self.classificar("Ampliacao da merenda escolar na rede publica", "educacao") == ["educacao"]
