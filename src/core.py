"""Núcleo de orquestração do processamento de arquivos."""
import sys
import os
from pathlib import Path
from datetime import datetime
import webbrowser

if sys.stdout is not None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr is not None:
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.config import (
    carregar_perfil,
    classificar_tipo,
    rotulo_tipo_arquivo,
    formatar_tamanho,
    LOG_FILE,
    PAINEL_FILE,
)
from src.readers import ler_conteudo_textual, preparar_preview
from src.rules import (
    identificar_tipo_documental,
    analisar_assunto,
    gerar_descricao,
    avaliar_destino_territorio,
)
from src.logging import preparar_log, registrar_decisao
from src.dashboard import gerar_painel_html
from src.document_access import autorizar_arquivo, inicializar_autorizacoes


def analisar_arquivo(arquivo: Path, perfil: dict = None) -> dict:
    """Realiza a análise técnica, documental e de território de um arquivo."""
    if perfil is None:
        perfil = carregar_perfil()

    territorio = perfil.get("territorio_documental", [])
    estatisticas = arquivo.stat()
    tipo_tecnico = classificar_tipo(arquivo)
    identificador_arquivo = autorizar_arquivo(arquivo)
    data_modificacao = datetime.fromtimestamp(estatisticas.st_mtime)

    if tipo_tecnico == "IGNORAR":
        return {
            "arquivo": arquivo.name,
            "caminho": str(arquivo),
            "extensao": arquivo.suffix.lower(),
            "id_arquivo": identificador_arquivo,
            "tipo_tecnico": tipo_tecnico,
            "tipo_arquivo": rotulo_tipo_arquivo(tipo_tecnico, arquivo.suffix),
            "tamanho": formatar_tamanho(estatisticas.st_size),
            "tamanho_bytes": estatisticas.st_size,
            "data_modificacao": data_modificacao.strftime("%d/%m/%Y %H:%M"),
            "tipo_documental": "NAO_APLICAVEL",
            "confianca_tipo_documental": "NAO_APLICAVEL",
            "evidencias_tipo_documental": "Arquivo de sistema.",
            "assunto": "NAO_APLICAVEL",
            "confianca_assunto": "NAO_APLICAVEL",
            "fonte_evidencia": "REGRA_SISTEMA",
            "estado_leitura": "NAO_APLICAVEL",
            "destino_sugerido": "",
            "destino_caminho": "",
            "estado_destino": "NAO_APLICAVEL",
            "evidencias_destino": "Arquivo de sistema.",
            "motivo_destino": "Destino não se aplica a arquivo ignorado.",
            "destino_legado": "",
            "motivo": "Arquivo configurado para ser ignorado.",
            "descricao": "Arquivo de sistema.",
            "estado_ficha": "IGNORADO",
            "acao_fisica": "NENHUMA — IGNORADO",
            "preview": {
                "tipo": "mensagem",
                "url": "",
                "conteudo": "Arquivo de sistema.",
            },
        }

    conteudo, estado_leitura = ler_conteudo_textual(arquivo)
    texto_para_tipo = conteudo if conteudo else arquivo.stem

    tipo_documental = identificar_tipo_documental(texto_para_tipo)
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
        territorio_documental=territorio,
    )

    return {
        "arquivo": arquivo.name,
        "caminho": str(arquivo),
        "extensao": arquivo.suffix.lower(),
        "id_arquivo": identificador_arquivo,
        "tipo_tecnico": tipo_tecnico,
        "tipo_arquivo": rotulo_tipo_arquivo(tipo_tecnico, arquivo.suffix),
        "tamanho": formatar_tamanho(estatisticas.st_size),
        "tamanho_bytes": estatisticas.st_size,
        "data_modificacao": data_modificacao.strftime("%d/%m/%Y %H:%M"),
        "tipo_documental": tipo_documental["tipo_documental"],
        "confianca_tipo_documental": tipo_documental["confianca_tipo_documental"],
        "evidencias_tipo_documental": tipo_documental["evidencias_tipo_documental"],
        "assunto": analise["assunto"],
        "confianca_assunto": analise["confianca"],
        "fonte_evidencia": analise["fonte_evidencia"],
        "estado_leitura": estado_leitura,
        "destino_sugerido": destino_territorio["destino_sugerido"],
        "destino_caminho": destino_territorio["destino_caminho"],
        "estado_destino": destino_territorio["estado_destino"],
        "evidencias_destino": destino_territorio["evidencias_destino"],
        "motivo_destino": destino_territorio["motivo_destino"],
        "destino_legado": analise["destino"],
        "motivo": analise["motivo"],
        "descricao": descricao,
        "estado_ficha": "AGUARDANDO_DECISAO_HUMANA",
        "acao_fisica": "NENHUMA — DRY-RUN",
        "preview": preview,
    }


def executar_orquestracao(
    perfil: dict = None,
    log_file: Path = None,
    painel_file: Path = None,
    abrir_navegador: bool = True,
) -> dict:
    """Executa a triagem completa em todas as pastas de entrada ativas."""
    if perfil is None:
        perfil = carregar_perfil()

    inicializar_autorizacoes(perfil)

    if log_file is None:
        log_file = LOG_FILE
    if painel_file is None:
        painel_file = PAINEL_FILE

    pastas_ativas = [
        Path(p["caminho"])
        for p in perfil.get("pastas_entrada", [])
        if p.get("monitorar", True) and p.get("caminho")
    ]

    print("\n" + "=" * 60)
    print("ORQUESTRADOR DE DOWNLOADS — INICIANDO VARREDURA")
    print("=" * 60)
    print(f"Perfil de Usuário: {perfil.get('usuario_windows', 'Padrão')}")
    print(f"Modo Operacional: DRY-RUN (Nenhum arquivo será movido)")
    print(f"Pastas monitoradas: {len(pastas_ativas)}")
    for pasta in pastas_ativas:
        print(f"  • {pasta} (Existe: {pasta.exists()})")

    log_path = preparar_log(log_file.parent, log_file)
    print(f"Arquivo de auditoria: {log_path}")

    registros = []
    for pasta_entrada in pastas_ativas:
        if not pasta_entrada.exists():
            print(f"\nAviso: Pasta de entrada não encontrada: {pasta_entrada}")
            continue

        arquivos = [item for item in pasta_entrada.iterdir() if item.is_file()]
        arquivos.sort(key=lambda item: item.stat().st_mtime, reverse=True)
        print(f"\nAnalisando {len(arquivos)} arquivo(s) em: {pasta_entrada}")

        for arquivo in arquivos:
            registro = analisar_arquivo(arquivo, perfil=perfil)
            registros.append(registro)
            registrar_decisao(log_file=log_path, registro=registro)

            print(
                f"[{registro['tipo_tecnico']}] {registro['arquivo']} -> "
                f"Natureza: {registro['tipo_documental']} | "
                f"Destino: {registro['destino_sugerido'] or 'A DEFINIR'}"
            )

    painel_gerado = gerar_painel_html(registros, caminho_saida=painel_file)
    print("\n" + "=" * 60)
    print(f"Análise concluída com sucesso!")
    print(f"Total de arquivos analisados: {len(registros)}")
    print(f"Painel gerado em: {painel_gerado}")
    print("Nenhum arquivo físico foi alterado ou movido.")
    print("=" * 60)

    if abrir_navegador:
        try:
            webbrowser.open(painel_gerado.resolve().as_uri())
        except Exception:
            pass

    return {
        "total_analisados": len(registros),
        "registros": registros,
        "log_file": log_path,
        "painel_file": painel_gerado,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Orquestrador de Downloads - Triagem e Governança de Arquivos"
    )
    parser.add_argument(
        "--apenas-analise",
        action="store_true",
        help="Executa apenas a varredura e fecha, sem iniciar o servidor interativo.",
    )
    parser.add_argument(
        "-s", "--servidor",
        action="store_true",
        default=True,
        help="Inicia o servidor local interativo (padrão: ativado).",
    )
    parser.add_argument(
        "-p", "--porta",
        type=int,
        default=8080,
        help="Porta para o servidor HTTP local (padrão: 8080).",
    )
    parser.add_argument(
        "--sem-navegador",
        action="store_true",
        help="Não abre o navegador automaticamente.",
    )

    args = parser.parse_args()
    servidor_ativo = args.servidor and not args.apenas_analise

    executar_orquestracao(abrir_navegador=(not args.sem_navegador and not servidor_ativo))

    if servidor_ativo:
        from src.server import iniciar_servidor
        iniciar_servidor(porta=args.porta, abrir_navegador=not args.sem_navegador)


if __name__ == "__main__":
    main()
