"""Testes unitários para extratores e utilitários de arquivos."""
from pathlib import Path
from src.config import formatar_tamanho, classificar_tipo
from src.readers.text_reader import ler_txt
from src.readers import ler_conteudo_textual


def test_formatar_tamanho():
    assert formatar_tamanho(500) == "500 B"
    assert formatar_tamanho(2048) == "2.0 KB"
    assert formatar_tamanho(5 * 1024 * 1024) == "5.0 MB"


def test_classificar_tipo():
    assert classificar_tipo(Path("documento.pdf")) == "DOCUMENTO"
    assert classificar_tipo(Path("planilha.xlsx")) == "PLANILHA"
    assert classificar_tipo(Path("foto.png")) == "IMAGEM"
    assert classificar_tipo(Path("desktop.ini")) == "IGNORAR"
    assert classificar_tipo(Path("programa.exe")) == "INSTALADOR"
    assert classificar_tipo(Path("desconhecido.xyz")) == "OUTRO"


def test_ler_txt(tmp_path):
    arquivo = tmp_path / "teste.txt"
    arquivo.write_text("Conteúdo de teste para o leitor de texto puro.", encoding="utf-8")
    assert ler_txt(arquivo) == "Conteúdo de teste para o leitor de texto puro."


def test_ler_conteudo_formato_nao_suportado(tmp_path):
    arquivo = tmp_path / "teste.xyz"
    arquivo.write_text("dummy", encoding="utf-8")
    conteudo, estado = ler_conteudo_textual(arquivo)
    assert conteudo == ""
    assert estado == "NAO_SUPORTADO_NESTA_VERSAO"
