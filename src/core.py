"""Núcleo de orquestração do processamento de arquivos."""
import sys
import os
from pathlib import Path
from datetime import datetime
from threading import RLock
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
    AKIRA_DIR,
    BASE_DIR,
    LOG_DIR,
    LOG_FILE,
    PAINEL_FILE,
    PERFIL_FILE,
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
from src.document_access import (
    SNAPSHOT_CHANGED,
    SNAPSHOT_MISSING,
    SNAPSHOT_REPLACED,
    SNAPSHOT_VALID,
    autorizar_arquivo,
    classificar_arquivo_autorizado,
    inicializar_autorizacoes,
)

ESTADO_AGUARDANDO = "AGUARDANDO_DECISAO_HUMANA"
ESTADO_MOVIDO = "MOVIDO"
ESTADO_AUSENTE = "AUSENTE_OU_RENOMEADO"
ESTADO_ALTERADO = "ALTERADO_EXTERNAMENTE"
ESTADO_SUBSTITUIDO = "SUBSTITUIDO_EXTERNAMENTE"
ESTADO_MOVIDO_AUSENTE = "MOVIDO_AUSENTE"
ESTADO_MOVIDO_ALTERADO = "MOVIDO_ALTERADO"
ESTADO_MOVIDO_SUBSTITUIDO = "MOVIDO_SUBSTITUIDO"
ESTADO_MOVIDO_SEM_PREVIEW = "MOVIDO_SEM_PREVIEW"

_SESSION_LOCK = RLock()
_SESSION_RECORDS: list[dict] = []
_SESSION_PROFILE: dict | None = None
_SESSION_PANEL_FILE: Path | None = None
_SESSION_LOG_FILE: Path | None = None


def _caminho_comparacao(caminho: str | Path) -> str:
    return os.path.normcase(
        os.path.normpath(str(Path(caminho).resolve(strict=False)))
    )


def _caminhos_artefatos_aplicacao(
    log_file: Path,
    painel_file: Path,
) -> set[str]:
    candidatos = {
        PAINEL_FILE,
        painel_file,
        LOG_FILE,
        log_file,
        LOG_DIR / "movimentacoes.csv",
        PERFIL_FILE,
        AKIRA_DIR / "perfil.json",
        BASE_DIR / "perfil.json",
        BASE_DIR / "src" / "config.py",
        BASE_DIR / "Orquestrador.spec",
    }
    return {_caminho_comparacao(caminho) for caminho in candidatos}


def _contadores_operacionais_locked() -> dict[str, int]:
    visiveis = [
        registro
        for registro in _SESSION_RECORDS
        if registro.get("estado_ficha") != "IGNORADO"
    ]
    estados = [registro.get("estado_operacional", ESTADO_AGUARDANDO) for registro in visiveis]
    return {
        "total": len(visiveis),
        "aguardando": estados.count(ESTADO_AGUARDANDO),
        "movimentados": sum(
            estado == ESTADO_MOVIDO or estado.startswith("MOVIDO_")
            for estado in estados
        ),
        "inconsistentes": sum(
            estado in {
                ESTADO_AUSENTE,
                ESTADO_ALTERADO,
                ESTADO_SUBSTITUIDO,
                ESTADO_MOVIDO_AUSENTE,
                ESTADO_MOVIDO_ALTERADO,
                ESTADO_MOVIDO_SUBSTITUIDO,
                ESTADO_MOVIDO_SEM_PREVIEW,
            }
            for estado in estados
        ),
    }


def obter_contadores_operacionais() -> dict[str, int]:
    with _SESSION_LOCK:
        return _contadores_operacionais_locked()


def _gerar_painel_atualizado_locked() -> None:
    if _SESSION_PROFILE is None or _SESSION_PANEL_FILE is None:
        return
    gerar_painel_html(
        _SESSION_RECORDS,
        caminho_saida=_SESSION_PANEL_FILE,
        perfil=_SESSION_PROFILE,
    )


def atualizar_estado_externo(identificador: str, snapshot_estado: str) -> dict | None:
    mapa = {
        SNAPSHOT_MISSING: (ESTADO_AUSENTE, ESTADO_MOVIDO_AUSENTE),
        SNAPSHOT_CHANGED: (ESTADO_ALTERADO, ESTADO_MOVIDO_ALTERADO),
        SNAPSHOT_REPLACED: (ESTADO_SUBSTITUIDO, ESTADO_MOVIDO_SUBSTITUIDO),
    }
    estados = mapa.get(snapshot_estado)
    if not estados:
        return None

    with _SESSION_LOCK:
        for registro in _SESSION_RECORDS:
            if registro.get("id_arquivo") != identificador:
                continue
            esta_movido = registro.get("estado_operacional", "").startswith("MOVIDO")
            registro["estado_operacional"] = estados[1] if esta_movido else estados[0]
            _gerar_painel_atualizado_locked()
            return {
                "estado_operacional": registro["estado_operacional"],
                "contadores": _contadores_operacionais_locked(),
            }
    return None


def marcar_arquivo_movido(
    identificador: str,
    caminho_destino: Path,
    autorizacao_transferida: bool,
) -> dict | None:
    with _SESSION_LOCK:
        for registro in _SESSION_RECORDS:
            if registro.get("id_arquivo") != identificador:
                continue
            registro["caminho_origem"] = registro.get(
                "caminho_origem",
                registro["caminho"],
            )
            registro["caminho"] = str(caminho_destino)
            registro["arquivo"] = caminho_destino.name
            registro["estado_operacional"] = (
                ESTADO_MOVIDO if autorizacao_transferida else ESTADO_MOVIDO_SEM_PREVIEW
            )
            registro["acao_fisica"] = "MOVIDO"
            try:
                estatisticas = caminho_destino.stat()
            except OSError:
                registro["estado_operacional"] = ESTADO_MOVIDO_AUSENTE
                registro["preview"] = {
                    "tipo": "mensagem",
                    "url": "",
                    "conteudo": "O arquivo não está mais disponível no destino.",
                }
            else:
                registro["tamanho_bytes"] = estatisticas.st_size
                registro["tamanho"] = formatar_tamanho(estatisticas.st_size)
                registro["data_modificacao"] = datetime.fromtimestamp(
                    estatisticas.st_mtime
                ).strftime("%d/%m/%Y %H:%M")
                if not autorizacao_transferida:
                    registro["preview"] = {
                        "tipo": "mensagem",
                        "url": "",
                        "conteudo": "O arquivo foi movido; o preview requer reanálise.",
                    }
            _gerar_painel_atualizado_locked()
            return {
                "estado_operacional": registro["estado_operacional"],
                "contadores": _contadores_operacionais_locked(),
            }
    return None


def marcar_arquivo_restaurado(
    identificador: str | None,
    caminho_restaurado: Path,
    autorizacao_restaurada: bool,
    caminho_origem: Path | None = None,
) -> dict | None:
    with _SESSION_LOCK:
        registro = next(
            (
                item for item in _SESSION_RECORDS
                if identificador and item.get("id_arquivo") == identificador
            ),
            None,
        )
        if registro is None and caminho_origem is not None:
            caminho_original = _caminho_comparacao(caminho_origem)
            registro = next(
                (
                    item for item in _SESSION_RECORDS
                    if item.get("caminho_origem")
                    and _caminho_comparacao(item["caminho_origem"]) == caminho_original
                ),
                None,
            )
        if _SESSION_PROFILE is None:
            return None

        registro_atualizado = analisar_arquivo(
            caminho_restaurado,
            perfil=_SESSION_PROFILE,
        )
        registro_atualizado["estado_operacional"] = ESTADO_AGUARDANDO
        registro_atualizado["acao_fisica"] = "REVERSAO_CONCLUIDA"
        if caminho_origem is not None:
            registro_atualizado["caminho_origem"] = str(caminho_origem)
        if registro is None:
            _SESSION_RECORDS.append(registro_atualizado)
            registro = registro_atualizado
            if _SESSION_LOG_FILE is not None:
                registrar_decisao(_SESSION_LOG_FILE, registro_atualizado)
        else:
            registro.clear()
            registro.update(registro_atualizado)
        _gerar_painel_atualizado_locked()
        return {
            "arquivo_id": registro.get("id_arquivo"),
            "autorizacao_restaurada": autorizacao_restaurada,
            "estado_operacional": registro["estado_operacional"],
            "contadores": _contadores_operacionais_locked(),
        }


def reconciliar_estado_operacional() -> dict[str, int]:
    with _SESSION_LOCK:
        alterado = False
        for registro in _SESSION_RECORDS:
            identificador = registro.get("id_arquivo")
            if not identificador:
                continue
            estado_snapshot = classificar_arquivo_autorizado(identificador)
            estado_atual = registro.get("estado_operacional", ESTADO_AGUARDANDO)
            esta_movido = estado_atual == ESTADO_MOVIDO or estado_atual.startswith("MOVIDO_")
            if estado_snapshot == SNAPSHOT_VALID:
                estado_novo = ESTADO_MOVIDO if esta_movido else ESTADO_AGUARDANDO
            else:
                mapa = {
                    SNAPSHOT_MISSING: (ESTADO_AUSENTE, ESTADO_MOVIDO_AUSENTE),
                    SNAPSHOT_CHANGED: (ESTADO_ALTERADO, ESTADO_MOVIDO_ALTERADO),
                    SNAPSHOT_REPLACED: (ESTADO_SUBSTITUIDO, ESTADO_MOVIDO_SUBSTITUIDO),
                }
                estados = mapa.get(estado_snapshot)
                if not estados:
                    continue
                estado_novo = estados[1] if esta_movido else estados[0]
            if estado_novo != estado_atual:
                registro["estado_operacional"] = estado_novo
                alterado = True
        if alterado:
            _gerar_painel_atualizado_locked()
        return _contadores_operacionais_locked()


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
            "estado_operacional": "IGNORADO",
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
        "estado_operacional": ESTADO_AGUARDANDO,
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
    global _SESSION_RECORDS, _SESSION_PROFILE, _SESSION_PANEL_FILE, _SESSION_LOG_FILE

    if perfil is None:
        perfil = carregar_perfil()

    inicializar_autorizacoes(perfil)

    if log_file is None:
        log_file = LOG_FILE
    if painel_file is None:
        painel_file = PAINEL_FILE
    artefatos_aplicacao = _caminhos_artefatos_aplicacao(log_file, painel_file)

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

        arquivos = [
            item
            for item in pasta_entrada.iterdir()
            if item.is_file()
            and _caminho_comparacao(item) not in artefatos_aplicacao
        ]
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

    with _SESSION_LOCK:
        _SESSION_RECORDS = registros
        _SESSION_PROFILE = perfil
        _SESSION_PANEL_FILE = painel_file
        _SESSION_LOG_FILE = log_path
        painel_gerado = gerar_painel_html(
            registros,
            caminho_saida=painel_file,
            perfil=perfil,
        )
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
