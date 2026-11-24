"""Módulo de configuração e constantes do Orquestrador de Downloads."""
from pathlib import Path
import os
import sys
import json

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

AKIRA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Akira"
PERFIL_FILE = AKIRA_DIR / "perfil.json"

LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "decisoes.csv"
PAINEL_FILE = BASE_DIR / "painel.html"

MAX_TEXTO = 20000
MAX_DESCRICAO = 620
MAX_PREVIEW_TEXTO = 12000
MAX_PREVIEW_IMAGEM_BYTES = 8 * 1024 * 1024
MAX_PREVIEW_MIDIA_BYTES = 40 * 1024 * 1024

CATEGORIAS = {
    "IMAGEM": {
        ".jpg", ".jpeg", ".png", ".gif",
        ".webp", ".bmp", ".svg"
    },
    "DOCUMENTO": {
        ".pdf", ".doc", ".docx", ".txt",
        ".odt", ".rtf"
    },
    "PLANILHA": {
        ".xls", ".xlsx", ".csv", ".ods"
    },
    "APRESENTACAO": {
        ".ppt", ".pptx", ".odp"
    },
    "AUDIO": {
        ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"
    },
    "VIDEO": {
        ".mp4", ".m4v", ".webm", ".mov"
    },
    "ARQUIVO_COMPACTADO": {
        ".zip", ".rar", ".7z", ".tar", ".gz"
    },
    "INSTALADOR": {
        ".exe", ".msi"
    },
}

IGNORAR = {
    "desktop.ini",
    "thumbs.db",
}

ROTULOS = {
    "NAO_IDENTIFICADO": "Ainda não identificado",
    "NAO_APLICAVEL": "Não se aplica",
    "TCC": "TCC",
    "SUMARIO": "Sumário",
    "MATRIZ_DE_CONTEUDOS": "Matriz de conteúdos",
    "PLANEJAMENTO_PEDAGOGICO": "Planejamento pedagógico",
    "LISTA_DE_ALUNOS": "Lista de alunos",
    "OFICIO_SEC": "Ofício da SEC",
    "IDENTIDADE_VISUAL_CETI": "Identidade visual do CETI",
    "CONFLITO_DE_EVIDENCIAS": "Informações divergentes",
}


def rotulo(valor: str) -> str:
    if valor in ROTULOS:
        return ROTULOS[valor]
    return valor.replace("_", " ").strip().capitalize()


def rotulo_tipo_arquivo(tipo_tecnico: str, extensao: str) -> str:
    extensao = (extensao or "").lower()
    if extensao in {".xls", ".xlsx", ".csv", ".ods"}:
        return "Planilha"
    if extensao in {".doc", ".docx", ".txt", ".odt", ".rtf"}:
        return "Texto"
    if extensao == ".pdf":
        return "PDF"
    if extensao in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}:
        return "Imagem"
    if extensao in {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}:
        return "Áudio"
    if extensao in {".mp4", ".m4v", ".webm", ".mov"}:
        return "Vídeo"
    if extensao in {".zip", ".rar", ".7z", ".tar", ".gz"}:
        return "Arquivo compactado"
    if extensao in {".exe", ".msi"}:
        return "Instalador"
    if tipo_tecnico == "APRESENTACAO":
        return "Apresentação"
    if tipo_tecnico == "IGNORAR":
        return "Arquivo de sistema"
    return "Outro"


def formatar_tamanho(tamanho: int) -> str:
    if tamanho < 1024:
        return f"{tamanho} B"
    if tamanho < 1024 * 1024:
        return f"{tamanho / 1024:.1f} KB"
    return f"{tamanho / (1024 * 1024):.1f} MB"


def classificar_tipo(arquivo: Path) -> str:
    if arquivo.name.lower() in IGNORAR:
        return "IGNORAR"
    extensao = arquivo.suffix.lower()
    for categoria, extensoes in CATEGORIAS.items():
        if extensao in extensoes:
            return categoria
    return "OUTRO"


def carregar_perfil() -> dict:
    perfil_candidatos = [
        PERFIL_FILE,
        BASE_DIR / "perfil.json",
    ]
    perfil_path = None
    for cand in perfil_candidatos:
        if cand.exists():
            perfil_path = cand
            break

    if perfil_path is None:
        home_dir = Path.home()
        downloads_dir = home_dir / "Downloads"
        revisar_dir = home_dir / "Documents" / "Revisar"
        perfil = {
            "usuario_windows": os.environ.get("USERNAME", home_dir.name),
            "pastas_entrada": [
                {
                    "nome": "Downloads",
                    "caminho": str(downloads_dir),
                    "monitorar": True
                }
            ],
            "territorio_documental": [
                {
                    "nome": "Revisar",
                    "caminho": str(revisar_dir),
                    "papel": "DESTINO",
                    "pode_receber_arquivos": True,
                    "contextos_associados": []
                }
            ]
        }
        try:
            AKIRA_DIR.mkdir(parents=True, exist_ok=True)
            with PERFIL_FILE.open("w", encoding="utf-8") as f:
                json.dump(perfil, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        return perfil

    with perfil_path.open("r", encoding="utf-8-sig") as arquivo_perfil:
        perfil = json.load(arquivo_perfil)

    pastas_entrada = perfil.get("pastas_entrada", [])
    entradas_ativas = [
        pasta
        for pasta in pastas_entrada
        if pasta.get("monitorar", True)
        and pasta.get("caminho")
    ]

    # Validação e correção de caminhos se apontarem para pastas inexistentes de outro usuário
    for pasta in entradas_ativas:
        p_caminho = Path(pasta["caminho"])
        if not p_caminho.exists():
            if pasta.get("nome") == "Downloads" and (Path.home() / "Downloads").exists():
                pasta["caminho"] = str(Path.home() / "Downloads")

    for pasta in perfil.get("territorio_documental", []):
        p_caminho = Path(pasta["caminho"])
        if not p_caminho.exists():
            if pasta.get("nome") == "Revisar":
                revisar_atual = Path.home() / "Documents" / "Revisar"
                revisar_atual.mkdir(parents=True, exist_ok=True)
                pasta["caminho"] = str(revisar_atual)

    if not entradas_ativas:
        raise ValueError(
            "O perfil do Akira não possui pasta de entrada ativa."
        )

    return perfil
