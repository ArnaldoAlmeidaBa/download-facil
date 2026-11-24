"""Ponto de entrada do Orquestrador de Downloads.

Executa a orquestração através do pacote modularizado `src`.
"""
import sys
import os
from pathlib import Path

# Proteção contra erros de saída e suporte completo a Unicode (UTF-8) no Windows
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
else:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")
else:
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.core import (
    main,
    executar_orquestracao,
    analisar_arquivo,
)
from src.config import (
    carregar_perfil,
    PERFIL_FILE,
    LOG_FILE,
    PAINEL_FILE,
)

if __name__ == "__main__":
    main()
