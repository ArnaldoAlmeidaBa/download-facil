"""Extrator para arquivos de texto puro (.txt)."""
from pathlib import Path
from src.config import MAX_TEXTO


def ler_txt(arquivo: Path, limite: int = MAX_TEXTO) -> str:
    return arquivo.read_text(
        encoding="utf-8",
        errors="replace",
    )[:limite]
