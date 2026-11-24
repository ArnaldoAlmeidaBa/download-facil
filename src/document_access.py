"""In-memory authorization for files and destinations exposed by the local UI."""
from dataclasses import dataclass
from pathlib import Path
import os
import secrets
from threading import Lock


@dataclass(frozen=True)
class FileSnapshot:
    path: Path
    resolved_path: Path
    size: int
    modified_ns: int
    device: int
    file_id: int


@dataclass(frozen=True)
class DestinationSnapshot:
    path: Path
    device: int
    file_id: int


_LOCK = Lock()
_CONTEXT_CONFIGURED = False
_SOURCE_ROOTS: tuple[Path, ...] = ()
_FILES: dict[str, FileSnapshot] = {}
_FILE_IDS_BY_PATH: dict[str, str] = {}
_DOCUMENT_IDS: set[str] = set()
_MOVED_DESTINATIONS: dict[str, str] = {}
_DESTINATIONS: dict[str, DestinationSnapshot] = {}
_DESTINATION_IDS_BY_PATH: dict[str, str] = {}

SNAPSHOT_VALID = "VALIDO"
SNAPSHOT_MISSING = "AUSENTE_OU_RENOMEADO"
SNAPSHOT_REPLACED = "SUBSTITUIDO"
SNAPSHOT_CHANGED = "ALTERADO"


def _key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def _resolve_existing(path: Path) -> Path | None:
    try:
        return path.resolve(strict=True)
    except (OSError, RuntimeError):
        return None


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(str(path)))


def _is_within(path: Path, roots: tuple[Path, ...]) -> bool:
    for root in roots:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _snapshot(path: Path) -> FileSnapshot | None:
    lexical = _absolute(path)
    resolved = _resolve_existing(lexical)
    if resolved is None:
        return None
    try:
        if not resolved.is_file():
            return None
        stats = resolved.stat()
    except OSError:
        return None
    return FileSnapshot(
        path=lexical,
        resolved_path=resolved,
        size=stats.st_size,
        modified_ns=stats.st_mtime_ns,
        device=stats.st_dev,
        file_id=stats.st_ino,
    )


def classificar_snapshot(autorizado: FileSnapshot) -> str:
    atual = _snapshot(autorizado.path)
    if atual is None:
        return SNAPSHOT_MISSING
    if (
        atual.resolved_path != autorizado.resolved_path
        or atual.device != autorizado.device
        or (
            autorizado.file_id
            and atual.file_id != autorizado.file_id
        )
    ):
        return SNAPSHOT_REPLACED
    if atual.size != autorizado.size or atual.modified_ns != autorizado.modified_ns:
        return SNAPSHOT_CHANGED
    return SNAPSHOT_VALID


def validar_snapshot(autorizado: FileSnapshot) -> bool:
    return classificar_snapshot(autorizado) == SNAPSHOT_VALID


def inicializar_autorizacoes(perfil: dict) -> None:
    global _CONTEXT_CONFIGURED, _SOURCE_ROOTS
    raizes = []
    with _LOCK:
        _FILES.clear()
        _FILE_IDS_BY_PATH.clear()
        _DOCUMENT_IDS.clear()
        _MOVED_DESTINATIONS.clear()
        _DESTINATIONS.clear()
        _DESTINATION_IDS_BY_PATH.clear()

        for pasta in perfil.get("pastas_entrada", []):
            if not pasta.get("monitorar", True) or not pasta.get("caminho"):
                continue
            raiz = _resolve_existing(Path(pasta["caminho"]))
            if raiz is not None and raiz.is_dir():
                raizes.append(raiz)
        _SOURCE_ROOTS = tuple(raizes)
        _CONTEXT_CONFIGURED = True

        for destino in perfil.get("territorio_documental", []):
            if (
                destino.get("papel") != "DESTINO"
                or not destino.get("pode_receber_arquivos", False)
                or not destino.get("caminho")
            ):
                continue
            caminho = _resolve_existing(Path(destino["caminho"]))
            if caminho is None or not caminho.is_dir():
                continue
            try:
                estatisticas = caminho.stat()
            except OSError:
                continue
            identificador = secrets.token_urlsafe(32)
            _DESTINATIONS[identificador] = DestinationSnapshot(
                caminho,
                estatisticas.st_dev,
                estatisticas.st_ino,
            )
            _DESTINATION_IDS_BY_PATH[_key(caminho)] = identificador


def limpar_documentos_autorizados() -> None:
    global _CONTEXT_CONFIGURED, _SOURCE_ROOTS
    with _LOCK:
        _CONTEXT_CONFIGURED = False
        _SOURCE_ROOTS = ()
        _FILES.clear()
        _FILE_IDS_BY_PATH.clear()
        _DOCUMENT_IDS.clear()
        _MOVED_DESTINATIONS.clear()
        _DESTINATIONS.clear()
        _DESTINATION_IDS_BY_PATH.clear()


def autorizar_arquivo(arquivo: Path) -> str | None:
    snapshot = _snapshot(arquivo)
    if snapshot is None:
        return None

    with _LOCK:
        if _CONTEXT_CONFIGURED and not _is_within(snapshot.resolved_path, _SOURCE_ROOTS):
            return None

        chave = _key(snapshot.path)
        existente = _FILE_IDS_BY_PATH.get(chave)
        if existente:
            anterior = _FILES.get(existente)
            if anterior == snapshot:
                return existente
            _FILES.pop(existente, None)
            _DOCUMENT_IDS.discard(existente)
            _MOVED_DESTINATIONS.pop(existente, None)

        identificador = secrets.token_urlsafe(32)
        _FILES[identificador] = snapshot
        _FILE_IDS_BY_PATH[chave] = identificador
        return identificador


def autorizar_documento(arquivo: Path) -> str | None:
    if arquivo.suffix.lower() != ".pdf":
        return None
    identificador = autorizar_arquivo(arquivo)
    if identificador is None:
        return None
    with _LOCK:
        _DOCUMENT_IDS.add(identificador)
    return identificador


def obter_arquivo_registrado(identificador: str) -> FileSnapshot | None:
    if not isinstance(identificador, str) or not identificador:
        return None
    with _LOCK:
        return _FILES.get(identificador)


def obter_arquivo_autorizado(identificador: str) -> FileSnapshot | None:
    autorizado = obter_arquivo_registrado(identificador)
    if autorizado is None or not validar_snapshot(autorizado):
        return None
    with _LOCK:
        if _CONTEXT_CONFIGURED and not _is_within(autorizado.resolved_path, _SOURCE_ROOTS):
            return None
    return autorizado


def obter_documento_autorizado(identificador: str) -> Path | None:
    if not isinstance(identificador, str) or not identificador:
        return None
    with _LOCK:
        autorizado = _FILES.get(identificador) if identificador in _DOCUMENT_IDS else None
    if autorizado is None or not validar_snapshot(autorizado):
        return None
    with _LOCK:
        destino_id = _MOVED_DESTINATIONS.get(identificador)
        if destino_id:
            destino = _DESTINATIONS.get(destino_id)
            if (
                destino is None
                or not validar_destino(destino)
                or not _is_within(autorizado.resolved_path, (destino.path,))
            ):
                return None
        elif _CONTEXT_CONFIGURED and not _is_within(autorizado.resolved_path, _SOURCE_ROOTS):
            return None
    return autorizado.path


def classificar_arquivo_autorizado(identificador: str) -> str | None:
    autorizado = obter_arquivo_registrado(identificador)
    if autorizado is None:
        return None
    return classificar_snapshot(autorizado)


def transferir_autorizacao_para_destino(
    identificador: str,
    destino_id: str,
    caminho_final: Path,
) -> bool:
    autorizado = obter_arquivo_registrado(identificador)
    destino = autorizar_destino(destino_id)
    if autorizado is None or destino is None:
        return False

    snapshot = _snapshot(caminho_final)
    if (
        snapshot is None
        or not _is_within(snapshot.resolved_path, (destino.path,))
        or snapshot.size != autorizado.size
        or snapshot.modified_ns != autorizado.modified_ns
    ):
        return False

    with _LOCK:
        anterior = _FILES.get(identificador)
        if anterior is None:
            return False
        chave_anterior = _key(anterior.path)
        if _FILE_IDS_BY_PATH.get(chave_anterior) == identificador:
            _FILE_IDS_BY_PATH.pop(chave_anterior, None)
        _FILES[identificador] = snapshot
        _FILE_IDS_BY_PATH[_key(snapshot.path)] = identificador
        _MOVED_DESTINATIONS[identificador] = destino_id
    return True


def restaurar_autorizacao_na_origem(
    identificador: str,
    caminho_restaurado: Path,
) -> bool:
    snapshot = _snapshot(caminho_restaurado)
    if snapshot is None:
        return False

    with _LOCK:
        if _CONTEXT_CONFIGURED and not _is_within(snapshot.resolved_path, _SOURCE_ROOTS):
            return False
        anterior = _FILES.get(identificador)
        if anterior is None:
            return False
        chave_anterior = _key(anterior.path)
        if _FILE_IDS_BY_PATH.get(chave_anterior) == identificador:
            _FILE_IDS_BY_PATH.pop(chave_anterior, None)
        _FILES[identificador] = snapshot
        _FILE_IDS_BY_PATH[_key(snapshot.path)] = identificador
        _MOVED_DESTINATIONS.pop(identificador, None)
    return True


def obter_destino_registrado(identificador: str) -> DestinationSnapshot | None:
    if not isinstance(identificador, str) or not identificador:
        return None
    with _LOCK:
        return _DESTINATIONS.get(identificador)


def validar_destino(autorizado: DestinationSnapshot) -> bool:
    atual = _resolve_existing(autorizado.path)
    if atual != autorizado.path or atual is None or not atual.is_dir():
        return False
    try:
        estatisticas = atual.stat()
    except OSError:
        return False
    return (
        estatisticas.st_dev == autorizado.device
        and (not autorizado.file_id or estatisticas.st_ino == autorizado.file_id)
    )


def autorizar_destino(identificador: str) -> DestinationSnapshot | None:
    autorizado = obter_destino_registrado(identificador)
    if autorizado is None or not validar_destino(autorizado):
        return None
    return autorizado


def identificador_destino(caminho: str | Path) -> str | None:
    resolvido = _resolve_existing(Path(caminho))
    if resolvido is None:
        return None
    with _LOCK:
        identificador = _DESTINATION_IDS_BY_PATH.get(_key(resolvido))
    if identificador is None or autorizar_destino(identificador) is None:
        return None
    return identificador


def caminho_fonte_autorizado(caminho: str | Path) -> bool:
    resolvido = Path(caminho).resolve(strict=False)
    with _LOCK:
        return not _CONTEXT_CONFIGURED or _is_within(resolvido, _SOURCE_ROOTS)


def caminho_destino_autorizado(caminho: str | Path) -> bool:
    pasta = Path(caminho).parent
    resolvido = _resolve_existing(pasta)
    if resolvido is None:
        return False
    with _LOCK:
        identificador = _DESTINATION_IDS_BY_PATH.get(_key(resolvido))
    return identificador is not None and autorizar_destino(identificador) is not None
