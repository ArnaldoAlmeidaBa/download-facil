"""Extrator para arquivos PDF (.pdf)."""
from pathlib import Path
from pypdf import PdfReader
from src.config import MAX_TEXTO


def ler_pdf(arquivo: Path, limite: int = MAX_TEXTO) -> str:
    leitor = PdfReader(str(arquivo))
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
