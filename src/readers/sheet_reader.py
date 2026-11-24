"""Extratores para planilhas (.xlsx e .xls)."""
from pathlib import Path
from openpyxl import load_workbook
import xlrd
from src.config import MAX_TEXTO


def ler_xlsx(arquivo: Path, limite: int = MAX_TEXTO) -> str:
    workbook = load_workbook(
        filename=arquivo,
        read_only=True,
        data_only=True,
    )
    partes = []
    tamanho_atual = 0

    try:
        for planilha in workbook.worksheets:
            cabecalho = f"PLANILHA: {planilha.title}"
            partes.append(cabecalho)
            tamanho_atual += len(cabecalho)

            for linha in planilha.iter_rows(values_only=True):
                valores = [
                    str(valor).strip()
                    for valor in linha
                    if valor is not None and str(valor).strip()
                ]
                if valores:
                    trecho = " | ".join(valores)
                    partes.append(trecho)
                    tamanho_atual += len(trecho)

                if tamanho_atual >= limite:
                    return "\n".join(partes)[:limite]
    finally:
        workbook.close()

    return "\n".join(partes)[:limite]


def ler_xls(arquivo: Path, limite: int = MAX_TEXTO) -> str:
    workbook = xlrd.open_workbook(str(arquivo))
    partes = []
    tamanho_atual = 0

    for planilha in workbook.sheets():
        cabecalho = f"PLANILHA: {planilha.name}"
        partes.append(cabecalho)
        tamanho_atual += len(cabecalho)

        limite_linhas = min(planilha.nrows, 250)
        limite_colunas = min(planilha.ncols, 40)

        for indice_linha in range(limite_linhas):
            valores = []
            for indice_coluna in range(limite_colunas):
                valor = planilha.cell_value(indice_linha, indice_coluna)
                if valor is not None and str(valor).strip():
                    valores.append(str(valor).strip())

            if valores:
                trecho = " | ".join(valores)
                partes.append(trecho)
                tamanho_atual += len(trecho)

            if tamanho_atual >= limite:
                return "\n".join(partes)[:limite]

    return "\n".join(partes)[:limite]
