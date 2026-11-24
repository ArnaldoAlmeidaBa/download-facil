"""Testes unitários para o gerador de dashboard HTML."""
from src.dashboard.generator import classe_confianca, contar_tipo, gerar_painel_html


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
