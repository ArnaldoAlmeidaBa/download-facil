"""Módulo de validação de destinos governados pelo território documental."""
from pathlib import Path
from src.rules.normalizer import normalizar
from src.config import rotulo


def avaliar_destino_territorio(
    arquivo: Path,
    conteudo: str,
    tipo_documental: dict,
    analise: dict,
    territorio_documental: list = None,
) -> dict:
    if territorio_documental is None:
        territorio_documental = []

    destinos_autorizados = [
        pasta
        for pasta in territorio_documental
        if pasta.get("papel") == "DESTINO"
        and pasta.get("pode_receber_arquivos", False)
        and pasta.get("caminho")
    ]

    if not destinos_autorizados:
        return {
            "estado_destino": "SEM_DESTINO_SUFICIENTEMENTE_SEGURO",
            "destino_sugerido": "",
            "destino_caminho": "",
            "evidencias_destino": "Nenhum destino autorizado está disponível.",
            "motivo_destino": (
                "O território documental não possui uma pasta "
                "autorizada que possa receber este arquivo."
            ),
        }

    texto_evidencia = normalizar(
        " ".join([
            arquivo.stem,
            conteudo or "",
            rotulo(tipo_documental["tipo_documental"]),
            rotulo(analise["assunto"]),
        ])
    )

    candidatos = []
    for pasta in destinos_autorizados:
        contextos = [
            str(ctx).strip()
            for ctx in pasta.get("contextos_associados", [])
            if str(ctx).strip()
        ]
        contextos_encontrados = [
            ctx
            for ctx in contextos
            if normalizar(ctx) and normalizar(ctx) in texto_evidencia
        ]
        if not contextos_encontrados:
            continue

        candidatos.append({
            "pasta": pasta,
            "contextos": contextos_encontrados,
        })

    if len(candidatos) == 1:
        candidato = candidatos[0]
        pasta = candidato["pasta"]
        nome = str(pasta.get("nome", pasta["caminho"]))

        return {
            "estado_destino": "DESTINO_EXISTENTE_SUGERIDO",
            "destino_sugerido": nome,
            "destino_caminho": str(pasta["caminho"]),
            "evidencias_destino": (
                "Contexto associado encontrado: " + ", ".join(candidato["contextos"])
            ),
            "motivo_destino": (
                f"A pasta '{nome}' pertence ao território declarado e seu contexto associado "
                "aparece explicitamente nas evidências do arquivo. A sugestão ainda depende de decisão humana."
            ),
        }

    if len(candidatos) > 1:
        nomes = [
            str(c["pasta"].get("nome", c["pasta"]["caminho"]))
            for c in candidatos
        ]
        return {
            "estado_destino": "SEM_DESTINO_SUFICIENTEMENTE_SEGURO",
            "destino_sugerido": "",
            "destino_caminho": "",
            "evidencias_destino": (
                "Mais de um destino apresentou contexto compatível: " + ", ".join(nomes)
            ),
            "motivo_destino": (
                "Há mais de uma pasta plausível no território. "
                "O Akira não escolherá entre elas sem nova evidência ou decisão humana."
            ),
        }

    return {
        "estado_destino": "SEM_DESTINO_SUFICIENTEMENTE_SEGURO",
        "destino_sugerido": "",
        "destino_caminho": "",
        "evidencias_destino": (
            "Nenhum contexto associado aos destinos autorizados apareceu explicitamente nas "
            "evidências do arquivo."
        ),
        "motivo_destino": (
            "O território foi consultado, mas não há evidência suficiente para indicar uma pasta "
            "existente com segurança."
        ),
    }
