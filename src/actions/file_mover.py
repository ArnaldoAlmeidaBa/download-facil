"""Módulo de execução de movimentações físicas seguras de arquivos."""
from pathlib import Path
from datetime import datetime
import shutil
import csv
from threading import RLock
from src.config import LOG_DIR
from src.document_access import (
    DestinationSnapshot,
    FileSnapshot,
    validar_destino,
    validar_snapshot,
)

LOG_MOVIMENTACOES = LOG_DIR / "movimentacoes.csv"

# Pilha em memória para suporte a Desfazer (Undo)
HISTORICO_MOVIMENTACOES: list[dict] = []
_HISTORICO_LOCK = RLock()


def gerar_caminho_sem_colisao(pasta_destino: Path, nome_arquivo: str) -> Path:
    """Gera um caminho que garante que nenhum arquivo existente seja sobrescrito."""

    def ocupado(caminho: Path) -> bool:
        return caminho.exists() or caminho.is_symlink()

    candidato = pasta_destino / nome_arquivo
    if not ocupado(candidato):
        return candidato

    origem_path = Path(nome_arquivo)
    stem = origem_path.stem
    suffix = origem_path.suffix

    contador = 1
    while True:
        novo_nome = f"{stem}_{contador}{suffix}"
        candidato = pasta_destino / novo_nome
        if not ocupado(candidato):
            return candidato
        contador += 1


def registrar_movimentacao_log(
    acao: str,
    origem: Path,
    destino: Path,
    sucesso: bool,
    detalhes: str = "",
    log_dir: Path = None,
):
    """Registra auditoria das operações físicas de movimentação em CSV."""
    if log_dir is None:
        log_dir = LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    arquivo_log = log_dir / "movimentacoes.csv"

    precisa_cabecalho = not arquivo_log.exists()
    with arquivo_log.open("a", newline="", encoding="utf-8-sig") as f:
        escritor = csv.writer(f, delimiter=";")
        if precisa_cabecalho:
            escritor.writerow([
                "data_hora",
                "acao",
                "origem",
                "destino",
                "sucesso",
                "detalhes",
            ])
        escritor.writerow([
            datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            acao,
            str(origem),
            str(destino),
            "SIM" if sucesso else "NAO",
            detalhes,
        ])


def _registrar_log_operacao(*args, **kwargs) -> str | None:
    try:
        registrar_movimentacao_log(*args, **kwargs)
    except OSError as erro:
        return f"Não foi possível registrar a auditoria: {type(erro).__name__}."
    return None


def _mover_arquivo_seguro(
    origem: Path,
    destino_pasta: Path,
    log_dir: Path = None,
    arquivo_autorizado: FileSnapshot = None,
    destino_autorizado: DestinationSnapshot = None,
    id_autorizacao: str = None,
) -> dict:
    """Move um arquivo para a pasta de destino com salvaguardas rigorosas."""
    if not origem.exists():
        erro = f"Arquivo de origem não encontrado: {origem}"
        _registrar_log_operacao("MOVER", origem, destino_pasta, False, erro, log_dir)
        return {"sucesso": False, "erro": erro}

    if not origem.is_file():
        erro = f"O caminho de origem não é um arquivo: {origem}"
        _registrar_log_operacao("MOVER", origem, destino_pasta, False, erro, log_dir)
        return {"sucesso": False, "erro": erro}

    if arquivo_autorizado and not validar_snapshot(arquivo_autorizado):
        erro = "O arquivo mudou desde a análise."
        _registrar_log_operacao("MOVER", origem, destino_pasta, False, erro, log_dir)
        return {"sucesso": False, "erro": erro}

    if destino_autorizado and not validar_destino(destino_autorizado):
        erro = "O destino mudou desde a análise."
        _registrar_log_operacao("MOVER", origem, destino_pasta, False, erro, log_dir)
        return {"sucesso": False, "erro": erro}

    destino_final = None
    try:
        if not destino_autorizado:
            destino_pasta.mkdir(parents=True, exist_ok=True)
        destino_final = gerar_caminho_sem_colisao(destino_pasta, origem.name)

        if arquivo_autorizado and not validar_snapshot(arquivo_autorizado):
            raise RuntimeError("O arquivo mudou durante a confirmação da movimentação.")
        if destino_autorizado and not validar_destino(destino_autorizado):
            raise RuntimeError("O destino mudou durante a confirmação da movimentação.")

        shutil.move(str(origem), str(destino_final))
        estatisticas = destino_final.stat()
    except (OSError, shutil.Error, RuntimeError) as e:
        erro = f"Falha ao mover arquivo: {type(e).__name__}: {e}"
        _registrar_log_operacao("MOVER", origem, destino_pasta, False, erro, log_dir)
        return {"sucesso": False, "erro": erro}

    registro_historico = {
        "origem_original": str(origem),
        "destino_atual": str(destino_final),
        "id_autorizacao": id_autorizacao,
        "data_hora": datetime.now().isoformat(),
        "destino_resolvido": str(destino_final.resolve(strict=True)),
        "tamanho": estatisticas.st_size,
        "modificado_ns": estatisticas.st_mtime_ns,
        "dispositivo": estatisticas.st_dev,
        "identificador_arquivo": estatisticas.st_ino,
    }
    HISTORICO_MOVIMENTACOES.append(registro_historico)
    aviso_log = _registrar_log_operacao(
        "MOVER",
        origem,
        destino_final,
        True,
        f"Movido com sucesso. Destino final: {destino_final.name}",
        log_dir,
    )

    resultado = {
        "sucesso": True,
        "origem": str(origem),
        "destino": str(destino_final),
        "nome_final": destino_final.name,
    }
    if aviso_log:
        resultado["aviso"] = aviso_log
    return resultado


def mover_arquivo_seguro(
    origem: Path,
    destino_pasta: Path,
    log_dir: Path = None,
    arquivo_autorizado: FileSnapshot = None,
    destino_autorizado: DestinationSnapshot = None,
    id_autorizacao: str = None,
) -> dict:
    with _HISTORICO_LOCK:
        return _mover_arquivo_seguro(
            origem,
            destino_pasta,
            log_dir,
            arquivo_autorizado,
            destino_autorizado,
            id_autorizacao,
        )


def _desfazer_ultima_movimentacao(log_dir: Path = None) -> dict:
    """Reverte a última movimentação registrada na pilha."""
    if not HISTORICO_MOVIMENTACOES:
        return {"sucesso": False, "erro": "Nenhuma movimentação para desfazer."}

    ultima = HISTORICO_MOVIMENTACOES[-1]
    id_autorizacao = ultima.get("id_autorizacao")
    origem_original = Path(ultima["origem_original"])
    destino_atual = Path(ultima["destino_atual"])

    if not destino_atual.exists() or not destino_atual.is_file():
        erro = f"Arquivo não encontrado no local para reversão: {destino_atual}"
        aviso = _registrar_log_operacao(
            "DESFAZER", destino_atual, origem_original, False, erro, log_dir
        )
        resultado = {"sucesso": False, "erro": erro}
        if aviso:
            resultado["aviso"] = aviso
        return resultado

    try:
        estatisticas = destino_atual.stat()
        destino_resolvido = str(destino_atual.resolve(strict=True))
        if (
            destino_resolvido != ultima.get("destino_resolvido")
            or estatisticas.st_size != ultima.get("tamanho")
            or estatisticas.st_mtime_ns != ultima.get("modificado_ns")
            or estatisticas.st_dev != ultima.get("dispositivo")
            or (
                ultima.get("identificador_arquivo")
                and estatisticas.st_ino != ultima["identificador_arquivo"]
            )
        ):
            erro = "O arquivo no destino mudou desde a movimentação."
            aviso = _registrar_log_operacao(
                "DESFAZER", destino_atual, origem_original, False, erro, log_dir
            )
            resultado = {"sucesso": False, "erro": erro}
            if aviso:
                resultado["aviso"] = aviso
            return resultado

        origem_original.parent.mkdir(parents=True, exist_ok=True)
        destino_revertido = gerar_caminho_sem_colisao(origem_original.parent, origem_original.name)

        shutil.move(str(destino_atual), str(destino_revertido))
        HISTORICO_MOVIMENTACOES.pop()
    except (OSError, shutil.Error, RuntimeError) as e:
        erro = f"Falha ao desfazer: {type(e).__name__}: {e}"
        _registrar_log_operacao("DESFAZER", destino_atual, origem_original, False, erro, log_dir)
        return {"sucesso": False, "erro": erro}

    aviso_log = _registrar_log_operacao(
        "DESFAZER",
        destino_atual,
        destino_revertido,
        True,
        "Reversão concluída com sucesso.",
        log_dir,
    )
    resultado = {
        "sucesso": True,
        "arquivo_restaurado": str(destino_revertido),
        "origem_original": str(origem_original),
        "id_autorizacao": id_autorizacao,
        "mensagem": f"Arquivo restaurado para: {destino_revertido}",
    }
    if aviso_log:
        resultado["aviso"] = aviso_log
    return resultado


def desfazer_ultima_movimentacao(log_dir: Path = None) -> dict:
    with _HISTORICO_LOCK:
        return _desfazer_ultima_movimentacao(log_dir)


def obter_historico_movimentacoes() -> list[dict]:
    """Retorna cópia da lista de movimentações realizadas na sessão."""
    with _HISTORICO_LOCK:
        return [dict(item) for item in HISTORICO_MOVIMENTACOES]


def limpar_historico():
    """Limpa o histórico em memória."""
    with _HISTORICO_LOCK:
        HISTORICO_MOVIMENTACOES.clear()
