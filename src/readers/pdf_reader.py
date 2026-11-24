"""Extrator para arquivos PDF (.pdf)."""
from pathlib import Path
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from src.config import MAX_TEXTO


def ler_pdf(arquivo: Path, limite: int = MAX_TEXTO) -> str:
    try:
        leitor = PdfReader(str(arquivo))
    except (PdfReadError, OSError, ValueError) as erro:
        raise PdfReadError(f"PDF invalido ou inacessivel: {type(erro).__name__}") from erro

    if getattr(leitor, "is_encrypted", False):
        raise PdfReadError("PDF protegido por senha.")

    partes = []
    tamanho_atual = 0

    for pagina in leitor.pages:
        texto = (pagina.extract_text() or "").strip()
        if texto:
            partes.append(texto)
            tamanho_atual += len(texto)

        if tamanho_atual >= limite:
            break

    return "\n".join(partes)[:limite]
