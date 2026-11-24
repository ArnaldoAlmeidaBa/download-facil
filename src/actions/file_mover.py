"""Módulo de execução de movimentações físicas seguras de arquivos."""
from pathlib import Path
from datetime import datetime
import shutil
import csv
from src.config import LOG_DIR

LOG_MOVIMENTACOES = LOG_DIR / "movimentacoes.csv"

# Pilha em memória para suporte a Desfazer (Undo)
HISTORICO_MOVIMENTACOES: list[dict] = []


def gerar_caminho_sem_colisao(pasta_destino: Path, nome_arquivo: str) -> Path:
    """Gera um caminho que garante que nenhum arquivo existente seja sobrescrito."""
    candidato = pasta_destino / nome_arquivo
    if not candidato.exists():
        return candidato

    origem_path = Path(nome_arquivo)
    stem = origem_path.stem
    suffix = origem_path.suffix

    contador = 1
    while True:
        novo_nome = f"{stem}_{contador}{suffix}"
        candidato = pasta_destino / novo_nome
        if not candidato.exists():
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


def mover_arquivo_seguro(
    origem: Path,
    destino_pasta: Path,
    log_dir: Path = None,
) -> dict:
    """Move um arquivo para a pasta de destino com salvaguardas rigorosas."""
    if not origem.exists():
        erro = f"Arquivo de origem não encontrado: {origem}"
        registrar_movimentacao_log("MOVER", origem, destino_pasta, False, erro, log_dir)
        return {"sucesso": False, "erro": erro}

    if not origem.is_file():
        erro = f"O caminho de origem não é um arquivo: {origem}"
        registrar_movimentacao_log("MOVER", origem, destino_pasta, False, erro, log_dir)
        return {"sucesso": False, "erro": erro}

    try:
        destino_pasta.mkdir(parents=True, exist_ok=True)
        destino_final = gerar_caminho_sem_colisao(destino_pasta, origem.name)

        shutil.move(str(origem), str(destino_final))

        registro_historico = {
            "origem_original": str(origem),
            "destino_atual": str(destino_final),
            "data_hora": datetime.now().isoformat(),
        }
        HISTORICO_MOVIMENTACOES.append(registro_historico)

        registrar_movimentacao_log(
            "MOVER",
            origem,
            destino_final,
            True,
            f"Movido com sucesso. Destino final: {destino_final.name}",
            log_dir,
        )

        return {
            "sucesso": True,
            "origem": str(origem),
            "destino": str(destino_final),
            "nome_final": destino_final.name,
        }
    except Exception as e:
        erro = f"Falha ao mover arquivo: {type(e).__name__}: {e}"
        registrar_movimentacao_log("MOVER", origem, destino_pasta, False, erro, log_dir)
        return {"sucesso": False, "erro": erro}


def desfazer_ultima_movimentacao(log_dir: Path = None) -> dict:
    """Reverte a última movimentação registrada na pilha."""
    if not HISTORICO_MOVIMENTACOES:
        return {"sucesso": False, "erro": "Nenhuma movimentação para desfazer."}

    ultima = HISTORICO_MOVIMENTACOES.pop()
    origem_original = Path(ultima["origem_original"])
    destino_atual = Path(ultima["destino_atual"])

    if not destino_atual.exists():
        erro = f"Arquivo não encontrado no local para reversão: {destino_atual}"
        registrar_movimentacao_log("DESFAZER", destino_atual, origem_original, False, erro, log_dir)
        return {"sucesso": False, "erro": erro}

    try:
        origem_original.parent.mkdir(parents=True, exist_ok=True)
        destino_revertido = gerar_caminho_sem_colisao(origem_original.parent, origem_original.name)

        shutil.move(str(destino_atual), str(destino_revertido))

        registrar_movimentacao_log(
            "DESFAZER",
            destino_atual,
            destino_revertido,
            True,
            "Reversão concluída com sucesso.",
            log_dir,
        )

        return {
            "sucesso": True,
            "arquivo_restaurado": str(destino_revertido),
            "mensagem": f"Arquivo restaurado para: {destino_revertido}",
        }
    except Exception as e:
        erro = f"Falha ao desfazer: {type(e).__name__}: {e}"
        registrar_movimentacao_log("DESFAZER", destino_atual, origem_original, False, erro, log_dir)
        return {"sucesso": False, "erro": erro}


def obter_historico_movimentacoes() -> list[dict]:
    """Retorna cópia da lista de movimentações realizadas na sessão."""
    return list(HISTORICO_MOVIMENTACOES)


def limpar_historico():
    """Limpa o histórico em memória."""
    HISTORICO_MOVIMENTACOES.clear()
