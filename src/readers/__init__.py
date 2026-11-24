"""Módulo de leitores textuais com despachante central."""
from pathlib import Path
from src.readers.text_reader import ler_txt
from src.readers.docx_reader import ler_docx
from src.readers.pdf_reader import ler_pdf
from src.readers.sheet_reader import ler_xlsx, ler_xls
from src.readers.ppt_reader import ler_pptx
from src.readers.preview_reader import preparar_preview

LEITORES = {
    ".txt": ler_txt,
    ".docx": ler_docx,
    ".pdf": ler_pdf,
    ".xls": ler_xls,
    ".xlsx": ler_xlsx,
    ".pptx": ler_pptx,
}


def ler_conteudo_textual(arquivo: Path) -> tuple[str, str]:
    leitor = LEITORES.get(arquivo.suffix.lower())
    if leitor is None:
        return ("", "NAO_SUPORTADO_NESTA_VERSAO")

    try:
        conteudo = leitor(arquivo)
        if not conteudo.strip():
            return ("", "LIDO_SEM_TEXTO_UTIL")
        return (conteudo, "LIDO")
    except Exception as erro:
        return ("", f"ERRO_LEITURA: {type(erro).__name__}: {erro}")


__all__ = [
    "ler_txt",
    "ler_docx",
    "ler_pdf",
    "ler_xlsx",
    "ler_xls",
    "ler_pptx",
    "ler_conteudo_textual",
    "preparar_preview",
]
