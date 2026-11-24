"""Módulo de registro e auditoria de decisões em arquivos CSV."""
from pathlib import Path
from datetime import datetime
import csv
from src.config import LOG_DIR, LOG_FILE


def preparar_log(log_dir: Path = None, log_file: Path = None) -> Path:
    if log_dir is None:
        log_dir = LOG_DIR
    if log_file is None:
        log_file = LOG_FILE

    log_dir.mkdir(parents=True, exist_ok=True)

    if not log_file.exists():
        with log_file.open("w", newline="", encoding="utf-8-sig") as arquivo_csv:
            escritor = csv.writer(arquivo_csv, delimiter=";")
            escritor.writerow([
                "data_hora_analise",
                "arquivo",
                "caminho_origem",
                "tipo_tecnico",
                "tipo_arquivo",
                "tipo_documental_sugerido",
                "confianca_tipo_documental",
                "evidencias_tipo_documental",
                "assunto_sugerido",
                "confianca_assunto",
                "fonte_evidencia",
                "estado_leitura",
                "estado_destino",
                "destino_sugerido",
                "destino_caminho",
                "evidencias_destino",
                "motivo_destino",
                "destino_legado_v0_10_1",
                "descricao_sugerida",
                "estado_ficha",
                "acao_fisica",
            ])

    return log_file


def registrar_decisao(log_file: Path, registro: dict):
    with log_file.open("a", newline="", encoding="utf-8-sig") as arquivo_csv:
        escritor = csv.writer(arquivo_csv, delimiter=";")
        escritor.writerow([
            datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            registro["arquivo"],
            registro["caminho"],
            registro["tipo_tecnico"],
            registro["tipo_arquivo"],
            registro["tipo_documental"],
            registro["confianca_tipo_documental"],
            registro["evidencias_tipo_documental"],
            registro["assunto"],
            registro["confianca_assunto"],
            registro["fonte_evidencia"],
            registro["estado_leitura"],
            registro["estado_destino"],
            registro["destino_sugerido"],
            registro["destino_caminho"],
            registro["evidencias_destino"],
            registro["motivo_destino"],
            registro["destino_legado"],
            registro["descricao"],
            registro["estado_ficha"],
            registro["acao_fisica"],
        ])
