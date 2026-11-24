"""Módulo para geração de pré-visualização de arquivos e mídias."""
from pathlib import Path
import base64
import mimetypes
from src.document_access import autorizar_documento
from src.config import (
    MAX_PREVIEW_TEXTO,
    MAX_PREVIEW_IMAGEM_BYTES,
    MAX_PREVIEW_MIDIA_BYTES,
)


def imagem_para_data_uri(arquivo: Path) -> tuple[str, str]:
    tamanho = arquivo.stat().st_size
    if tamanho == 0:
        return ("", "A imagem está vazia.")
    if tamanho > MAX_PREVIEW_IMAGEM_BYTES:
        return ("", "A imagem é muito grande para ser incorporada à pré-visualização deste painel.")

    try:
        mime_type, _ = mimetypes.guess_type(arquivo.name)
        if not mime_type:
            mapa_mime = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp",
                ".bmp": "image/bmp",
                ".svg": "image/svg+xml",
            }
            mime_type = mapa_mime.get(arquivo.suffix.lower(), "application/octet-stream")

        dados = arquivo.read_bytes()
        codificado = base64.b64encode(dados).decode("ascii")
        return (f"data:{mime_type};base64,{codificado}", "")
    except Exception as erro:
        return ("", f"Não foi possível preparar a imagem para visualização. Detalhe técnico: {type(erro).__name__}.")


def midia_para_data_uri(arquivo: Path) -> tuple[str, str]:
    try:
        tamanho = arquivo.stat().st_size
        if tamanho == 0:
            return ("", "Este arquivo está vazio.")
        if tamanho > MAX_PREVIEW_MIDIA_BYTES:
            return ("", "Este arquivo de mídia é grande demais para ser incorporado nesta pré-visualização.")

        mime_type, _ = mimetypes.guess_type(arquivo.name)
        if not mime_type:
            mime_type = "application/octet-stream"

        dados = arquivo.read_bytes()
        codificado = base64.b64encode(dados).decode("ascii")
        return (f"data:{mime_type};base64,{codificado}", "")
    except Exception as erro:
        return ("", f"Não foi possível preparar esta mídia para visualização. Detalhe técnico: {type(erro).__name__}.")


def preparar_preview(arquivo: Path, conteudo: str, estado_leitura: str) -> dict:
    extensao = arquivo.suffix.lower()

    if extensao == ".pdf":
        if estado_leitura.startswith("ERRO_LEITURA"):
            if "protegido" in estado_leitura.lower():
                mensagem = "Este PDF está protegido por senha e não pode ser pré-visualizado."
            else:
                mensagem = "Este PDF está inválido, inacessível ou não pôde ser lido."
            return {"tipo": "mensagem", "url": "", "conteudo": mensagem}

        identificador = autorizar_documento(arquivo)
        return {
            "tipo": "pdf",
            "url": f"/api/documento/{identificador}",
            "conteudo": "",
        }

    if extensao in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}:
        data_uri, erro = imagem_para_data_uri(arquivo)
        if data_uri:
            return {"tipo": "imagem", "url": data_uri, "conteudo": ""}
        return {"tipo": "mensagem", "url": "", "conteudo": erro}

    if extensao in {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}:
        data_uri, erro = midia_para_data_uri(arquivo)
        if data_uri:
            return {"tipo": "audio", "url": data_uri, "conteudo": ""}
        return {"tipo": "mensagem", "url": "", "conteudo": erro}

    if extensao in {".mp4", ".m4v", ".webm", ".mov"}:
        data_uri, erro = midia_para_data_uri(arquivo)
        if data_uri:
            return {"tipo": "video", "url": data_uri, "conteudo": ""}
        return {"tipo": "mensagem", "url": "", "conteudo": erro}

    if extensao in {".txt", ".docx", ".xls", ".xlsx", ".pptx"} and conteudo:
        return {
            "tipo": "texto",
            "url": "",
            "conteudo": conteudo[:MAX_PREVIEW_TEXTO],
        }

    if estado_leitura.startswith("ERRO_LEITURA"):
        return {
            "tipo": "mensagem",
            "url": "",
            "conteudo": (
                "Não foi possível preparar uma visualização deste arquivo. "
                "Ele pode estar vazio, incompleto ou corrompido."
            ),
        }

    return {
        "tipo": "mensagem",
        "url": "",
        "conteudo": "Este tipo de arquivo não será aberto dentro do painel.",
    }
