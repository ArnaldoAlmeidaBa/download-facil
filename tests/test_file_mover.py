"""Testes unitários para movimentação segura de arquivos e função desfazer."""
from src.actions.file_mover import (
    mover_arquivo_seguro,
    desfazer_ultima_movimentacao,
    gerar_caminho_sem_colisao,
    limpar_historico,
    obter_historico_movimentacoes,
)


def test_gerar_caminho_sem_colisao(tmp_path):
    pasta = tmp_path / "destino"
    pasta.mkdir()

    # Caso 1: arquivo não existe
    caminho1 = gerar_caminho_sem_colisao(pasta, "doc.pdf")
    assert caminho1.name == "doc.pdf"

    # Caso 2: arquivo já existe
    (pasta / "doc.pdf").write_text("conteudo original", encoding="utf-8")
    caminho2 = gerar_caminho_sem_colisao(pasta, "doc.pdf")
    assert caminho2.name == "doc_1.pdf"

    # Caso 3: doc.pdf e doc_1.pdf já existem
    (pasta / "doc_1.pdf").write_text("conteudo 2", encoding="utf-8")
    caminho3 = gerar_caminho_sem_colisao(pasta, "doc.pdf")
    assert caminho3.name == "doc_2.pdf"


def test_mover_arquivo_com_sucesso_e_desfazer(tmp_path):
    limpar_historico()

    origem_dir = tmp_path / "downloads"
    origem_dir.mkdir()
    arquivo_origem = origem_dir / "tcc_final.pdf"
    arquivo_origem.write_text("trabalho academico", encoding="utf-8")

    destino_dir = tmp_path / "revisar"

    # 1. Executa movimentação segura
    res = mover_arquivo_seguro(arquivo_origem, destino_dir, log_dir=tmp_path / "logs")
    assert res["sucesso"] is True
    assert not arquivo_origem.exists()

    arquivo_movido = destino_dir / "tcc_final.pdf"
    assert arquivo_movido.exists()
    assert arquivo_movido.read_text(encoding="utf-8") == "trabalho academico"

    # 2. Reverte movimentação via Desfazer
    res_undo = desfazer_ultima_movimentacao(log_dir=tmp_path / "logs")
    assert res_undo["sucesso"] is True
    assert not arquivo_movido.exists()
    assert arquivo_origem.exists()
    assert arquivo_origem.read_text(encoding="utf-8") == "trabalho academico"


def test_mover_arquivo_inexistente(tmp_path):
    limpar_historico()
    arquivo_fantasma = tmp_path / "inexistente.pdf"
    destino_dir = tmp_path / "destino"

    res = mover_arquivo_seguro(arquivo_fantasma, destino_dir, log_dir=tmp_path / "logs")
    assert res["sucesso"] is False
    assert "não encontrado" in res["erro"]


def test_desfazer_preserva_historico_quando_arquivo_movido_foi_alterado(tmp_path):
    limpar_historico()
    origem = tmp_path / "downloads"
    destino = tmp_path / "revisar"
    origem.mkdir()
    arquivo = origem / "documento.txt"
    arquivo.write_text("original", encoding="utf-8")

    resultado = mover_arquivo_seguro(arquivo, destino, log_dir=tmp_path / "logs")
    assert resultado["sucesso"] is True
    (destino / "documento.txt").write_text("substituido", encoding="utf-8")

    reversao = desfazer_ultima_movimentacao(log_dir=tmp_path / "logs")
    assert reversao["sucesso"] is False
    assert len(obter_historico_movimentacoes()) == 1
    assert not arquivo.exists()


def test_desfazer_falha_transitoria_preserva_historico_para_nova_tentativa(
    tmp_path, monkeypatch
):
    import src.actions.file_mover as file_mover

    limpar_historico()
    origem = tmp_path / "downloads" / "documento.txt"
    origem.parent.mkdir()
    origem.write_text("conteudo", encoding="utf-8")
    destino = tmp_path / "revisar"
    resultado = mover_arquivo_seguro(
        origem,
        destino,
        log_dir=tmp_path / "logs",
    )
    assert resultado["sucesso"] is True

    mover_original = file_mover.shutil.move
    falhar_uma_vez = True

    def mover_com_falha_transitoria(*args, **kwargs):
        nonlocal falhar_uma_vez
        if falhar_uma_vez:
            falhar_uma_vez = False
            raise PermissionError("bloqueio temporário de fixture")
        return mover_original(*args, **kwargs)

    monkeypatch.setattr(file_mover.shutil, "move", mover_com_falha_transitoria)
    reversao = desfazer_ultima_movimentacao(log_dir=tmp_path / "logs")
    assert reversao["sucesso"] is False
    assert len(obter_historico_movimentacoes()) == 1
    assert (destino / "documento.txt").exists()

    reversao = desfazer_ultima_movimentacao(log_dir=tmp_path / "logs")
    assert reversao["sucesso"] is True
    assert not obter_historico_movimentacoes()
    assert origem.read_text(encoding="utf-8") == "conteudo"


def test_reversao_nao_sobrescreve_arquivo_existente_na_origem(tmp_path):
    limpar_historico()
    origem = tmp_path / "downloads"
    origem.mkdir()
    arquivo = origem / "documento.txt"
    arquivo.write_text("original", encoding="utf-8")
    destino = tmp_path / "revisar"

    resultado = mover_arquivo_seguro(
        arquivo,
        destino,
        log_dir=tmp_path / "logs",
    )
    assert resultado["sucesso"] is True
    arquivo.write_text("outro arquivo criado externamente", encoding="utf-8")

    reversao = desfazer_ultima_movimentacao(log_dir=tmp_path / "logs")
    assert reversao["sucesso"] is True
    assert arquivo.read_text(encoding="utf-8") == "outro arquivo criado externamente"
    assert (origem / "documento_1.txt").read_text(encoding="utf-8") == "original"


def test_falha_de_auditoria_nao_apresenta_movimentacao_fisica_como_falha(
    tmp_path, monkeypatch
):
    import src.actions.file_mover as file_mover

    limpar_historico()
    origem = tmp_path / "downloads" / "documento.txt"
    origem.parent.mkdir()
    origem.write_text("conteudo", encoding="utf-8")

    def falhar_auditoria(*args, **kwargs):
        raise OSError("fixture")

    monkeypatch.setattr(
        file_mover,
        "registrar_movimentacao_log",
        falhar_auditoria,
    )

    resultado = mover_arquivo_seguro(
        origem,
        tmp_path / "revisar",
        log_dir=tmp_path / "logs",
    )
    assert resultado["sucesso"] is True
    assert "auditoria" in resultado["aviso"].lower()
    assert not origem.exists()
    assert len(obter_historico_movimentacoes()) == 1
