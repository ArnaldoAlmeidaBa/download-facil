"""Extrator para apresentações PowerPoint (.pptx)."""
from pathlib import Path
from pptx import Presentation
from src.config import MAX_TEXTO


def ler_pptx(arquivo: Path, limite: int = MAX_TEXTO) -> str:
    apresentacao = Presentation(str(arquivo))
    partes = []
    tamanho_atual = 0

    for numero, slide in enumerate(apresentacao.slides, start=1):
        textos_slide = []
        for shape in slide.shapes:
            if not hasattr(shape, "text"):
                continue
            texto_shape = (shape.text or "").strip()
            if texto_shape:
                textos_slide.append(texto_shape)

        if textos_slide:
            cabecalho = f"SLIDE {numero}"
            partes.append(cabecalho)
            tamanho_atual += len(cabecalho)

            for trecho in textos_slide:
                partes.append(trecho)
                tamanho_atual += len(trecho)

                if tamanho_atual >= limite:
                    return "\n".join(partes)[:limite]

    return "\n".join(partes)[:limite]
