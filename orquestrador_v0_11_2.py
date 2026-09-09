from pathlib import Path
from datetime import datetime
from html import escape
import base64
import csv
import mimetypes
import json
import os
import re
import unicodedata
import webbrowser

from docx import Document
from pypdf import PdfReader
from openpyxl import load_workbook
import xlrd
from pptx import Presentation


# ============================================================
# CONFIGURAÇÃO
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

AKIRA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Akira"
PERFIL_FILE = AKIRA_DIR / "perfil.json"

LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "decisoes_v0_11_2.csv"

PAINEL_FILE = BASE_DIR / "painel.html"


def carregar_perfil() -> dict:
    if not PERFIL_FILE.exists():
        raise FileNotFoundError(
            f"Perfil do Akira não encontrado: {PERFIL_FILE}"
        )

    with PERFIL_FILE.open(
        "r",
        encoding="utf-8-sig",
    ) as arquivo_perfil:
        perfil = json.load(arquivo_perfil)

    pastas_entrada = perfil.get("pastas_entrada", [])

    entradas_ativas = [
        pasta
        for pasta in pastas_entrada
        if pasta.get("monitorar", True)
        and pasta.get("caminho")
    ]

    if not entradas_ativas:
        raise ValueError(
            "O perfil do Akira não possui pasta de entrada ativa."
        )

    return perfil


PERFIL = carregar_perfil()

PASTAS_ENTRADA = [
    Path(pasta["caminho"])
    for pasta in PERFIL["pastas_entrada"]
    if pasta.get("monitorar", True)
    and pasta.get("caminho")
]

# Compatibilidade com a V0.10:
# nesta etapa controlada, o restante do motor continua trabalhando
# com uma única caixa de entrada. O perfil já admite 1..N entradas,
# mas a ampliação do processamento ficará para uma etapa posterior.
DOWNLOADS = PASTAS_ENTRADA[0]

TERRITORIO_DOCUMENTAL = PERFIL.get(
    "territorio_documental",
    [],
)

MAX_TEXTO = 20000
MAX_DESCRICAO = 620
MAX_PREVIEW_TEXTO = 12000

# Evita transformar imagens muito grandes em um painel HTML gigantesco.
MAX_PREVIEW_IMAGEM_BYTES = 8 * 1024 * 1024


# ============================================================
# TIPOS TÉCNICOS
# ============================================================

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


# ============================================================
# NOMES AMIGÁVEIS PARA INTERFACE
# ============================================================

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

    return (
        valor
        .replace("_", " ")
        .strip()
        .capitalize()
    )


def rotulo_tipo_arquivo(
    tipo_tecnico: str,
    extensao: str,
) -> str:

    extensao = (
        extensao
        or ""
    ).lower()

    if extensao in {
        ".xls",
        ".xlsx",
        ".csv",
        ".ods",
    }:
        return "Planilha"

    if extensao in {
        ".doc",
        ".docx",
        ".txt",
        ".odt",
        ".rtf",
    }:
        return "Texto"

    if extensao == ".pdf":
        return "PDF"

    if extensao in {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".bmp",
        ".svg",
    }:
        return "Imagem"

    if extensao in {
        ".mp3",
        ".wav",
        ".m4a",
        ".aac",
        ".ogg",
        ".flac",
    }:
        return "Áudio"

    if extensao in {
        ".mp4",
        ".m4v",
        ".webm",
        ".mov",
    }:
        return "Vídeo"

    if extensao in {
        ".zip",
        ".rar",
        ".7z",
        ".tar",
        ".gz",
    }:
        return "Arquivo compactado"

    if extensao in {
        ".exe",
        ".msi",
    }:
        return "Instalador"

    if tipo_tecnico == "APRESENTACAO":
        return "Apresentação"

    if tipo_tecnico == "IGNORAR":
        return "Arquivo de sistema"

    return "Outro"


# ============================================================
# REGRAS DE TIPO DOCUMENTAL
# ============================================================

REGRAS_TIPO_DOCUMENTAL = [
    {
        "tipo_documental": "TCC",
        "sinais": [
            "trabalho de conclusao de curso",
            "apresentado como requisito",
            "referencial teorico",
            "metodologia",
            "consideracoes finais",
        ],
        "sinais_fortes": [
            "trabalho de conclusao de curso",
            "apresentado como requisito",
        ],
        "minimo_sinais": 2,
    },
    {
        "tipo_documental": "MATRIZ_DE_CONTEUDOS",
        "sinais": [
            "matriz de conteudos",
            "disciplina",
            "carga horaria",
            "eixo",
        ],
        "sinais_fortes": [
            "matriz de conteudos",
        ],
        "minimo_sinais": 3,
    },
    {
        "tipo_documental": "SUMARIO",
        "sinais": [
            "sumario",
            "introducao",
            "referencial teorico",
            "metodologia",
            "conclusao",
            "referencias",
        ],
        "sinais_fortes": [
            "sumario",
        ],
        "minimo_sinais": 4,
    },
]


# ============================================================
# REGRAS DE ASSUNTO
#
# Ainda são experimentais.
# Não autorizam movimentação.
# ============================================================

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


# ============================================================
# UTILITÁRIOS
# ============================================================

def normalizar(texto: str) -> str:
    texto = texto.lower()

    texto = unicodedata.normalize(
        "NFD",
        texto
    )

    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )

    for caractere in [
        "_", "-", ".", ",", ";", ":",
        "/", "\\", "\n", "\r", "\t",
        "(", ")", "[", "]"
    ]:
        texto = texto.replace(
            caractere,
            " "
        )

    return " ".join(
        texto.split()
    )


def limpar_texto(texto: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        texto
    ).strip()


def limitar_texto(
    texto: str,
    limite: int
) -> str:
    texto = limpar_texto(
        texto
    )

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


def formatar_tamanho(
    tamanho: int
) -> str:
    if tamanho < 1024:
        return f"{tamanho} B"

    if tamanho < 1024 * 1024:
        return f"{tamanho / 1024:.1f} KB"

    return (
        f"{tamanho / (1024 * 1024):.1f} MB"
    )


def classificar_tipo(
    arquivo: Path
) -> str:
    if arquivo.name.lower() in IGNORAR:
        return "IGNORAR"

    extensao = arquivo.suffix.lower()

    for categoria, extensoes in CATEGORIAS.items():
        if extensao in extensoes:
            return categoria

    return "OUTRO"


# ============================================================
# LEITORES
# ============================================================

def ler_txt(
    arquivo: Path
) -> str:
    return arquivo.read_text(
        encoding="utf-8",
        errors="replace",
    )[:MAX_TEXTO]


def ler_docx(
    arquivo: Path
) -> str:
    documento = Document(
        arquivo
    )

    partes = []

    for paragrafo in documento.paragraphs:
        texto = paragrafo.text.strip()

        if texto:
            partes.append(
                texto
            )

    for tabela in documento.tables:
        for linha in tabela.rows:
            valores = [
                celula.text.strip()
                for celula in linha.cells
                if celula.text.strip()
            ]

            if valores:
                partes.append(
                    " | ".join(valores)
                )

    return "\n".join(
        partes
    )[:MAX_TEXTO]


def ler_pdf(
    arquivo: Path
) -> str:
    leitor = PdfReader(
        str(arquivo)
    )

    partes = []
    tamanho_atual = 0

    for pagina in leitor.pages:
        texto = (
            pagina.extract_text()
            or ""
        ).strip()

        if texto:
            partes.append(
                texto
            )

            tamanho_atual += len(
                texto
            )

        if tamanho_atual >= MAX_TEXTO:
            break

    return "\n".join(
        partes
    )[:MAX_TEXTO]


def ler_xlsx(
    arquivo: Path
) -> str:
    workbook = load_workbook(
        filename=arquivo,
        read_only=True,
        data_only=True,
    )

    partes = []
    tamanho_atual = 0

    try:
        for planilha in workbook.worksheets:
            cabecalho = (
                f"PLANILHA: {planilha.title}"
            )

            partes.append(
                cabecalho
            )

            tamanho_atual += len(
                cabecalho
            )

            for linha in planilha.iter_rows(
                values_only=True
            ):
                valores = [
                    str(valor).strip()
                    for valor in linha
                    if (
                        valor is not None
                        and str(valor).strip()
                    )
                ]

                if valores:
                    trecho = " | ".join(
                        valores
                    )

                    partes.append(
                        trecho
                    )

                    tamanho_atual += len(
                        trecho
                    )

                if tamanho_atual >= MAX_TEXTO:
                    return "\n".join(
                        partes
                    )[:MAX_TEXTO]

    finally:
        workbook.close()

    return "\n".join(
        partes
    )[:MAX_TEXTO]


def ler_xls(
    arquivo: Path
) -> str:
    workbook = xlrd.open_workbook(
        str(arquivo)
    )

    partes = []
    tamanho_atual = 0

    for planilha in workbook.sheets():
        cabecalho = (
            f"PLANILHA: {planilha.name}"
        )
        partes.append(cabecalho)
        tamanho_atual += len(cabecalho)

        limite_linhas = min(
            planilha.nrows,
            250,
        )
        limite_colunas = min(
            planilha.ncols,
            40,
        )

        for indice_linha in range(
            limite_linhas
        ):
            valores = []

            for indice_coluna in range(
                limite_colunas
            ):
                valor = planilha.cell_value(
                    indice_linha,
                    indice_coluna,
                )

                if (
                    valor is not None
                    and str(valor).strip()
                ):
                    valores.append(
                        str(valor).strip()
                    )

            if valores:
                trecho = " | ".join(
                    valores
                )
                partes.append(trecho)
                tamanho_atual += len(trecho)

            if tamanho_atual >= MAX_TEXTO:
                return "\n".join(
                    partes
                )[:MAX_TEXTO]

    return "\n".join(
        partes
    )[:MAX_TEXTO]


def ler_pptx(
    arquivo: Path
) -> str:
    apresentacao = Presentation(
        str(arquivo)
    )

    partes = []
    tamanho_atual = 0

    for numero, slide in enumerate(
        apresentacao.slides,
        start=1
    ):
        textos_slide = []

        for shape in slide.shapes:
            if not hasattr(
                shape,
                "text",
            ):
                continue

            texto_shape = (
                shape.text
                or ""
            ).strip()

            if texto_shape:
                textos_slide.append(
                    texto_shape
                )

        if textos_slide:
            cabecalho = (
                f"SLIDE {numero}"
            )
            partes.append(cabecalho)
            tamanho_atual += len(cabecalho)

            for trecho in textos_slide:
                partes.append(trecho)
                tamanho_atual += len(trecho)

                if tamanho_atual >= MAX_TEXTO:
                    return "\n".join(
                        partes
                    )[:MAX_TEXTO]

    return "\n".join(
        partes
    )[:MAX_TEXTO]


def ler_conteudo_textual(
    arquivo: Path
) -> tuple[str, str]:

    leitores = {
        ".txt": ler_txt,
        ".docx": ler_docx,
        ".pdf": ler_pdf,
        ".xls": ler_xls,
        ".xlsx": ler_xlsx,
        ".pptx": ler_pptx,
    }

    leitor = leitores.get(
        arquivo.suffix.lower()
    )

    if leitor is None:
        return (
            "",
            "NAO_SUPORTADO_NESTA_VERSAO",
        )

    try:
        conteudo = leitor(
            arquivo
        )

        if not conteudo.strip():
            return (
                "",
                "LIDO_SEM_TEXTO_UTIL",
            )

        return (
            conteudo,
            "LIDO",
        )

    except Exception as erro:
        return (
            "",
            (
                "ERRO_LEITURA: "
                f"{type(erro).__name__}: "
                f"{erro}"
            ),
        )


# ============================================================
# TIPO DOCUMENTAL
# ============================================================

def identificar_tipo_documental(
    texto: str
) -> dict:

    texto_normalizado = normalizar(
        texto
    )

    candidatos = []

    for regra in REGRAS_TIPO_DOCUMENTAL:
        sinais_encontrados = [
            sinal
            for sinal in regra["sinais"]
            if normalizar(sinal)
            in texto_normalizado
        ]

        fortes_encontrados = [
            sinal
            for sinal in regra[
                "sinais_fortes"
            ]
            if normalizar(sinal)
            in texto_normalizado
        ]

        quantidade = len(
            sinais_encontrados
        )

        if (
            quantidade
            < regra["minimo_sinais"]
        ):
            continue

        proporcao = (
            quantidade
            / len(regra["sinais"])
        )

        candidatos.append({
            "tipo_documental":
                regra["tipo_documental"],

            "quantidade":
                quantidade,

            "proporcao":
                proporcao,

            "sinais":
                sinais_encontrados,

            "fortes":
                fortes_encontrados,
        })

    if not candidatos:
        return {
            "tipo_documental":
                "NAO_IDENTIFICADO",

            "confianca_tipo_documental":
                "BAIXA",

            "evidencias_tipo_documental":
                (
                    "Nenhum conjunto de sinais "
                    "foi suficiente."
                ),
        }

    candidatos.sort(
        key=lambda candidato: (
            len(candidato["fortes"]),
            candidato["proporcao"],
            candidato["quantidade"],
        ),
        reverse=True,
    )

    melhor = candidatos[0]

    if (
        melhor["fortes"]
        and melhor["proporcao"] >= 0.60
    ):
        confianca = "ALTA"

    elif melhor["proporcao"] >= 0.60:
        confianca = "MEDIA"

    else:
        confianca = "BAIXA"

    return {
        "tipo_documental":
            melhor["tipo_documental"],

        "confianca_tipo_documental":
            confianca,

        "evidencias_tipo_documental":
            ", ".join(
                melhor["sinais"]
            ),
    }


# ============================================================
# ASSUNTO
# ============================================================

def regra_encontrada(
    texto: str
):
    texto_normalizado = normalizar(
        texto
    )

    for regra in REGRAS_ASSUNTO:
        if all(
            normalizar(termo)
            in texto_normalizado
            for termo
            in regra["termos"]
        ):
            return regra

    return None


def analisar_assunto(
    arquivo: Path,
    conteudo: str,
    estado_leitura: str,
) -> dict:

    regra_nome = regra_encontrada(
        arquivo.stem
    )

    regra_conteudo = (
        regra_encontrada(conteudo)
        if conteudo
        else None
    )

    if (
        regra_nome
        and regra_conteudo
        and (
            regra_nome["assunto"]
            == regra_conteudo["assunto"]
        )
    ):
        return {
            "assunto":
                regra_nome["assunto"],

            "destino":
                regra_nome["destino"],

            "confianca":
                "ALTA",

            "fonte_evidencia":
                "NOME+CONTEUDO",

            "estado_leitura":
                estado_leitura,

            "motivo":
                (
                    f"{regra_nome['motivo']} "
                    "Nome e conteúdo fornecem "
                    "evidências concordantes."
                ),
        }

    if (
        regra_nome
        and regra_conteudo
        and (
            regra_nome["assunto"]
            != regra_conteudo["assunto"]
        )
    ):
        return {
            "assunto":
                "CONFLITO_DE_EVIDENCIAS",

            "destino":
                r"REVISAR\Conflitos",

            "confianca":
                "BAIXA",

            "fonte_evidencia":
                "NOME<>CONTEUDO",

            "estado_leitura":
                estado_leitura,

            "motivo":
                (
                    "O nome sugere "
                    f"{regra_nome['assunto']}, "
                    "mas o conteúdo sugere "
                    f"{regra_conteudo['assunto']}."
                ),
        }

    if regra_conteudo:
        return {
            "assunto":
                regra_conteudo["assunto"],

            "destino":
                regra_conteudo["destino"],

            "confianca":
                "ALTA",

            "fonte_evidencia":
                "CONTEUDO",

            "estado_leitura":
                estado_leitura,

            "motivo":
                (
                    f"{regra_conteudo['motivo']} "
                    "Classificação sustentada "
                    "pelo conteúdo."
                ),
        }

    if regra_nome:
        return {
            "assunto":
                regra_nome["assunto"],

            "destino":
                regra_nome["destino"],

            "confianca":
                "MEDIA",

            "fonte_evidencia":
                "NOME",

            "estado_leitura":
                estado_leitura,

            "motivo":
                (
                    f"{regra_nome['motivo']} "
                    "Classificação sustentada "
                    "apenas pelo nome."
                ),
        }

    return {
        "assunto":
            "NAO_IDENTIFICADO",

        "destino":
            r"REVISAR\Nao_Identificados",

        "confianca":
            "BAIXA",

        "fonte_evidencia":
            "NENHUMA",

        "estado_leitura":
            estado_leitura,

        "motivo":
            (
                "Não foi encontrada evidência "
                "suficiente para classificar "
                "o assunto."
            ),
    }


# ============================================================
# DESCRIÇÃO EM LINGUAGEM DE TRABALHO
# ============================================================

def gerar_descricao(
    arquivo: Path,
    tipo_documental: dict,
    analise: dict,
    conteudo: str,
    estado_leitura: str,
) -> str:

    tipo = tipo_documental[
        "tipo_documental"
    ]

    assunto = analise[
        "assunto"
    ]

    tamanho = arquivo.stat().st_size

    if tamanho == 0:
        return (
            "O arquivo está vazio. "
            "Vale baixá-lo novamente antes "
            "de decidir onde arquivá-lo."
        )

    if estado_leitura.startswith(
        "ERRO_LEITURA"
    ):
        if assunto != "NAO_IDENTIFICADO":
            return (
                f"O nome indica que este material está "
                f"relacionado a {rotulo(assunto)}. "
                "O arquivo parece estar incompleto ou "
                "corrompido; vale baixá-lo novamente "
                "antes de arquivá-lo."
            )

        return (
            "O arquivo parece estar incompleto ou "
            "corrompido. Vale baixá-lo novamente "
            "antes de arquivá-lo."
        )

    if estado_leitura == (
        "NAO_SUPORTADO_NESTA_VERSAO"
    ):
        if assunto != "NAO_IDENTIFICADO":
            return (
                f"{rotulo(assunto)} identificado pelo "
                "nome do arquivo."
            )

        if arquivo.suffix.lower() in {
            ".jpg", ".jpeg", ".png",
            ".gif", ".webp", ".bmp", ".svg"
        }:
            return (
                "Imagem recebida e pronta para revisão."
            )

        if arquivo.suffix.lower() in {
            ".zip", ".rar", ".7z", ".tar", ".gz"
        }:
            return (
                "Arquivo compactado recebido. "
                "O conteúdo interno não será aberto "
                "automaticamente."
            )

        if arquivo.suffix.lower() in {
            ".exe", ".msi"
        }:
            return (
                "Instalador recebido. "
                "Nenhuma execução será realizada "
                "pelo orquestrador."
            )

        return (
            "Arquivo recebido e pronto para revisão."
        )

    partes = []

    if tipo != "NAO_IDENTIFICADO":
        partes.append(
            rotulo(tipo) + "."
        )

    elif assunto != "NAO_IDENTIFICADO":
        partes.append(
            rotulo(assunto) + "."
        )

    if conteudo:
        trecho = limitar_texto(
            conteudo,
            420
        )

        if trecho:
            partes.append(
                trecho
            )

    if not partes:
        return (
            "Arquivo recebido. "
            "Ainda não há elementos suficientes "
            "para caracterizá-lo."
        )

    return limitar_texto(
        " ".join(partes),
        MAX_DESCRICAO
    )


# ============================================================
# PRÉ-VISUALIZAÇÃO DE IMAGEM
# ============================================================

def imagem_para_data_uri(
    arquivo: Path
) -> tuple[str, str]:

    tamanho = arquivo.stat().st_size

    if tamanho == 0:
        return (
            "",
            "A imagem está vazia."
        )

    if tamanho > MAX_PREVIEW_IMAGEM_BYTES:
        return (
            "",
            (
                "A imagem é muito grande para ser "
                "incorporada à pré-visualização deste painel."
            ),
        )

    try:
        mime_type, _ = mimetypes.guess_type(
            arquivo.name
        )

        if not mime_type:
            extensao = arquivo.suffix.lower()

            mapa_mime = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp",
                ".bmp": "image/bmp",
                ".svg": "image/svg+xml",
            }

            mime_type = mapa_mime.get(
                extensao,
                "application/octet-stream",
            )

        dados = arquivo.read_bytes()

        codificado = base64.b64encode(
            dados
        ).decode(
            "ascii"
        )

        data_uri = (
            f"data:{mime_type};base64,{codificado}"
        )

        return (
            data_uri,
            ""
        )

    except Exception as erro:
        return (
            "",
            (
                "Não foi possível preparar a imagem "
                "para visualização. "
                f"Detalhe técnico: {type(erro).__name__}."
            ),
        )


MAX_PREVIEW_MIDIA_BYTES = (
    40 * 1024 * 1024
)


def midia_para_data_uri(
    arquivo: Path
) -> tuple[str, str]:
    try:
        tamanho = arquivo.stat().st_size

        if tamanho == 0:
            return (
                "",
                "Este arquivo está vazio.",
            )

        if tamanho > MAX_PREVIEW_MIDIA_BYTES:
            return (
                "",
                (
                    "Este arquivo de mídia é grande demais "
                    "para ser incorporado nesta pré-visualização."
                ),
            )

        mime_type, _ = mimetypes.guess_type(
            arquivo.name
        )

        if not mime_type:
            mime_type = (
                "application/octet-stream"
            )

        dados = arquivo.read_bytes()

        codificado = base64.b64encode(
            dados
        ).decode("ascii")

        return (
            (
                f"data:{mime_type};base64,"
                f"{codificado}"
            ),
            "",
        )

    except Exception as erro:
        return (
            "",
            (
                "Não foi possível preparar "
                "esta mídia para visualização. "
                f"Detalhe técnico: "
                f"{type(erro).__name__}."
            ),
        )


# ============================================================
# PREVIEW
# ============================================================

def preparar_preview(
    arquivo: Path,
    conteudo: str,
    estado_leitura: str,
) -> dict:

    extensao = arquivo.suffix.lower()

    if extensao == ".pdf":
        return {
            "tipo": "pdf",
            "url": arquivo.resolve().as_uri(),
            "conteudo": "",
        }

    if extensao in {
        ".jpg", ".jpeg", ".png",
        ".gif", ".webp", ".bmp", ".svg"
    }:
        data_uri, erro = imagem_para_data_uri(
            arquivo
        )

        if data_uri:
            return {
                "tipo": "imagem",
                "url": data_uri,
                "conteudo": "",
            }

        return {
            "tipo": "mensagem",
            "url": "",
            "conteudo": erro,
        }

    if extensao in {
        ".mp3",
        ".wav",
        ".m4a",
        ".aac",
        ".ogg",
        ".flac",
    }:
        data_uri, erro = midia_para_data_uri(
            arquivo
        )

        if data_uri:
            return {
                "tipo": "audio",
                "url": data_uri,
                "conteudo": "",
            }

        return {
            "tipo": "mensagem",
            "url": "",
            "conteudo": erro,
        }

    if extensao in {
        ".mp4",
        ".m4v",
        ".webm",
        ".mov",
    }:
        data_uri, erro = midia_para_data_uri(
            arquivo
        )

        if data_uri:
            return {
                "tipo": "video",
                "url": data_uri,
                "conteudo": "",
            }

        return {
            "tipo": "mensagem",
            "url": "",
            "conteudo": erro,
        }

    if (
        extensao in {
            ".txt",
            ".docx",
            ".xls",
            ".xlsx",
            ".pptx",
        }
        and conteudo
    ):
        return {
            "tipo": "texto",
            "url": "",
            "conteudo": conteudo[
                :MAX_PREVIEW_TEXTO
            ],
        }

    if estado_leitura.startswith(
        "ERRO_LEITURA"
    ):
        return {
            "tipo": "mensagem",
            "url": "",
            "conteudo": (
                "Não foi possível preparar uma "
                "visualização deste arquivo. "
                "Ele pode estar vazio, incompleto "
                "ou corrompido."
            ),
        }

    return {
        "tipo": "mensagem",
        "url": "",
        "conteudo": (
            "Este tipo de arquivo não será aberto "
            "dentro do painel."
        ),
    }


# ============================================================
# DESTINO GOVERNADO PELO TERRITÓRIO DOCUMENTAL
#
# V0.11:
# - destino autorizado não é automaticamente destino adequado;
# - somente pastas declaradas no território podem ser sugeridas;
# - contexto associado precisa aparecer de forma explícita nas
#   evidências do arquivo;
# - nenhuma pasta é criada e nenhum arquivo é movido;
# - o destino legado é preservado apenas para rastreabilidade.
# ============================================================

def avaliar_destino_territorio(
    arquivo: Path,
    conteudo: str,
    tipo_documental: dict,
    analise: dict,
) -> dict:

    destinos_autorizados = [
        pasta
        for pasta in TERRITORIO_DOCUMENTAL
        if pasta.get("papel") == "DESTINO"
        and pasta.get(
            "pode_receber_arquivos",
            False,
        )
        and pasta.get("caminho")
    ]

    if not destinos_autorizados:
        return {
            "estado_destino":
                "SEM_DESTINO_SUFICIENTEMENTE_SEGURO",

            "destino_sugerido":
                "",

            "destino_caminho":
                "",

            "evidencias_destino":
                "Nenhum destino autorizado está disponível.",

            "motivo_destino":
                (
                    "O território documental não possui uma pasta "
                    "autorizada que possa receber este arquivo."
                ),
        }

    texto_evidencia = normalizar(
        " ".join([
            arquivo.stem,
            conteudo or "",
            rotulo(
                tipo_documental[
                    "tipo_documental"
                ]
            ),
            rotulo(
                analise["assunto"]
            ),
        ])
    )

    candidatos = []

    for pasta in destinos_autorizados:
        contextos = [
            str(contexto).strip()
            for contexto in pasta.get(
                "contextos_associados",
                [],
            )
            if str(contexto).strip()
        ]

        contextos_encontrados = [
            contexto
            for contexto in contextos
            if normalizar(contexto)
            and normalizar(contexto)
            in texto_evidencia
        ]

        if not contextos_encontrados:
            continue

        candidatos.append({
            "pasta": pasta,
            "contextos":
                contextos_encontrados,
        })

    if len(candidatos) == 1:
        candidato = candidatos[0]
        pasta = candidato["pasta"]

        nome = str(
            pasta.get(
                "nome",
                pasta["caminho"],
            )
        )

        return {
            "estado_destino":
                "DESTINO_EXISTENTE_SUGERIDO",

            "destino_sugerido":
                nome,

            "destino_caminho":
                str(pasta["caminho"]),

            "evidencias_destino":
                (
                    "Contexto associado encontrado: "
                    + ", ".join(
                        candidato["contextos"]
                    )
                ),

            "motivo_destino":
                (
                    f"A pasta '{nome}' pertence ao território "
                    "declarado e seu contexto associado aparece "
                    "explicitamente nas evidências do arquivo. "
                    "A sugestão ainda depende de decisão humana."
                ),
        }

    if len(candidatos) > 1:
        nomes = [
            str(
                candidato["pasta"].get(
                    "nome",
                    candidato["pasta"]["caminho"],
                )
            )
            for candidato in candidatos
        ]

        return {
            "estado_destino":
                "SEM_DESTINO_SUFICIENTEMENTE_SEGURO",

            "destino_sugerido":
                "",

            "destino_caminho":
                "",

            "evidencias_destino":
                (
                    "Mais de um destino apresentou contexto "
                    "compatível: "
                    + ", ".join(nomes)
                ),

            "motivo_destino":
                (
                    "Há mais de uma pasta plausível no território. "
                    "O Akira não escolherá entre elas sem nova "
                    "evidência ou decisão humana."
                ),
        }

    return {
        "estado_destino":
            "SEM_DESTINO_SUFICIENTEMENTE_SEGURO",

        "destino_sugerido":
            "",

        "destino_caminho":
            "",

        "evidencias_destino":
            (
                "Nenhum contexto associado aos destinos "
                "autorizados apareceu explicitamente nas "
                "evidências do arquivo."
            ),

        "motivo_destino":
            (
                "O território foi consultado, mas não há evidência "
                "suficiente para indicar uma pasta existente com "
                "segurança."
            ),
    }


# ============================================================
# ANÁLISE DO ARQUIVO
# ============================================================

def analisar_arquivo(
    arquivo: Path
) -> dict:

    estatisticas = arquivo.stat()

    tipo_tecnico = classificar_tipo(
        arquivo
    )

    data_modificacao = datetime.fromtimestamp(
        estatisticas.st_mtime
    )

    if tipo_tecnico == "IGNORAR":
        return {
            "arquivo": arquivo.name,
            "caminho": str(arquivo),
            "extensao": arquivo.suffix.lower(),
            "tipo_tecnico": tipo_tecnico,

            "tipo_arquivo":
                rotulo_tipo_arquivo(
                    tipo_tecnico,
                    arquivo.suffix,
                ),

            "tamanho":
                formatar_tamanho(
                    estatisticas.st_size
                ),

            "tamanho_bytes":
                estatisticas.st_size,

            "data_modificacao":
                data_modificacao.strftime(
                    "%d/%m/%Y %H:%M"
                ),

            "tipo_documental":
                "NAO_APLICAVEL",

            "confianca_tipo_documental":
                "NAO_APLICAVEL",

            "evidencias_tipo_documental":
                "Arquivo de sistema.",

            "assunto":
                "NAO_APLICAVEL",

            "confianca_assunto":
                "NAO_APLICAVEL",

            "fonte_evidencia":
                "REGRA_SISTEMA",

            "estado_leitura":
                "NAO_APLICAVEL",

            "destino_sugerido":
                "",

            "destino_caminho":
                "",

            "estado_destino":
                "NAO_APLICAVEL",

            "evidencias_destino":
                "Arquivo de sistema.",

            "motivo_destino":
                "Destino não se aplica a arquivo ignorado.",

            "destino_legado":
                "",

            "motivo":
                "Arquivo configurado para ser ignorado.",

            "descricao":
                "Arquivo de sistema.",

            "estado_ficha":
                "IGNORADO",

            "acao_fisica":
                "NENHUMA — IGNORADO",

            "preview":
                {
                    "tipo": "mensagem",
                    "url": "",
                    "conteudo":
                        "Arquivo de sistema.",
                },
        }

    conteudo, estado_leitura = (
        ler_conteudo_textual(
            arquivo
        )
    )

    texto_para_tipo = (
        conteudo
        if conteudo
        else arquivo.stem
    )

    tipo_documental = (
        identificar_tipo_documental(
            texto_para_tipo
        )
    )

    analise = analisar_assunto(
        arquivo=arquivo,
        conteudo=conteudo,
        estado_leitura=estado_leitura,
    )

    descricao = gerar_descricao(
        arquivo=arquivo,
        tipo_documental=tipo_documental,
        analise=analise,
        conteudo=conteudo,
        estado_leitura=estado_leitura,
    )

    preview = preparar_preview(
        arquivo=arquivo,
        conteudo=conteudo,
        estado_leitura=estado_leitura,
    )

    destino_territorio = avaliar_destino_territorio(
        arquivo=arquivo,
        conteudo=conteudo,
        tipo_documental=tipo_documental,
        analise=analise,
    )

    return {
        "arquivo":
            arquivo.name,

        "caminho":
            str(arquivo),

        "extensao":
            arquivo.suffix.lower(),

        "tipo_tecnico":
            tipo_tecnico,

        "tipo_arquivo":
            rotulo_tipo_arquivo(
                tipo_tecnico,
                arquivo.suffix,
            ),

        "tamanho":
            formatar_tamanho(
                estatisticas.st_size
            ),

        "tamanho_bytes":
            estatisticas.st_size,

        "data_modificacao":
            data_modificacao.strftime(
                "%d/%m/%Y %H:%M"
            ),

        "tipo_documental":
            tipo_documental[
                "tipo_documental"
            ],

        "confianca_tipo_documental":
            tipo_documental[
                "confianca_tipo_documental"
            ],

        "evidencias_tipo_documental":
            tipo_documental[
                "evidencias_tipo_documental"
            ],

        "assunto":
            analise["assunto"],

        "confianca_assunto":
            analise["confianca"],

        "fonte_evidencia":
            analise["fonte_evidencia"],

        "estado_leitura":
            estado_leitura,

        "destino_sugerido":
            destino_territorio[
                "destino_sugerido"
            ],

        "destino_caminho":
            destino_territorio[
                "destino_caminho"
            ],

        "estado_destino":
            destino_territorio[
                "estado_destino"
            ],

        "evidencias_destino":
            destino_territorio[
                "evidencias_destino"
            ],

        "motivo_destino":
            destino_territorio[
                "motivo_destino"
            ],

        "destino_legado":
            analise["destino"],

        "motivo":
            analise["motivo"],

        "descricao":
            descricao,

        "estado_ficha":
            "AGUARDANDO_DECISAO_HUMANA",

        "acao_fisica":
            "NENHUMA — DRY-RUN",

        "preview":
            preview,
    }


# ============================================================
# LOG
# ============================================================

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

    return LOG_FILE


def registrar_decisao(
    log_file: Path,
    registro: dict,
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
            datetime.now().strftime(
                "%d/%m/%Y %H:%M:%S"
            ),

            registro["arquivo"],
            registro["caminho"],
            registro["tipo_tecnico"],
            registro["tipo_arquivo"],
            registro["tipo_documental"],

            registro[
                "confianca_tipo_documental"
            ],

            registro[
                "evidencias_tipo_documental"
            ],

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


# ============================================================
# PAINEL
# ============================================================

def classe_confianca(
    confianca: str
) -> str:

    mapa = {
        "ALTA": "alta",
        "MEDIA": "media",
        "BAIXA": "baixa",
    }

    return mapa.get(
        confianca,
        "neutra"
    )


def contar_tipo(
    registros: list[dict],
    tipo: str
) -> int:

    return sum(
        1
        for registro in registros
        if (
            registro["tipo_tecnico"] == tipo
            and registro["estado_ficha"]
            != "IGNORADO"
        )
    )


def gerar_html_preview(
    registro: dict,
    indice: int,
) -> str:

    preview = registro["preview"]

    nome = escape(
        registro["arquivo"]
    )

    tipo = preview["tipo"]

    if tipo == "pdf":
        corpo = f"""
        <iframe
            class="preview-pdf"
            src="{escape(preview['url'])}"
            title="Visualização de {nome}"
        ></iframe>
        """

    elif tipo == "imagem":
        corpo = f"""
        <div class="preview-imagem-area">
            <img
                class="preview-imagem"
                src="{preview['url']}"
                alt="Visualização de {nome}"
            >
        </div>
        """

    elif tipo == "audio":
        corpo = f"""
        <div class="preview-midia-area">
            <audio
                class="preview-audio"
                controls
                preload="metadata"
                src="{preview['url']}"
            >
                Seu navegador não conseguiu reproduzir este áudio.
            </audio>
        </div>
        """

    elif tipo == "video":
        corpo = f"""
        <div class="preview-midia-area">
            <video
                class="preview-video"
                controls
                preload="metadata"
                src="{preview['url']}"
            >
                Seu navegador não conseguiu reproduzir este vídeo.
            </video>
        </div>
        """

    elif tipo == "texto":
        corpo = f"""
        <pre class="preview-texto">{
            escape(preview["conteudo"])
        }</pre>
        """

    else:
        corpo = f"""
        <div class="preview-mensagem">
            {escape(preview["conteudo"])}
        </div>
        """

    return f"""
    <div
        class="preview-template"
        id="preview-{indice}"
        hidden
    >
        {corpo}
    </div>
    """


def gerar_painel_html(
    registros: list[dict]
) -> Path:

    visiveis = [
        registro
        for registro in registros
        if registro["estado_ficha"] != "IGNORADO"
    ]

    fichas = []
    previews = []

    for indice, registro in enumerate(
        visiveis,
        start=1
    ):

        nome = escape(
            registro["arquivo"]
        )

        caminho = escape(
            registro["caminho"]
        )

        tipo_tecnico = escape(
            registro["tipo_tecnico"]
        )

        extensao = escape(
            registro["extensao"]
            .upper()
            .replace(".", "")
        )

        tamanho = escape(
            registro["tamanho"]
        )

        data_modificacao = escape(
            registro["data_modificacao"]
        )

        tipo_arquivo_interface = escape(
            registro["tipo_arquivo"]
        )

        tipo_documental_interface = escape(
            "A identificar"
            if registro["tipo_documental"] in {
                "NAO_IDENTIFICADO",
                "NAO_APLICAVEL",
            }
            else rotulo(
                registro["tipo_documental"]
            )
        )

        assunto_interface = escape(
            "A identificar"
            if registro["assunto"] in {
                "NAO_IDENTIFICADO",
                "NAO_APLICAVEL",
            }
            else rotulo(
                registro["assunto"]
            )
        )

        confianca_tipo = escape(
            registro[
                "confianca_tipo_documental"
            ]
        )

        descricao = escape(
            registro["descricao"]
        )

        destino = escape(
            registro["destino_sugerido"]
            or "A definir"
        )

        if (
            registro["estado_destino"]
            == "SEM_DESTINO_SUFICIENTEMENTE_SEGURO"
        ):
            estado_destino_interface = (
                "Aguardando definição"
            )

        elif (
            registro["estado_destino"]
            == "DESTINO_EXISTENTE_SUGERIDO"
        ):
            estado_destino_interface = (
                "Destino sugerido"
            )

        else:
            estado_destino_interface = (
                "Não se aplica"
            )

        estado_destino = escape(
            estado_destino_interface
        )

        evidencias_destino = escape(
            registro["evidencias_destino"]
        )

        motivo_destino = escape(
            registro["motivo_destino"]
        )

        destino_legado = escape(
            registro["destino_legado"]
            or "Nenhum"
        )

        evidencias = escape(
            registro[
                "evidencias_tipo_documental"
            ]
        )

        estado_leitura = escape(
            registro["estado_leitura"]
        )

        motivo = escape(
            registro["motivo"]
        )

        classe = classe_confianca(
            registro[
                "confianca_tipo_documental"
            ]
        )

        busca = escape(
            normalizar(
                " ".join([
                    registro["arquivo"],
                    registro["tipo_tecnico"],
                    registro["tipo_arquivo"],
                    rotulo(
                        registro[
                            "tipo_documental"
                        ]
                    ),
                    rotulo(
                        registro["assunto"]
                    ),
                    registro["descricao"],
                    registro["destino_sugerido"],
                    registro["estado_destino"],
                    registro["evidencias_destino"],
                ])
            )
        )

        problema = (
            registro["tamanho_bytes"] == 0
            or registro[
                "estado_leitura"
            ].startswith(
                "ERRO_LEITURA"
            )
        )

        estado_visual = (
            "Precisa de atenção"
            if problema
            else "Aguardando decisão"
        )

        classe_status = (
            "status problema"
            if problema
            else "status"
        )

        ficha = f"""
        <article
            class="ficha"
            data-busca="{busca}"
            data-tipo="{tipo_tecnico}"
        >

            <div class="ficha-topo">

                <div class="arquivo-area">

                    <div class="icone-arquivo">
                        {extensao or "ARQ"}
                    </div>

                    <div class="arquivo-texto">

                        <h2>
                            {nome}
                        </h2>

                        <div class="metadados">
                            {tipo_tecnico}
                            ·
                            {tamanho}
                            ·
                            {data_modificacao}
                        </div>

                        <div class="caminho">
                            {caminho}
                        </div>

                    </div>

                </div>


                <div class="acoes-topo">

                    <button
                        type="button"
                        class="visualizar"
                        data-preview="{indice}"
                        data-nome="{nome}"
                    >
                        Visualizar
                    </button>

                    <span class="{classe_status}">
                        {estado_visual}
                    </span>

                </div>

            </div>


            <div class="conteudo-ficha">

                <section class="coluna entendimento">

                    <h3>
                        O que chegou
                    </h3>

                    <div class="grade-entendimento">

                        <div class="campo">

                            <span>
                                Tipo de arquivo
                            </span>

                            <strong>
                                {tipo_arquivo_interface}
                            </strong>

                        </div>


                        <div class="campo">

                            <span>
                                Natureza
                            </span>

                            <strong>
                                {tipo_documental_interface}
                            </strong>

                        </div>


                        <div class="campo largura-total">

                            <span>
                                Tema
                            </span>

                            <strong>
                                {assunto_interface}
                            </strong>

                        </div>

                    </div>


                    <div class="descricao">

                        <span>
                            Em poucas palavras
                        </span>

                        <p>
                            {descricao}
                        </p>

                    </div>

                </section>


                <section class="coluna organizacao">

                    <h3>
                        Organização sugerida
                    </h3>

                    <div class="campo">

                        <span>
                            Pasta
                        </span>

                        <strong>
                            📁 {destino}
                        </strong>

                    </div>


                    <div class="campo">

                        <span>
                            Situação
                        </span>

                        <strong>
                            {estado_destino}
                        </strong>

                    </div>


                    <div class="campo">

                        <span>
                            Projeto
                        </span>

                        <strong>
                            Nenhum projeto vinculado
                        </strong>

                    </div>


                    <div class="nota">
                        {motivo_destino}
                    </div>

                </section>


                <section class="coluna detalhes">

                    <h3>
                        Detalhes
                    </h3>

                    <dl>

                        <div>
                            <dt>
                                Leitura
                            </dt>

                            <dd>
                                {estado_leitura}
                            </dd>
                        </div>


                        <div>
                            <dt>
                                Evidências
                            </dt>

                            <dd>
                                {evidencias}
                            </dd>
                        </div>


                        <div>
                            <dt>
                                Formato
                            </dt>

                            <dd>
                                {tipo_tecnico}
                                ({extensao or "-"})
                            </dd>
                        </div>


                        <div>
                            <dt>
                                Tamanho
                            </dt>

                            <dd>
                                {tamanho}
                            </dd>
                        </div>


                        <div>
                            <dt>
                                Modificação
                            </dt>

                            <dd>
                                {data_modificacao}
                            </dd>
                        </div>

                    </dl>


                    <details>

                        <summary>
                            Ver análise técnica
                        </summary>

                        <p>
                            <strong>Confiança interna:</strong>
                            {confianca_tipo}
                        </p>

                        <p>
                            {motivo}
                        </p>

                        <p>
                            <strong>Destino — evidências:</strong>
                            {evidencias_destino}
                        </p>

                        <p>
                            <strong>Sugestão legada preservada
                            para rastreabilidade:</strong>
                            {destino_legado}
                        </p>

                    </details>

                </section>

            </div>


            <section class="decisao">

                <h3>
                    O que você quer fazer?
                </h3>

                <div class="botoes">

                    <button
                        class="principal"
                        disabled
                    >
                        ✓ Arquivar aqui
                    </button>

                    <button disabled>
                        Escolher outra pasta
                    </button>

                    <button disabled>
                        Criar pasta
                    </button>

                    <button disabled>
                        Vincular a projeto
                    </button>

                    <button disabled>
                        Editar informações
                    </button>

                    <button disabled>
                        Deixar para depois
                    </button>

                    <button
                        class="lixeira"
                        disabled
                    >
                        Enviar para lixeira
                    </button>

                </div>

            </section>

        </article>
        """

        fichas.append(
            ficha
        )

        previews.append(
            gerar_html_preview(
                registro,
                indice
            )
        )

    total = len(
        visiveis
    )

    documentos = contar_tipo(
        visiveis,
        "DOCUMENTO"
    )

    imagens = contar_tipo(
        visiveis,
        "IMAGEM"
    )

    planilhas = contar_tipo(
        visiveis,
        "PLANILHA"
    )

    apresentacoes = contar_tipo(
        visiveis,
        "APRESENTACAO"
    )

    compactados = contar_tipo(
        visiveis,
        "ARQUIVO_COMPACTADO"
    )

    instaladores = contar_tipo(
        visiveis,
        "INSTALADOR"
    )

    outros = (
        total
        - documentos
        - imagens
        - planilhas
        - apresentacoes
        - compactados
        - instaladores
    )

    gerado_em = datetime.now().strftime(
        "%d/%m/%Y às %H:%M"
    )

    usuario_interface = escape(
        PERFIL.get(
            "usuario_windows",
            "Usuário atual",
        )
    )

    entrada_configurada = next(
        (
            pasta
            for pasta in PERFIL.get(
                "pastas_entrada",
                [],
            )
            if pasta.get("monitorar", True)
            and pasta.get("caminho")
        ),
        {},
    )

    entrada_nome_interface = escape(
        entrada_configurada.get(
            "nome",
            DOWNLOADS.name or "Entrada",
        )
    )

    entrada_caminho_interface = escape(
        str(
            entrada_configurada.get(
                "caminho",
                DOWNLOADS,
            )
        )
    )

    destinos_conhecidos = [
        pasta
        for pasta in TERRITORIO_DOCUMENTAL
        if pasta.get("papel") == "DESTINO"
        and pasta.get(
            "pode_receber_arquivos",
            False,
        )
    ]

    destinos_nomes = [
        escape(
            str(
                pasta.get(
                    "nome",
                    pasta.get(
                        "caminho",
                        "Destino",
                    ),
                )
            )
        )
        for pasta in destinos_conhecidos
    ]

    destinos_interface = (
        ", ".join(destinos_nomes)
        if destinos_nomes
        else "Nenhum destino cadastrado"
    )

    total_destinos = len(
        destinos_conhecidos
    )

    html = f"""
<!DOCTYPE html>

<html lang="pt-BR">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>
    Caixa de Entrada Documental
</title>

<style>

* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    font-family:
        Arial,
        Helvetica,
        sans-serif;
    background: #f5f7fa;
    color: #172033;
    line-height: 1.35;
}}

body.modal-aberto {{
    overflow: hidden;
}}

header {{
    height: 74px;
    background: #ffffff;
    border-bottom: 1px solid #dfe3e8;
    display: flex;
    align-items: center;
    padding: 0 20px;
}}

.cabecalho {{
    width: 100%;
    display: flex;
    justify-content: space-between;
    gap: 30px;
}}

.titulo-principal h1 {{
    margin: 0;
    font-size: 25px;
}}

.titulo-principal p {{
    margin: 3px 0 0;
    color: #667085;
    font-size: 14px;
}}

.modo {{
    text-align: right;
    font-size: 12px;
    color: #667085;
}}

.modo strong {{
    display: block;
    color: #344054;
}}

.contexto-perfil {{
    background: #f8fafc;
    border-bottom: 1px solid #dfe3e8;
    padding: 9px 20px;
    display: flex;
    flex-wrap: wrap;
    gap: 8px 18px;
    align-items: center;
    font-size: 12px;
    color: #475467;
}}

.contexto-perfil .item-perfil {{
    display: flex;
    gap: 5px;
    align-items: baseline;
    min-width: 0;
}}

.contexto-perfil .item-perfil span {{
    color: #667085;
}}

.contexto-perfil .item-perfil strong {{
    color: #344054;
    font-weight: 700;
    word-break: break-word;
}}

.contexto-perfil .caminho-perfil {{
    color: #98a2b3;
    font-weight: 400;
}}

.layout {{
    display: grid;
    grid-template-columns: 200px minmax(0, 1fr);
    min-height: calc(100vh - 74px);
}}

aside {{
    background: #ffffff;
    border-right: 1px solid #dfe3e8;
    padding: 18px 9px;
}}

aside h4 {{
    margin: 18px 8px 8px;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: .06em;
    color: #667085;
}}

.menu-item {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    min-height: 36px;
    padding: 7px 9px;
    border-radius: 7px;
    font-size: 14px;
    cursor: pointer;
}}

.menu-item:hover {{
    background: #f2f4f7;
}}

.menu-item.ativo {{
    background: #eef4ff;
    color: #155eef;
    font-weight: 700;
}}

.contagem {{
    min-width: 25px;
    text-align: center;
    background: #eef2f6;
    border-radius: 999px;
    padding: 2px 7px;
    font-size: 12px;
}}

.principal-area {{
    min-width: 0;
    padding: 16px 18px;
}}

.barra-superior {{
    display: grid;
    grid-template-columns: 1fr minmax(280px, 420px);
    gap: 18px;
    align-items: center;
    margin-bottom: 12px;
}}

.barra-superior h2 {{
    margin: 0;
    font-size: 20px;
}}

.barra-superior h2 span {{
    font-size: 13px;
    font-weight: 400;
    color: #667085;
    margin-left: 7px;
}}

.busca {{
    height: 38px;
    border: 1px solid #cfd5dd;
    border-radius: 9px;
    padding: 0 13px;
    font-size: 14px;
    background: #fff;
}}

.ficha {{
    background: #fff;
    border: 1px solid #d9dfe7;
    border-radius: 10px;
    margin-bottom: 11px;
    overflow: hidden;
}}

.ficha-topo {{
    padding: 10px 13px;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 14px;
    border-bottom: 1px solid #e7eaf0;
}}

.arquivo-area {{
    display: flex;
    gap: 11px;
    min-width: 0;
}}

.icone-arquivo {{
    min-width: 42px;
    height: 42px;
    background: #eef4ff;
    border: 1px solid #c7d7fe;
    border-radius: 7px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #155eef;
    font-size: 11px;
    font-weight: 800;
}}

.arquivo-texto {{
    min-width: 0;
}}

.arquivo-texto h2 {{
    margin: 0 0 2px;
    font-size: 16px;
    word-break: break-word;
}}

.metadados {{
    font-size: 12px;
    color: #667085;
}}

.caminho {{
    margin-top: 2px;
    font-size: 11px;
    color: #98a2b3;
    word-break: break-all;
}}

.acoes-topo {{
    display: flex;
    align-items: center;
    gap: 7px;
}}

.visualizar {{
    border: 1px solid #b7c5dd;
    background: #fff;
    color: #344054;
    border-radius: 6px;
    padding: 6px 10px;
    cursor: pointer;
    font-size: 11.5px;
}}

.visualizar:hover {{
    background: #f6f8fb;
}}

.status {{
    background: #fff4cc;
    border: 1px solid #f7dfa2;
    border-radius: 999px;
    padding: 4px 9px;
    font-size: 11px;
    color: #6d5200;
    white-space: nowrap;
}}

.status.problema {{
    background: #fee4e2;
    border-color: #fecdca;
    color: #b42318;
}}

.conteudo-ficha {{
    display: grid;
    grid-template-columns:
        minmax(360px, 1.25fr)
        minmax(230px, .72fr)
        minmax(280px, .88fr);
}}

.coluna {{
    padding: 9px 11px;
    min-width: 0;
}}

.coluna + .coluna {{
    border-left: 1px solid #e7eaf0;
}}

.coluna h3 {{
    font-size: 14px;
    margin: 0 0 7px;
}}

.grade-entendimento {{
    display: grid;
    grid-template-columns: 2fr .72fr;
    gap: 7px;
}}

.largura-total {{
    grid-column: 1 / -1;
}}

.campo {{
    background: #f7f8fa;
    border-radius: 6px;
    padding: 7px 9px;
}}

.campo span,
.descricao span {{
    display: block;
    font-size: 11px;
    color: #667085;
    margin-bottom: 2px;
}}

.campo strong {{
    font-size: 13px;
    word-break: break-word;
}}

.descricao {{
    margin-top: 7px;
    background: #f7f8fa;
    border-radius: 6px;
    padding: 7px 9px;
}}

.descricao p {{
    margin: 2px 0 0;
    font-size: 12.5px;
    line-height: 1.38;
}}

.confianca {{
    display: inline-block;
    border-radius: 5px;
    padding: 2px 6px;
}}

.alta {{
    background: #d1fadf;
    color: #05603a;
}}

.media {{
    background: #fff3c7;
    color: #7a4f01;
}}

.baixa {{
    background: #fee4e2;
    color: #b42318;
}}

.organizacao .campo {{
    margin-bottom: 7px;
}}

.nota {{
    background: #eef4ff;
    color: #175cd3;
    padding: 8px 9px;
    border-radius: 6px;
    font-size: 11.5px;
}}

dl {{
    margin: 0;
}}

dl > div {{
    display: grid;
    grid-template-columns: 105px 1fr;
    gap: 7px;
    padding: 4px 0;
    border-bottom: 1px solid #edf0f3;
    font-size: 11.5px;
}}

dt {{
    color: #667085;
}}

dd {{
    margin: 0;
    word-break: break-word;
}}

details {{
    margin-top: 7px;
    font-size: 11.5px;
}}

summary {{
    cursor: pointer;
    font-weight: 600;
}}

details p {{
    color: #667085;
}}

.decisao {{
    border-top: 1px solid #e7eaf0;
    padding: 7px 11px 9px;
}}

.decisao h3 {{
    font-size: 13px;
    margin: 0 0 6px;
}}

.botoes {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}}

button {{
    min-height: 31px;
    padding: 6px 10px;
    border: 1px solid #cfd5dd;
    border-radius: 6px;
    background: #fff;
    color: #667085;
    font-size: 11.5px;
}}

button:disabled {{
    opacity: .75;
    cursor: not-allowed;
}}

button.principal {{
    background: #155eef;
    border-color: #155eef;
    color: #fff;
}}

button.lixeira {{
    margin-left: auto;
    border-color: #fda29b;
    color: #d92d20;
}}

.sem-resultados {{
    display: none;
    padding: 35px;
    text-align: center;
    color: #667085;
}}

footer {{
    padding: 4px 0 18px;
    text-align: center;
    color: #98a2b3;
    font-size: 11px;
}}


/* ========================================================
   MODAL
   ======================================================== */

.modal {{
    position: fixed;
    inset: 0;
    background: rgba(20, 27, 40, .58);
    display: none;
    align-items: center;
    justify-content: center;
    padding: 22px;
    z-index: 9999;
}}

.modal.aberto {{
    display: flex;
}}

.modal-caixa {{
    width: min(1280px, 96vw);
    height: min(850px, 92vh);
    background: #fff;
    border-radius: 11px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}}

.modal-topo {{
    min-height: 54px;
    padding: 10px 14px;
    border-bottom: 1px solid #e3e6eb;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 15px;
}}

.modal-titulo-area {{
    min-width: 0;
}}

.modal-titulo {{
    margin: 0;
    font-size: 16px;
    word-break: break-word;
}}

.modal-subtitulo {{
    font-size: 11.5px;
    color: #667085;
}}

.modal-fechar {{
    border: 1px solid #cfd5dd;
    background: #fff;
    color: #344054;
    border-radius: 6px;
    min-width: 72px;
    cursor: pointer;
}}

.modal-conteudo {{
    flex: 1;
    min-height: 0;
    background: #eef1f5;
    padding: 12px;
}}

.modal-documento {{
    height: 100%;
    background: #fff;
    border: 1px solid #d8dde5;
    border-radius: 7px;
    overflow: auto;
}}

.preview-pdf {{
    display: block;
    width: 100%;
    height: 100%;
    border: 0;
}}

.preview-imagem-area {{
    min-height: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 22px;
}}

.preview-imagem {{
    display: block;
    max-width: 100%;
    max-height: 720px;
    width: auto;
    height: auto;
    object-fit: contain;
}}

.preview-midia-area {{
    min-height: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 28px;
}}

.preview-audio {{
    width: min(760px, 100%);
}}

.preview-video {{
    display: block;
    width: min(960px, 100%);
    max-height: 720px;
}}

.preview-texto {{
    margin: 0;
    padding: 28px 34px;
    white-space: pre-wrap;
    word-break: break-word;
    font-family:
        Arial,
        Helvetica,
        sans-serif;
    font-size: 14px;
    line-height: 1.55;
    color: #222;
}}

.preview-mensagem {{
    padding: 40px;
    font-size: 15px;
    color: #667085;
}}


@media (
    max-width: 1100px
) {{

    .layout {{
        grid-template-columns: 1fr;
    }}

    aside {{
        display: none;
    }}

    .conteudo-ficha {{
        grid-template-columns: 1fr 1fr;
    }}

    .detalhes {{
        grid-column: 1 / -1;
        border-left: 0 !important;
        border-top: 1px solid #e7eaf0;
    }}
}}


@media (
    max-width: 720px
) {{

    .principal-area {{
        padding: 10px;
    }}

    .barra-superior {{
        grid-template-columns: 1fr;
    }}

    .conteudo-ficha {{
        grid-template-columns: 1fr;
    }}

    .coluna + .coluna {{
        border-left: 0;
        border-top: 1px solid #e7eaf0;
    }}

    .detalhes {{
        grid-column: auto;
    }}

    .grade-entendimento {{
        grid-template-columns: 1fr;
    }}

    .largura-total {{
        grid-column: auto;
    }}

    button.lixeira {{
        margin-left: 0;
    }}

    .modo {{
        display: none;
    }}

    .acoes-topo {{
        flex-direction: column;
        align-items: flex-end;
    }}

    .modal {{
        padding: 6px;
    }}

    .modal-caixa {{
        width: 100%;
        height: 92vh;
    }}

    .preview-texto {{
        padding: 18px;
    }}
}}

</style>

</head>


<body>

<header>

    <div class="cabecalho">

        <div class="titulo-principal">

            <h1>
                Caixa de Entrada Documental
            </h1>

            <p>
                Arquivos recebidos e analisados.
                A decisão continua sendo sua.
            </p>

        </div>


        <div class="modo">

            <strong>
                V0.11.2 — inspeção multiformato
            </strong>

            Nenhum arquivo foi movido,
            alterado ou excluído.

            <br>

            Atualizado em {gerado_em}

        </div>

    </div>

</header>

<div class="contexto-perfil">

    <div class="item-perfil">
        <span>Perfil:</span>
        <strong>{usuario_interface}</strong>
    </div>

    <div class="item-perfil">
        <span>Entrada observada:</span>
        <strong>{entrada_nome_interface}</strong>
        <span class="caminho-perfil">
            {entrada_caminho_interface}
        </span>
    </div>

    <div class="item-perfil">
        <span>Destinos conhecidos:</span>
        <strong>{total_destinos}</strong>
        <span>{destinos_interface}</span>
    </div>

</div>


<div class="layout">


<aside>

    <div
        class="menu-item ativo filtro"
        data-filtro="TODOS"
    >
        <span>Todos</span>
        <span class="contagem">{total}</span>
    </div>

    <div
        class="menu-item filtro"
        data-filtro="DOCUMENTO"
    >
        <span>Documentos</span>
        <span class="contagem">{documentos}</span>
    </div>

    <div
        class="menu-item filtro"
        data-filtro="IMAGEM"
    >
        <span>Imagens</span>
        <span class="contagem">{imagens}</span>
    </div>

    <div
        class="menu-item filtro"
        data-filtro="PLANILHA"
    >
        <span>Planilhas</span>
        <span class="contagem">{planilhas}</span>
    </div>

    <div
        class="menu-item filtro"
        data-filtro="APRESENTACAO"
    >
        <span>Apresentações</span>
        <span class="contagem">{apresentacoes}</span>
    </div>

    <div
        class="menu-item filtro"
        data-filtro="ARQUIVO_COMPACTADO"
    >
        <span>Compactados</span>
        <span class="contagem">{compactados}</span>
    </div>

    <div
        class="menu-item filtro"
        data-filtro="INSTALADOR"
    >
        <span>Instaladores</span>
        <span class="contagem">{instaladores}</span>
    </div>

    <div
        class="menu-item filtro"
        data-filtro="OUTRO"
    >
        <span>Outros</span>
        <span class="contagem">{outros}</span>
    </div>


    <h4>
        Estado
    </h4>

    <div class="menu-item">
        <span>Aguardando decisão</span>
        <span class="contagem">{total}</span>
    </div>

</aside>


<section class="principal-area">


    <div class="barra-superior">

        <h2>
            Todos os arquivos

            <span>
                {total} arquivo(s)
            </span>
        </h2>


        <input
            id="busca"
            class="busca"
            type="search"
            placeholder="Buscar por nome, tema, tipo ou destino..."
        >

    </div>


    <main id="lista-fichas">

        {"".join(fichas)}

        <div
            id="sem-resultados"
            class="sem-resultados"
        >
            Nenhum arquivo corresponde
            aos filtros atuais.
        </div>

    </main>


    <footer>
        Caixa de Entrada Documental · V0.10
    </footer>

</section>

</div>


<div
    id="modal"
    class="modal"
    role="dialog"
    aria-modal="true"
    aria-labelledby="modal-titulo"
>

    <div class="modal-caixa">

        <div class="modal-topo">

            <div class="modal-titulo-area">

                <h2
                    id="modal-titulo"
                    class="modal-titulo"
                >
                    Visualizar arquivo
                </h2>

                <div class="modal-subtitulo">
                    Pré-visualização dentro do painel
                </div>

            </div>


            <button
                id="modal-fechar"
                class="modal-fechar"
                type="button"
            >
                Fechar
            </button>

        </div>


        <div class="modal-conteudo">

            <div
                id="modal-documento"
                class="modal-documento"
            ></div>

        </div>

    </div>

</div>


<div hidden>
    {"".join(previews)}
</div>


<script>

const busca =
    document.getElementById("busca");

const fichas = Array.from(
    document.querySelectorAll(".ficha")
);

const filtros = Array.from(
    document.querySelectorAll(".filtro")
);

const semResultados =
    document.getElementById(
        "sem-resultados"
    );

const modal =
    document.getElementById("modal");

const modalDocumento =
    document.getElementById(
        "modal-documento"
    );

const modalTitulo =
    document.getElementById(
        "modal-titulo"
    );

const modalFechar =
    document.getElementById(
        "modal-fechar"
    );

let filtroAtual = "TODOS";


function normalizarTexto(texto) {{
    return texto
        .normalize("NFD")
        .replace(
            /[\\u0300-\\u036f]/g,
            ""
        )
        .toLowerCase()
        .trim();
}}


function aplicarFiltros() {{

    const termo = normalizarTexto(
        busca.value
    );

    let visiveis = 0;

    fichas.forEach(
        ficha => {{

            const texto =
                normalizarTexto(
                    ficha.dataset.busca || ""
                );

            const tipo =
                ficha.dataset.tipo || "";

            const correspondeBusca =
                !termo ||
                texto.includes(termo);

            const correspondeTipo =
                filtroAtual === "TODOS" ||
                tipo === filtroAtual ||
                (
                    filtroAtual === "OUTRO" &&
                    ![
                        "DOCUMENTO",
                        "IMAGEM",
                        "PLANILHA",
                        "APRESENTACAO",
                        "ARQUIVO_COMPACTADO",
                        "INSTALADOR"
                    ].includes(tipo)
                );

            const mostrar =
                correspondeBusca &&
                correspondeTipo;

            ficha.style.display =
                mostrar
                ? ""
                : "none";

            if (mostrar) {{
                visiveis += 1;
            }}

        }}
    );

    semResultados.style.display =
        visiveis === 0
        ? "block"
        : "none";
}}


function abrirModal(
    indice,
    nome
) {{

    const template =
        document.getElementById(
            "preview-" + indice
        );

    if (!template) {{
        return;
    }}

    modalDocumento.innerHTML =
        template.innerHTML;

    modalTitulo.textContent =
        nome;

    modal.classList.add(
        "aberto"
    );

    document.body.classList.add(
        "modal-aberto"
    );

    modalFechar.focus();
}}


function fecharModal() {{

    modal.classList.remove(
        "aberto"
    );

    document.body.classList.remove(
        "modal-aberto"
    );

    modalDocumento.innerHTML = "";
}}


busca.addEventListener(
    "input",
    aplicarFiltros
);


filtros.forEach(
    filtro => {{

        filtro.addEventListener(
            "click",
            () => {{

                filtros.forEach(
                    item =>
                        item.classList.remove(
                            "ativo"
                        )
                );

                filtro.classList.add(
                    "ativo"
                );

                filtroAtual =
                    filtro.dataset.filtro;

                aplicarFiltros();

            }}
        );

    }}
);


document
    .querySelectorAll(
        ".visualizar"
    )
    .forEach(
        botao => {{

            botao.addEventListener(
                "click",
                () => {{

                    abrirModal(
                        botao.dataset.preview,
                        botao.dataset.nome
                    );

                }}
            );

        }}
    );


modalFechar.addEventListener(
    "click",
    fecharModal
);


modal.addEventListener(
    "click",
    evento => {{

        if (evento.target === modal) {{
            fecharModal();
        }}

    }}
);


document.addEventListener(
    "keydown",
    evento => {{

        if (
            evento.key === "Escape"
            &&
            modal.classList.contains(
                "aberto"
            )
        ) {{
            fecharModal();
        }}

    }}
);

</script>


</body>

</html>
"""

    PAINEL_FILE.write_text(
        html,
        encoding="utf-8",
    )

    return PAINEL_FILE


# ============================================================
# EXECUÇÃO
# ============================================================

def main():

    print(
        f"\nObservando pasta: "
        f"{DOWNLOADS}"
    )

    print(
        "MODO: DRY-RUN — "
        "nenhum arquivo será movido."
    )

    print(
        "Perfil Akira: "
        f"{PERFIL.get('usuario_windows', 'Usuário atual')}"
    )

    print(
        "Destinos conhecidos no território: "
        f"{len(TERRITORIO_DOCUMENTAL)}"
    )

    if not DOWNLOADS.exists():
        print(
            "A pasta Downloads "
            "não foi encontrada."
        )

        return

    log_file = preparar_log()

    print(
        f"Log: {log_file}"
    )

    registros = []

    arquivos = [
        item
        for item in DOWNLOADS.iterdir()
        if item.is_file()
    ]

    arquivos.sort(
        key=lambda item:
            item.stat().st_mtime,
        reverse=True,
    )

    for arquivo in arquivos:

        registro = analisar_arquivo(
            arquivo
        )

        registros.append(
            registro
        )

        registrar_decisao(
            log_file=log_file,
            registro=registro,
        )

        print(
            f"\nArquivo: "
            f"{registro['arquivo']}"
        )

        print(
            "Tipo técnico: "
            f"{registro['tipo_tecnico']}"
        )

        print(
            "Tipo de arquivo: "
            f"{registro['tipo_arquivo']}"
        )

        print(
            "Natureza: "
            f"{registro['tipo_documental']}"
        )

        print(
            "Assunto: "
            f"{registro['assunto']}"
        )

        print(
            "Estado do destino: "
            f"{registro['estado_destino']}"
        )

        print(
            "Destino sugerido: "
            f"{registro['destino_sugerido'] or 'NENHUM'}"
        )

        print(
            "Ação física: NENHUMA"
        )

    painel = gerar_painel_html(
        registros
    )

    print(
        "\nAnálise concluída."
    )

    print(
        f"Painel gerado em: "
        f"{painel}"
    )

    print(
        "Nenhum arquivo foi movido."
    )

    try:
        webbrowser.open(
            painel.resolve().as_uri()
        )

    except Exception:
        pass


if __name__ == "__main__":
    main()