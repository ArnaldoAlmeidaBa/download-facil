"""Testes unitários para o módulo de auditoria e logs."""
from src.logging.audit_logger import preparar_log, registrar_decisao


def test_preparar_e_registrar_decisao(tmp_path):
    log_file = tmp_path / "logs" / "teste_decisoes.csv"
    preparar_log(log_file.parent, log_file)
    assert log_file.exists()

    registro_amostra = {
        "arquivo": "teste.pdf",
        "caminho": "C:\\Downloads\\teste.pdf",
        "tipo_tecnico": "DOCUMENTO",
        "tipo_arquivo": "PDF",
        "tipo_documental": "OFICIO_SEC",
        "confianca_tipo_documental": "ALTA",
        "evidencias_tipo_documental": "oficio, sec",
        "assunto": "OFICIO_SEC",
        "confianca_assunto": "ALTA",
        "fonte_evidencia": "CONTEUDO",
        "estado_leitura": "LIDO",
        "estado_destino": "DESTINO_EXISTENTE_SUGERIDO",
        "destino_sugerido": "Oficios",
        "destino_caminho": "C:\\Destino\\Oficios",
        "evidencias_destino": "Contexto encontrado",
        "motivo_destino": "Motivo teste",
        "destino_legado": "REVISAR\\Oficios",
        "descricao": "Ofício da SEC recebido",
        "estado_ficha": "AGUARDANDO_DECISAO_HUMANA",
        "acao_fisica": "NENHUMA — DRY-RUN",
    }
    registrar_decisao(log_file, registro_amostra)

    conteudo = log_file.read_text(encoding="utf-8-sig")
    assert "teste.pdf" in conteudo
    assert "OFICIO_SEC" in conteudo
    assert "NENHUMA — DRY-RUN" in conteudo
