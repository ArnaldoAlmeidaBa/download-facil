"""Módulo de regras do Orquestrador."""
from src.rules.normalizer import normalizar, limpar_texto, limitar_texto
from src.rules.classifiers import (
    REGRAS_TIPO_DOCUMENTAL,
    REGRAS_ASSUNTO,
    identificar_tipo_documental,
    regra_encontrada,
    analisar_assunto,
    gerar_descricao,
)
from src.rules.territory import avaliar_destino_territorio

__all__ = [
    "normalizar",
    "limpar_texto",
    "limitar_texto",
    "REGRAS_TIPO_DOCUMENTAL",
    "REGRAS_ASSUNTO",
    "identificar_tipo_documental",
    "regra_encontrada",
    "analisar_assunto",
    "gerar_descricao",
    "avaliar_destino_territorio",
]
