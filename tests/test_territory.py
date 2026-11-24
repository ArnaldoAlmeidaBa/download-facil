"""Testes unitários para o módulo de território documental."""
from pathlib import Path
from src.rules.territory import avaliar_destino_territorio


def test_territorio_sem_destinos_autorizados():
    arquivo = Path("documento.pdf")
    resultado = avaliar_destino_territorio(
        arquivo=arquivo,
        conteudo="Texto qualquer",
        tipo_documental={"tipo_documental": "NAO_IDENTIFICADO"},
        analise={"assunto": "NAO_IDENTIFICADO"},
        territorio_documental=[]
    )
    assert resultado["estado_destino"] == "SEM_DESTINO_SUFICIENTEMENTE_SEGURO"
    assert resultado["destino_sugerido"] == ""


def test_territorio_destino_sugerido_com_sucesso():
    arquivo = Path("Oficio_SEC_01.pdf")
    conteudo = "Encaminha ofício da SEC para conhecimento."
    territorio = [
        {
            "nome": "Oficios",
            "caminho": "C:\\Documentos\\Oficios",
            "papel": "DESTINO",
            "pode_receber_arquivos": True,
            "contextos_associados": ["oficio", "sec"]
        }
    ]
    resultado = avaliar_destino_territorio(
        arquivo=arquivo,
        conteudo=conteudo,
        tipo_documental={"tipo_documental": "OFICIO_SEC"},
        analise={"assunto": "OFICIO_SEC"},
        territorio_documental=territorio
    )
    assert resultado["estado_destino"] == "DESTINO_EXISTENTE_SUGERIDO"
    assert resultado["destino_sugerido"] == "Oficios"
    assert "C:\\Documentos\\Oficios" in resultado["destino_caminho"]


def test_territorio_conflito_multiplos_destinos():
    arquivo = Path("Alunos_Oficios.pdf")
    conteudo = "Lista de alunos e ofício conjunto."
    territorio = [
        {
            "nome": "Oficios",
            "caminho": "C:\\Destino\\Oficios",
            "papel": "DESTINO",
            "pode_receber_arquivos": True,
            "contextos_associados": ["oficio"]
        },
        {
            "nome": "Alunos",
            "caminho": "C:\\Destino\\Alunos",
            "papel": "DESTINO",
            "pode_receber_arquivos": True,
            "contextos_associados": ["alunos"]
        }
    ]
    resultado = avaliar_destino_territorio(
        arquivo=arquivo,
        conteudo=conteudo,
        tipo_documental={"tipo_documental": "NAO_IDENTIFICADO"},
        analise={"assunto": "NAO_IDENTIFICADO"},
        territorio_documental=territorio
    )
    assert resultado["estado_destino"] == "SEM_DESTINO_SUFICIENTEMENTE_SEGURO"
    assert "Mais de um destino" in resultado["evidencias_destino"]
