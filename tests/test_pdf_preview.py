from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import urllib.error
import urllib.request

from pypdf import PdfWriter

from src.document_access import (
    autorizar_documento,
    limpar_documentos_autorizados,
)
from src.readers import ler_conteudo_textual
from src.readers.preview_reader import preparar_preview
from src.server import OrquestradorRequestHandler


def criar_pdf(caminho: Path, paginas: int = 1, protegido: bool = False) -> None:
    escritor = PdfWriter()
    for _ in range(paginas):
        escritor.add_blank_page(width=300, height=300)
    if protegido:
        escritor.encrypt("senha-teste")
    with caminho.open("wb") as arquivo:
        escritor.write(arquivo)


def iniciar_servidor():
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), OrquestradorRequestHandler)
    thread = Thread(
        target=lambda: servidor.serve_forever(poll_interval=0.01),
        daemon=True,
    )
    thread.start()
    return servidor, thread


def requisitar(url: str, headers: dict = None):
    requisicao = urllib.request.Request(url, headers=headers or {})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(requisicao, timeout=5) as resposta:
            return resposta.status, dict(resposta.headers), resposta.read()
    except urllib.error.HTTPError as erro:
        return erro.code, dict(erro.headers), erro.read()


def test_preview_pdf_simples_e_multipaginas_com_nome_acentuado(tmp_path):
    simples = tmp_path / "documento.pdf"
    criar_pdf(simples)
    conteudo, estado = ler_conteudo_textual(simples)
    preview = preparar_preview(simples, conteudo, estado)
    assert preview["tipo"] == "pdf"
    assert preview["url"].startswith("/api/documento/")

    varias_paginas = tmp_path / "Relatório Técnico de revisão.pdf"
    criar_pdf(varias_paginas, paginas=3)
    _, estado = ler_conteudo_textual(varias_paginas)
    preview = preparar_preview(varias_paginas, "", estado)
    assert preview["tipo"] == "pdf"
    assert preview["url"].startswith("/api/documento/")


def test_pdf_inexistente_invalido_e_protegido(tmp_path):
    inexistente = tmp_path / "inexistente.pdf"
    _, estado = ler_conteudo_textual(inexistente)
    assert estado.startswith("ERRO_LEITURA")

    invalido = tmp_path / "invalido.pdf"
    invalido.write_text("isso nao e um PDF", encoding="utf-8")
    _, estado = ler_conteudo_textual(invalido)
    preview = preparar_preview(invalido, "", estado)
    assert preview["tipo"] == "mensagem"
    assert "inválido" in preview["conteudo"].lower()

    protegido = tmp_path / "protegido.pdf"
    criar_pdf(protegido, protegido=True)
    _, estado = ler_conteudo_textual(protegido)
    preview = preparar_preview(protegido, "", estado)
    assert preview["tipo"] == "mensagem"
    assert "protegido" in preview["conteudo"].lower()


def test_servidor_entrega_somente_pdf_autorizado_com_range(tmp_path):
    limpar_documentos_autorizados()
    pdf = tmp_path / "Documento protegido por espaço.pdf"
    criar_pdf(pdf, paginas=2)
    identificador = autorizar_documento(pdf)
    servidor, thread = iniciar_servidor()

    try:
        base = f"http://127.0.0.1:{servidor.server_port}"
        status, cabecalhos, corpo = requisitar(f"{base}/api/documento/{identificador}")
        assert status == 200
        assert cabecalhos["Content-Type"] == "application/pdf"
        assert cabecalhos["X-Content-Type-Options"] == "nosniff"
        assert corpo.startswith(b"%PDF")

        status, cabecalhos, corpo = requisitar(
            f"{base}/api/documento/{identificador}",
            {"Range": "bytes=0-15"},
        )
        assert status == 206
        assert len(corpo) == 16
        assert cabecalhos["Accept-Ranges"] == "bytes"

        status, _, _ = requisitar(f"{base}/api/documento/{'0' * 64}")
        assert status == 404

        identificador_traversal = "../" + identificador
        status, _, _ = requisitar(f"{base}/api/documento/{identificador_traversal}")
        assert status == 404
    finally:
        servidor.shutdown()
        servidor.server_close()
        thread.join(timeout=5)
        limpar_documentos_autorizados()


def test_servidor_rejeita_pdf_invalido_protegido_e_inexistente(tmp_path):
    limpar_documentos_autorizados()
    invalido = tmp_path / "invalid.pdf"
    invalido.write_text("texto", encoding="utf-8")
    protegido = tmp_path / "protected.pdf"
    criar_pdf(protegido, protegido=True)
    servidor, thread = iniciar_servidor()

    try:
        base = f"http://127.0.0.1:{servidor.server_port}"

        invalido_id = autorizar_documento(invalido)
        status, _, _ = requisitar(f"{base}/api/documento/{invalido_id}")
        assert status == 422

        protegido_id = autorizar_documento(protegido)
        status, _, _ = requisitar(f"{base}/api/documento/{protegido_id}")
        assert status == 423

        inexistente = tmp_path / "missing.pdf"
        inexistente_id = autorizar_documento(inexistente)
        status, _, _ = requisitar(f"{base}/api/documento/{inexistente_id}")
        assert status == 404
    finally:
        servidor.shutdown()
        servidor.server_close()
        thread.join(timeout=5)
        limpar_documentos_autorizados()


def test_previews_imagem_audio_e_video_continuam_funcionando(tmp_path):
    imagem = tmp_path / "imagem.png"
    imagem.write_bytes(b"\x89PNG\r\n\x1a\n" + b"dados-ficticios")
    preview = preparar_preview(imagem, "", "LIDO")
    assert preview["tipo"] == "imagem"
    assert preview["url"].startswith("data:image/png;base64,")

    audio = tmp_path / "som.mp3"
    audio.write_bytes(b"dados-de-audio")
    preview = preparar_preview(audio, "", "LIDO")
    assert preview["tipo"] == "audio"
    assert preview["url"].startswith("data:audio/")

    video = tmp_path / "video.mp4"
    video.write_bytes(b"dados-de-video")
    preview = preparar_preview(video, "", "LIDO")
    assert preview["tipo"] == "video"
    assert preview["url"].startswith("data:video/")
