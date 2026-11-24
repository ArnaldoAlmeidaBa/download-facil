"""Testes unitários para o módulo de normalização de texto."""
from src.rules.normalizer import normalizar, limpar_texto, limitar_texto


def test_normalizar_remover_acentos_e_maiusculas():
    texto = "EDUCAÇÃO CONTEMPORÂNEA & Coordenação Pedagógica!"
    resultado = normalizar(texto)
    assert "educacao contemporanea" in resultado
    assert "coordenacao pedagogica" in resultado
    assert "!" not in resultado


def test_normalizar_pontuacao_e_espacos():
    texto = "relatorio_final---2026.pdf; (versao   2)"
    resultado = normalizar(texto)
    assert resultado == "relatorio final 2026 pdf versao 2"


def test_limpar_texto():
    texto = "  Linha 1 \n\n   Linha   2 \t  "
    assert limpar_texto(texto) == "Linha 1 Linha 2"


def test_limitar_texto():
    texto_curto = "Texto curto."
    assert limitar_texto(texto_curto, 50) == "Texto curto."

    texto_longo = "Palavra " * 30
    resultado = limitar_texto(texto_longo, 40)
    assert len(resultado) <= 45
    assert resultado.endswith("...")
