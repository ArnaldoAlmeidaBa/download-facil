"""Módulo de regras de tipo documental, assunto e geração de descrição."""
from pathlib import Path
from src.rules.normalizer import normalizar, limitar_texto
from src.config import rotulo, MAX_DESCRICAO

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


def identificar_tipo_documental(texto: str) -> dict:
    texto_normalizado = normalizar(texto)
    candidatos = []

    for regra in REGRAS_TIPO_DOCUMENTAL:
        sinais_encontrados = [
            sinal
            for sinal in regra["sinais"]
            if normalizar(sinal) in texto_normalizado
        ]
        fortes_encontrados = [
            sinal
            for sinal in regra["sinais_fortes"]
            if normalizar(sinal) in texto_normalizado
        ]
        quantidade = len(sinais_encontrados)

        if quantidade < regra["minimo_sinais"]:
            continue

        proporcao = quantidade / len(regra["sinais"])
        candidatos.append({
            "tipo_documental": regra["tipo_documental"],
            "quantidade": quantidade,
            "proporcao": proporcao,
            "sinais": sinais_encontrados,
            "fortes": fortes_encontrados,
        })

    if not candidatos:
        return {
            "tipo_documental": "NAO_IDENTIFICADO",
            "confianca_tipo_documental": "BAIXA",
            "evidencias_tipo_documental": "Nenhum conjunto de sinais foi suficiente.",
        }

    candidatos.sort(
        key=lambda c: (
            len(c["fortes"]),
            c["proporcao"],
            c["quantidade"],
        ),
        reverse=True,
    )
    melhor = candidatos[0]

    if melhor["fortes"] and melhor["proporcao"] >= 0.60:
        confianca = "ALTA"
    elif melhor["proporcao"] >= 0.60:
        confianca = "MEDIA"
    else:
        confianca = "BAIXA"

    return {
        "tipo_documental": melhor["tipo_documental"],
        "confianca_tipo_documental": confianca,
        "evidencias_tipo_documental": ", ".join(melhor["sinais"]),
    }


def regra_encontrada(texto: str):
    texto_normalizado = normalizar(texto)
    for regra in REGRAS_ASSUNTO:
        if all(
            normalizar(termo) in texto_normalizado
            for termo in regra["termos"]
        ):
            return regra
    return None


def analisar_assunto(
    arquivo: Path,
    conteudo: str,
    estado_leitura: str,
) -> dict:
    regra_nome = regra_encontrada(arquivo.stem)
    regra_conteudo = regra_encontrada(conteudo) if conteudo else None

    if (
        regra_nome
        and regra_conteudo
        and (regra_nome["assunto"] == regra_conteudo["assunto"])
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
        and (regra_nome["assunto"] != regra_conteudo["assunto"])
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
                "Classificação sustentada pelo conteúdo."
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
                "Classificação sustentada apenas pelo nome."
            ),
        }

    return {
        "assunto": "NAO_IDENTIFICADO",
        "destino": r"REVISAR\Nao_Identificados",
        "confianca": "BAIXA",
        "fonte_evidencia": "NENHUMA",
        "estado_leitura": estado_leitura,
        "motivo": "Não foi encontrada evidência suficiente para classificar o assunto.",
    }


def gerar_descricao(
    arquivo: Path,
    tipo_documental: dict,
    analise: dict,
    conteudo: str,
    estado_leitura: str,
) -> str:
    tipo = tipo_documental["tipo_documental"]
    assunto = analise["assunto"]
    tamanho = arquivo.stat().st_size

    if tamanho == 0:
        return (
            "O arquivo está vazio. "
            "Vale baixá-lo novamente antes de decidir onde arquivá-lo."
        )

    if estado_leitura.startswith("ERRO_LEITURA"):
        if assunto != "NAO_IDENTIFICADO":
            return (
                f"O nome indica que este material está relacionado a {rotulo(assunto)}. "
                "O arquivo parece estar incompleto ou corrompido; vale baixá-lo novamente "
                "antes de arquivá-lo."
            )
        return (
            "O arquivo parece estar incompleto ou corrompido. "
            "Vale baixá-lo novamente antes de arquivá-lo."
        )

    if estado_leitura == "NAO_SUPORTADO_NESTA_VERSAO":
        if assunto != "NAO_IDENTIFICADO":
            return f"{rotulo(assunto)} identificado pelo nome do arquivo."
        ext = arquivo.suffix.lower()
        if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}:
            return "Imagem recebida e pronta para revisão."
        if ext in {".zip", ".rar", ".7z", ".tar", ".gz"}:
            return (
                "Arquivo compactado recebido. "
                "O conteúdo interno não será aberto automaticamente."
            )
        if ext in {".exe", ".msi"}:
            return (
                "Instalador recebido. "
                "Nenhuma execução será realizada pelo orquestrador."
            )
        return "Arquivo recebido e pronto para revisão."

    partes = []
    if tipo != "NAO_IDENTIFICADO":
        partes.append(rotulo(tipo) + ".")
    elif assunto != "NAO_IDENTIFICADO":
        partes.append(rotulo(assunto) + ".")

    if conteudo:
        trecho = limitar_texto(conteudo, 420)
        if trecho:
            partes.append(trecho)

    if not partes:
        return (
            "Arquivo recebido. "
            "Ainda não há elementos suficientes para caracterizá-lo."
        )

    return limitar_texto(" ".join(partes), MAX_DESCRICAO)
