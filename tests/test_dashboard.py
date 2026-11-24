"""Testes unitários para o gerador de dashboard HTML."""
from src.dashboard.generator import (
    classe_confianca,
    contar_estado,
    contar_inconsistencias,
    contar_movimentados,
    contar_tipo,
    gerar_painel_html,
)


def test_classe_confianca():
    assert classe_confianca("ALTA") == "alta"
    assert classe_confianca("MEDIA") == "media"
    assert classe_confianca("BAIXA") == "baixa"
    assert classe_confianca("OUTRA") == "neutra"


def test_contar_tipo():
    registros = [
        {"tipo_tecnico": "DOCUMENTO", "estado_ficha": "AGUARDANDO"},
        {"tipo_tecnico": "DOCUMENTO", "estado_ficha": "AGUARDANDO"},
        {"tipo_tecnico": "DOCUMENTO", "estado_ficha": "IGNORADO"},
        {"tipo_tecnico": "IMAGEM", "estado_ficha": "AGUARDANDO"},
    ]
    assert contar_tipo(registros, "DOCUMENTO") == 2
    assert contar_tipo(registros, "IMAGEM") == 1


def test_gerar_painel_html_integracao(tmp_path):
    saida = tmp_path / "painel_teste.html"
    registros = [
        {
            "arquivo": "tcc.pdf",
            "caminho": "C:\\Downloads\\tcc.pdf",
            "extensao": ".pdf",
            "tipo_tecnico": "DOCUMENTO",
            "tipo_arquivo": "PDF",
            "tamanho": "1.2 MB",
            "tamanho_bytes": 1200000,
            "data_modificacao": "23/11/2026 15:00",
            "tipo_documental": "TCC",
            "confianca_tipo_documental": "ALTA",
            "evidencias_tipo_documental": "tcc, metodologia",
            "assunto": "TCC",
            "confianca_assunto": "ALTA",
            "fonte_evidencia": "CONTEUDO",
            "estado_leitura": "LIDO",
            "destino_sugerido": "Revisar",
            "destino_caminho": "C:\\Revisar",
            "estado_destino": "DESTINO_EXISTENTE_SUGERIDO",
            "evidencias_destino": "Evidencias",
            "motivo_destino": "Motivo",
            "destino_legado": "",
            "motivo": "Motivo",
            "descricao": "TCC sobre educacao",
            "estado_ficha": "AGUARDANDO_DECISAO_HUMANA",
            "acao_fisica": "NENHUMA — DRY-RUN",
            "preview": {"tipo": "texto", "url": "", "conteudo": "Texto preview"},
        }
    ]
    painel = gerar_painel_html(registros, caminho_saida=saida)
    assert painel.exists()
    conteudo = painel.read_text(encoding="utf-8")
    assert "tcc.pdf" in conteudo
    assert "btn-acao-mover" in conteudo
    assert "desfazerAcao" in conteudo


def test_painel_exibe_estados_operacionais_e_contagens(tmp_path):
    base = {
        "arquivo": "fixture.txt",
        "caminho": "C:\\Downloads\\fixture.txt",
        "extensao": ".txt",
        "tipo_tecnico": "DOCUMENTO",
        "tipo_arquivo": "Texto",
        "tamanho": "1 KB",
        "tamanho_bytes": 1000,
        "data_modificacao": "23/11/2026 15:00",
        "tipo_documental": "NAO_IDENTIFICADO",
        "confianca_tipo_documental": "BAIXA",
        "evidencias_tipo_documental": "",
        "assunto": "NAO_IDENTIFICADO",
        "confianca_assunto": "BAIXA",
        "fonte_evidencia": "NOME_ARQUIVO",
        "estado_leitura": "LIDO",
        "destino_sugerido": "Revisar",
        "destino_caminho": "",
        "estado_destino": "SEM_DESTINO_SUFICIENTEMENTE_SEGURO",
        "evidencias_destino": "",
        "motivo_destino": "",
        "destino_legado": "",
        "motivo": "",
        "descricao": "Documento fictício.",
        "estado_ficha": "AGUARDANDO_DECISAO_HUMANA",
        "estado_operacional": "AGUARDANDO_DECISAO_HUMANA",
        "acao_fisica": "NENHUMA",
        "preview": {"tipo": "texto", "url": "", "conteudo": ""},
    }
    registros = [
        dict(base),
        dict(base, estado_operacional="MOVIDO"),
        dict(base, estado_operacional="ALTERADO_EXTERNAMENTE"),
    ]
    assert contar_estado(registros, "AGUARDANDO_DECISAO_HUMANA") == 1
    assert contar_movimentados(registros) == 1
    assert contar_inconsistencias(registros) == 1

    saida = tmp_path / "estados.html"
    gerar_painel_html(registros, caminho_saida=saida)
    conteudo = saida.read_text(encoding="utf-8")
    assert "Aguardando decisão" in conteudo
    assert "Movimentado" in conteudo
    assert "Alterado externamente" in conteudo
    assert 'data-contagem-estado="AGUARDANDO_DECISAO_HUMANA">1' in conteudo
    assert 'data-contagem-estado="MOVIDO">1' in conteudo
    assert 'data-contagem-estado="INCONSISTENCIAS">1' in conteudo
    assert "sessionStorage" in conteudo
