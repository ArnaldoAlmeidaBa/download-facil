"""Extrator para documentos Microsoft Word (.docx)."""
from pathlib import Path
from docx import Document
from src.config import MAX_TEXTO


def ler_docx(arquivo: Path, limite: int = MAX_TEXTO) -> str:
    documento = Document(arquivo)
    partes = []

    for paragrafo in documento.paragraphs:
        texto = paragrafo.text.strip()
        if texto:
            partes.append(texto)

    for tabela in documento.tables:
        for linha in tabela.rows:
            valores = [
                celula.text.strip()
                for celula in linha.cells
                if celula.text.strip()
            ]
            if valores:
                partes.append(" | ".join(valores))

    return "\n".join(partes)[:limite]
