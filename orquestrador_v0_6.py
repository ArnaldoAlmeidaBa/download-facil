from pathlib import Path
from datetime import datetime
import csv
import unicodedata

from docx import Document
from pypdf import PdfReader
from openpyxl import load_workbook


BASE_DIR = Path(__file__).resolve().parent
DOWNLOADS = Path.home() / "Downloads"

LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "decisoes_v0_6.csv"

MAX_TEXTO = 20000

CATEGORIAS = {
    "IMAGEM": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"},
    "DOCUMENTO": {".pdf", ".doc", ".docx", ".txt", ".odt", ".rtf"},
    "PLANILHA": {".xls", ".xlsx", ".csv", ".ods"},
    "APRESENTACAO": {".ppt", ".pptx", ".odp"},
    "ARQUIVO_COMPACTADO": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "INSTALADOR": {".exe", ".msi"},
}

IGNORAR = {
    "desktop.ini",
    "thumbs.db",
}

REGRAS_ASSUNTO = [
    {
        "termos": ["oficio", "sec"],
        "assunto": "OFICIO_SEC",
        "destino": r"REVISAR\Oficios_SEC",
        "motivo": "Há evidência compatível com ofício da SEC.",
    },
    {
        "termos": ["planejamento", "pedagogico"],
        "assunto": "PLANEJAMENTO_PEDAGOGICO",
        "destino": r"REVISAR\Planejamento_Pedagogico",
        "motivo": "Há evidência compatível com planejamento pedagógico.",
    },
    {
        "termos": ["lista", "alunos"],
        "assunto": "LISTA_DE_ALUNOS",
        "destino": r"REVISAR\Alunos",
        "motivo": "Há evidência compatível com relação/lista de alunos.",
    },
    {
        "termos": ["logo", "ceti"],
        "assunto": "IDENTIDADE_VISUAL_CETI",
        "destino": r"REVISAR\Identidade_Visual_CETI",
        "motivo": "Há evidência compatível com identidade visual do CETI.",
    },
]


def normalizar(texto: str) -> str:
    texto = texto.lower()

    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )

    for caractere in [
        "_", "-", ".", ",", ";", ":", "/", "\\",
        "\n", "\r", "\t", "(", ")", "[", "]"
    ]:
        texto = texto.replace(caractere, " ")

    return " ".join(texto.split())


def classificar_tipo(arquivo: Path) -> str:
    if arquivo.name.lower() in IGNORAR:
        return "IGNORAR"

    extensao = arquivo.suffix.lower()

    for categoria, extensoes in CATEGORIAS.items():
        if extensao in extensoes:
            return categoria

    return "OUTRO"


def ler_txt(arquivo: Path) -> str:
    return arquivo.read_text(
        encoding="utf-8",
        errors="replace",
    )[:MAX_TEXTO]


def ler_docx(arquivo: Path) -> str:
    documento = Document(arquivo)

    partes = []

    for paragrafo in documento.paragraphs:
        texto = paragrafo.text.strip()
        if texto:
            partes.append(texto)

    for tabela in documento.tables:
        for linha in tabela.rows:
            valores = [
                celula.text.strip()
                for celula in linha.cells
                if celula.text.strip()
            ]

            if valores:
                partes.append(" | ".join(valores))

    return "\n".join(partes)[:MAX_TEXTO]


def ler_pdf(arquivo: Path) -> str:
    leitor = PdfReader(str(arquivo))

    partes = []

    for pagina in leitor.pages:
        texto = pagina.extract_text() or ""

        if texto.strip():
            partes.append(texto.strip())

        if sum(len(parte) for parte in partes) >= MAX_TEXTO:
            break

    return "\n".join(partes)[:MAX_TEXTO]


def ler_xlsx(arquivo: Path) -> str:
    workbook = load_workbook(
        filename=arquivo,
        read_only=True,
        data_only=True,
    )

    partes = []

    try:
        for planilha in workbook.worksheets:
            partes.append(f"PLANILHA: {planilha.title}")

            for linha in planilha.iter_rows(values_only=True):
                valores = [
                    str(valor).strip()
                    for valor in linha
                    if valor is not None and str(valor).strip()
                ]

                if valores:
                    partes.append(" | ".join(valores))

                if sum(len(parte) for parte in partes) >= MAX_TEXTO:
                    return "\n".join(partes)[:MAX_TEXTO]

    finally:
        workbook.close()

    return "\n".join(partes)[:MAX_TEXTO]


def ler_conteudo_textual(arquivo: Path) -> tuple[str, str]:
    extensao = arquivo.suffix.lower()

    leitores = {
        ".txt": ler_txt,
        ".docx": ler_docx,
        ".pdf": ler_pdf,
        ".xlsx": ler_xlsx,
    }

    leitor = leitores.get(extensao)

    if leitor is None:
        return "", "NAO_SUPORTADO_NESTA_VERSAO"

    try:
        conteudo = leitor(arquivo)

        if not conteudo.strip():
            return "", "LIDO_SEM_TEXTO_UTIL"

        return conteudo, "LIDO"

    except Exception as erro:
        return "", f"ERRO_LEITURA: {type(erro).__name__}: {erro}"


def regra_encontrada(texto: str):
    texto_normalizado = normalizar(texto)

    for regra in REGRAS_ASSUNTO:
        if all(
            normalizar(termo) in texto_normalizado
            for termo in regra["termos"]
        ):
            return regra

    return None


def analisar_assunto(arquivo: Path) -> dict:
    regra_nome = regra_encontrada(arquivo.stem)

    conteudo, estado_leitura = ler_conteudo_textual(arquivo)

    regra_conteudo = (
        regra_encontrada(conteudo)
        if conteudo
        else None
    )

    if (
        regra_nome
        and regra_conteudo
        and regra_nome["assunto"] == regra_conteudo["assunto"]
    ):
        return {
            "assunto": regra_nome["assunto"],
            "destino": regra_nome["destino"],
            "confianca": "ALTA",
            "fonte_evidencia": "NOME+CONTEUDO",
            "estado_leitura": estado_leitura,
            "motivo": (
                f"{regra_nome['motivo']} "
                "Nome e conteúdo fornecem evidências concordantes."
            ),
        }

    if (
        regra_nome
        and regra_conteudo
        and regra_nome["assunto"] != regra_conteudo["assunto"]
    ):
        return {
            "assunto": "CONFLITO_DE_EVIDENCIAS",
            "destino": r"REVISAR\Conflitos",
            "confianca": "BAIXA",
            "fonte_evidencia": "NOME<>CONTEUDO",
            "estado_leitura": estado_leitura,
            "motivo": (
                f"O nome sugere {regra_nome['assunto']}, "
                f"mas o conteúdo sugere {regra_conteudo['assunto']}."
            ),
        }

    if regra_conteudo:
        return {
            "assunto": regra_conteudo["assunto"],
            "destino": regra_conteudo["destino"],
            "confianca": "ALTA",
            "fonte_evidencia": "CONTEUDO",
            "estado_leitura": estado_leitura,
            "motivo": (
                f"{regra_conteudo['motivo']} "
                "A classificação foi sustentada pelo conteúdo."
            ),
        }

    if regra_nome:
        return {
            "assunto": regra_nome["assunto"],
            "destino": regra_nome["destino"],
            "confianca": "MEDIA",
            "fonte_evidencia": "NOME",
            "estado_leitura": estado_leitura,
            "motivo": (
                f"{regra_nome['motivo']} "
                "A classificação está sustentada apenas pelo nome do arquivo."
            ),
        }

    return {
        "assunto": "NAO_IDENTIFICADO",
        "destino": r"REVISAR\Nao_Identificados",
        "confianca": "BAIXA",
        "fonte_evidencia": "NENHUMA",
        "estado_leitura": estado_leitura,
        "motivo": (
            "Não foi encontrada evidência suficiente "
            "para classificar o assunto."
        ),
    }


def preparar_log() -> Path:
    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not LOG_FILE.exists():
        with LOG_FILE.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as arquivo_csv:

            escritor = csv.writer(
                arquivo_csv,
                delimiter=";",
            )

            escritor.writerow([
                "data_hora_analise",
                "arquivo",
                "caminho_origem",
                "tipo_tecnico",
                "assunto_sugerido",
                "confianca",
                "fonte_evidencia",
                "estado_leitura",
                "destino_sugerido",
                "motivo",
                "acao_fisica",
            ])

    return LOG_FILE


def registrar_decisao(
    log_file: Path,
    arquivo: Path,
    tipo: str,
    analise: dict,
    acao: str,
):
    with log_file.open(
        "a",
        newline="",
        encoding="utf-8-sig",
    ) as arquivo_csv:

        escritor = csv.writer(
            arquivo_csv,
            delimiter=";",
        )

        escritor.writerow([
            datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            arquivo.name,
            str(arquivo),
            tipo,
            analise["assunto"],
            analise["confianca"],
            analise["fonte_evidencia"],
            analise["estado_leitura"],
            analise["destino"],
            analise["motivo"],
            acao,
        ])


log_file = preparar_log()

print(f"\nObservando pasta: {DOWNLOADS}")
print("MODO: DRY-RUN — nenhum arquivo será movido.")
print(f"Log: {log_file}\n")

if not DOWNLOADS.exists():
    print("A pasta Downloads não foi encontrada.")

else:
    arquivos = [
        item
        for item in DOWNLOADS.iterdir()
        if item.is_file()
    ]

    for arquivo in sorted(
        arquivos,
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ):
        tipo = classificar_tipo(arquivo)

        print(f"Arquivo: {arquivo.name}")
        print(f"Tipo técnico: {tipo}")

        if tipo == "IGNORAR":
            analise = {
                "assunto": "NAO_APLICAVEL",
                "destino": "",
                "confianca": "ALTA",
                "fonte_evidencia": "REGRA_SISTEMA",
                "estado_leitura": "NAO_APLICAVEL",
                "motivo": (
                    "Arquivo de sistema configurado "
                    "para ser ignorado."
                ),
            }

            acao = "NENHUMA — IGNORADO"

            print("Decisão: IGNORAR")
            print(f"Motivo: {analise['motivo']}")

        else:
            analise = analisar_assunto(arquivo)
            acao = "NENHUMA — DRY-RUN"

            print(f"Assunto sugerido: {analise['assunto']}")
            print(f"Confiança: {analise['confianca']}")
            print(f"Fonte da evidência: {analise['fonte_evidencia']}")
            print(f"Estado da leitura: {analise['estado_leitura']}")
            print(f"Destino sugerido: {analise['destino']}")
            print(f"Motivo: {analise['motivo']}")

        print("Ação física: NENHUMA")

        registrar_decisao(
            log_file=log_file,
            arquivo=arquivo,
            tipo=tipo,
            analise=analise,
            acao=acao,
        )

        print("-" * 70)

print("\nAnálise concluída.")
print(f"Decisões registradas em: {log_file}")