"""Módulo de normalização e manipulação de textos."""
import re
import unicodedata


def normalizar(texto: str) -> str:
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )
    for caractere in [
        "_", "-", ".", ",", ";", ":",
        "/", "\\", "\n", "\r", "\t",
        "(", ")", "[", "]", "{", "}",
        "!", "?", "\"", "'", "`",
    ]:
        texto = texto.replace(caractere, " ")
    return " ".join(texto.split())


def limpar_texto(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()


def limitar_texto(texto: str, limite: int) -> str:
    texto = limpar_texto(texto)
    if len(texto) <= limite:
        return texto

    corte = texto[:limite]
    ultima_quebra = max(
        corte.rfind(". "),
        corte.rfind("; "),
        corte.rfind(", "),
        corte.rfind(" ")
    )
    if ultima_quebra > limite * 0.65:
        corte = corte[:ultima_quebra]

    return corte.rstrip() + "..."
