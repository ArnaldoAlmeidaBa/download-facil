"""Starts the app against an isolated, reusable set of fictional documents."""
import argparse
import json
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
ENVIRONMENT = REPOSITORY.parent / "orquestrador-downloads-homologacao"
INPUT = ENVIRONMENT / "entrada"
DESTINATION_REVIEW = ENVIRONMENT / "destino-revisao"
DESTINATION_ARCHIVE = ENVIRONMENT / "destino-arquivo"
LOGS = ENVIRONMENT / "logs"
ARTIFACTS = ENVIRONMENT / "artefatos"
PROFILE_FILE = ENVIRONMENT / "perfil-homologacao.json"
PANEL_FILE = ARTIFACTS / "painel.html"
DECISIONS_LOG = LOGS / "decisoes.csv"

sys.path.insert(0, str(REPOSITORY))


def _create_fixtures() -> None:
    from docx import Document
    from openpyxl import Workbook
    from PIL import Image, ImageDraw

    for folder in (INPUT, DESTINATION_REVIEW, DESTINATION_ARCHIVE, LOGS, ARTIFACTS):
        folder.mkdir(parents=True, exist_ok=True)

    pdf_path = INPUT / "Ata de Revisao Manual - Homologacao.pdf"
    if not pdf_path.exists():
        pdf_image = Image.new("RGB", (800, 1120), "white")
        draw = ImageDraw.Draw(pdf_image)
        draw.rectangle((35, 35, 765, 1085), outline="#31577a", width=5)
        draw.text((80, 120), "DOCUMENTO FICTICIO DE HOMOLOGACAO", fill="#17324d")
        draw.text((80, 190), "Destino de teste: revisao manual", fill="#31577a")
        pdf_image.save(pdf_path, format="PDF", resolution=110)

    txt_path = INPUT / "Notas de Revisao Manual - Homologacao.txt"
    if not txt_path.exists():
        txt_path.write_text(
            "Documento fictício para homologação manual.\n"
            "Contexto: revisão manual de arquivos de teste.\n",
            encoding="utf-8",
        )

    docx_path = INPUT / "Relatorio de Revisao Manual - Homologacao.docx"
    if not docx_path.exists():
        document = Document()
        document.add_heading("Relatório fictício de homologação", level=1)
        document.add_paragraph(
            "Este arquivo contém somente dados de teste para revisão manual."
        )
        document.add_paragraph("Destino de teste: revisão manual.")
        document.save(docx_path)

    xlsx_path = INPUT / "Planilha de Arquivo Oficial - Homologacao.xlsx"
    if not xlsx_path.exists():
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Dados fictícios"
        sheet.append(["Item", "Descrição"])
        sheet.append(["Amostra", "Arquivo oficial de homologação, sem dados reais"])
        workbook.save(xlsx_path)

    image_path = INPUT / "Imagem de Arquivo Oficial - Homologacao.png"
    if not image_path.exists():
        image = Image.new("RGB", (900, 520), "#e8eef5")
        draw = ImageDraw.Draw(image)
        draw.rectangle((30, 30, 870, 490), outline="#31577a", width=4)
        draw.text((70, 180), "DOWNLOAD FACIL - IMAGEM FICTICIA", fill="#17324d")
        draw.text((70, 235), "Fixture para homologacao local", fill="#31577a")
        image.save(image_path, format="PNG")


def _expected_profile() -> dict:
    return {
        "usuario_windows": "Usuario de Homologacao",
        "pastas_entrada": [{
            "nome": "Entrada de Homologacao",
            "caminho": str(INPUT),
            "monitorar": True,
        }],
        "territorio_documental": [
            {
                "nome": "Revisao de Homologacao",
                "caminho": str(DESTINATION_REVIEW),
                "papel": "DESTINO",
                "pode_receber_arquivos": True,
                "contextos_associados": ["revisao manual"],
            },
            {
                "nome": "Arquivo de Homologacao",
                "caminho": str(DESTINATION_ARCHIVE),
                "papel": "DESTINO",
                "pode_receber_arquivos": True,
                "contextos_associados": ["arquivo oficial"],
            },
        ],
    }


def _load_profile() -> dict:
    with PROFILE_FILE.open("r", encoding="utf-8") as stream:
        profile = json.load(stream)
    if profile != _expected_profile():
        raise RuntimeError(
            "O perfil isolado foi alterado; restaure-o antes de iniciar a homologação."
        )
    return profile


def _prepare_environment() -> None:
    _create_fixtures()
    if PROFILE_FILE.exists():
        _load_profile()
        return

    PROFILE_FILE.write_text(
        json.dumps(_expected_profile(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Inicia a homologação local isolada.")
    parser.add_argument("--porta", type=int, default=8080)
    parser.add_argument("--sem-navegador", action="store_true")
    args = parser.parse_args()

    _prepare_environment()

    import src.actions.file_mover as file_mover
    import src.core as core
    import src.dashboard.generator as dashboard
    import src.server as server

    file_mover.LOG_DIR = LOGS
    dashboard.carregar_perfil = _load_profile
    server.PAINEL_FILE = PANEL_FILE

    def run_analysis(abrir_navegador: bool = False) -> dict:
        return core.executar_orquestracao(
            perfil=_load_profile(),
            log_file=DECISIONS_LOG,
            painel_file=PANEL_FILE,
            abrir_navegador=abrir_navegador,
        )

    server.executar_orquestracao = run_analysis
    run_analysis()

    print("\nAmbiente isolado de homologação pronto.")
    print(f"Perfil: {PROFILE_FILE}")
    print(f"Entrada fictícia: {INPUT}")
    print(f"Destinos autorizados: {DESTINATION_REVIEW} ; {DESTINATION_ARCHIVE}")
    print(f"Logs e painel: {ENVIRONMENT}")
    print("O painel será aberto no navegador. Encerre o servidor com Ctrl+C.")
    server.iniciar_servidor(porta=args.porta, abrir_navegador=not args.sem_navegador)


if __name__ == "__main__":
    main()
