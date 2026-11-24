"""Testes unitários para os classificadores de tipo e assunto."""
from pathlib import Path
from src.rules.classifiers import (
    identificar_tipo_documental,
    analisar_assunto,
    gerar_descricao,
)


def test_identificar_tipo_documental_tcc():
    texto = (
        "Trabalho de Conclusão de Curso apresentado como requisito parcial "
        "para obtenção do título. Referencial Teórico e Metodologia aplicada. "
        "Considerações finais satisfatórias."
    )
    resultado = identificar_tipo_documental(texto)
    assert resultado["tipo_documental"] == "TCC"
    assert resultado["confianca_tipo_documental"] == "ALTA"


def test_identificar_tipo_documental_matriz():
    texto = (
        "Matriz de Conteúdos Curriculares da Disciplina de Informática. "
        "Carga Horária: 60h. Eixo Tecnológico."
    )
    resultado = identificar_tipo_documental(texto)
    assert resultado["tipo_documental"] == "MATRIZ_DE_CONTEUDOS"


def test_identificar_tipo_documental_nao_identificado():
    texto = "Receita de bolo de cenoura com cobertura de chocolate."
    resultado = identificar_tipo_documental(texto)
    assert resultado["tipo_documental"] == "NAO_IDENTIFICADO"
    assert resultado["confianca_tipo_documental"] == "BAIXA"


def test_analisar_assunto_concordante():
    arquivo = Path("oficio_sec_012.pdf")
    conteudo = "Ofício expedido pela SEC Bahia para providências pedagógicas."
    resultado = analisar_assunto(arquivo, conteudo, "LIDO")
    assert resultado["assunto"] == "OFICIO_SEC"
    assert resultado["confianca"] == "ALTA"
    assert resultado["fonte_evidencia"] == "NOME+CONTEUDO"


def test_analisar_assunto_conflito():
    arquivo = Path("lista_alunos_turma_a.pdf")
    conteudo = "Ofício da SEC referente ao calendário anual."
    resultado = analisar_assunto(arquivo, conteudo, "LIDO")
    assert resultado["assunto"] == "CONFLITO_DE_EVIDENCIAS"
    assert resultado["confianca"] == "BAIXA"
    assert resultado["fonte_evidencia"] == "NOME<>CONTEUDO"


def test_gerar_descricao_arquivo_vazio(tmp_path):
    arquivo_vazio = tmp_path / "vazio.txt"
    arquivo_vazio.write_text("", encoding="utf-8")
    desc = gerar_descricao(
        arquivo_vazio,
        {"tipo_documental": "NAO_IDENTIFICADO"},
        {"assunto": "NAO_IDENTIFICADO"},
        "",
        "LIDO_SEM_TEXTO_UTIL"
    )
    assert "vazio" in desc.lower()
