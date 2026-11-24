"""Controle de acesso local a documentos autorizados pelo painel."""
from hashlib import sha256
from pathlib import Path
from threading import Lock


_DOCUMENTOS_AUTORIZADOS: dict[str, Path] = {}
_LOCK = Lock()


def autorizar_documento(arquivo: Path) -> str:
    arquivo_real = arquivo.resolve(strict=False)
    identificador = sha256(str(arquivo_real).encode("utf-8")).hexdigest()
    with _LOCK:
        _DOCUMENTOS_AUTORIZADOS[identificador] = arquivo_real
    return identificador


def limpar_documentos_autorizados() -> None:
    with _LOCK:
        _DOCUMENTOS_AUTORIZADOS.clear()


def obter_documento_autorizado(identificador: str) -> Path | None:
    if not isinstance(identificador, str) or not identificador:
        return None
    with _LOCK:
        arquivo = _DOCUMENTOS_AUTORIZADOS.get(identificador)
    return arquivo
