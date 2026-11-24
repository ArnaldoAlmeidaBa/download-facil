from pathlib import Path
import os

import src.core as core
from src.document_access import limpar_documentos_autorizados


def _executar_analise(tmp_path: Path, nome="amostra.txt"):
    entrada = tmp_path / "entrada"
    entrada.mkdir()
    arquivo = entrada / nome
    arquivo.write_text("Conteudo ficticio para análise.", encoding="utf-8")
    destino = tmp_path / "destino"
    destino.mkdir()
    perfil = {
        "usuario_windows": "Teste",
        "pastas_entrada": [{
            "caminho": str(entrada),
            "monitorar": True,
        }],
        "territorio_documental": [{
            "nome": "Revisao",
            "caminho": str(destino),
            "papel": "DESTINO",
            "pode_receber_arquivos": True,
            "contextos_associados": [],
        }],
    }
    resultado = core.executar_orquestracao(
        perfil=perfil,
        log_file=tmp_path / "logs" / "decisoes.csv",
        painel_file=tmp_path / "painel.html",
        abrir_navegador=False,
    )
    return arquivo, resultado


def test_reconciliar_arquivo_removido_alterado_e_substituido(tmp_path):
    limpar_documentos_autorizados()
    try:
        arquivo, resultado = _executar_analise(tmp_path)
        registro = resultado["registros"][0]

        arquivo.unlink()
        core.reconciliar_estado_operacional()
        assert registro["estado_operacional"] == core.ESTADO_AUSENTE

        arquivo.write_text("Conteudo recriado para testar renomeacao.", encoding="utf-8")
        core.executar_orquestracao(
            perfil=core._SESSION_PROFILE,
            log_file=tmp_path / "logs" / "decisoes.csv",
            painel_file=tmp_path / "painel.html",
            abrir_navegador=False,
        )
        registro = core._SESSION_RECORDS[0]
        arquivo.rename(arquivo.with_name("renomeado.txt"))
        core.reconciliar_estado_operacional()
        assert registro["estado_operacional"] == core.ESTADO_AUSENTE
        (arquivo.parent / "renomeado.txt").unlink()

        arquivo.write_text("Conteudo alterado externamente, com tamanho diferente.", encoding="utf-8")
        core.executar_orquestracao(
            perfil=core._SESSION_PROFILE,
            log_file=tmp_path / "logs" / "decisoes.csv",
            painel_file=tmp_path / "painel.html",
            abrir_navegador=False,
        )
        registro = core._SESSION_RECORDS[0]
        arquivo.write_text("Conteudo alterado externamente e novamente.", encoding="utf-8")
        core.reconciliar_estado_operacional()
        assert registro["estado_operacional"] == core.ESTADO_ALTERADO

        substituto = arquivo.with_suffix(".substituto")
        substituto.write_text(arquivo.read_text(encoding="utf-8"), encoding="utf-8")
        identificador_substituto = substituto.stat().st_ino
        assert identificador_substituto != arquivo.stat().st_ino
        os.replace(substituto, arquivo)
        assert arquivo.stat().st_ino == identificador_substituto
        core.reconciliar_estado_operacional()
        assert registro["estado_operacional"] == core.ESTADO_SUBSTITUIDO
    finally:
        limpar_documentos_autorizados()


def test_artefatos_exatos_sao_excluidos_e_nomes_semelhantes_permanecem(
    tmp_path, monkeypatch
):
    limpar_documentos_autorizados()
    app = tmp_path / "aplicacao"
    entrada = app
    entrada.mkdir()
    codigo = entrada / "src"
    codigo.mkdir()
    destino = tmp_path / "destino"
    destino.mkdir()
    painel = entrada / "painel.html"
    log = entrada / "decisoes.csv"
    movimentacoes = entrada / "movimentacoes.csv"
    perfil_aplicacao = entrada / "perfil.json"
    configuracao_aplicacao = codigo / "config.py"
    spec_aplicacao = entrada / "Orquestrador.spec"
    painel.write_text("<html>painel anterior</html>", encoding="utf-8")
    log.write_text("log anterior", encoding="utf-8")
    movimentacoes.write_text("historico anterior", encoding="utf-8")
    perfil_aplicacao.write_text('{"fixture": true}', encoding="utf-8")
    configuracao_aplicacao.write_text("APP_CONFIGURATION = True\n", encoding="utf-8")
    spec_aplicacao.write_text("EXE = []\n", encoding="utf-8")

    nomes_semelhantes = {
        "config.py",
        "painel.html",
        "decisoes.csv",
        "movimentacoes.csv",
        "perfil.json",
        "Orquestrador.spec",
        "documento-legitimo.txt",
    }
    (entrada / "config.py").write_text("USER_CONFIGURATION = True\n", encoding="utf-8")
    (codigo / "painel.html").write_text("<html>documento legitimo</html>", encoding="utf-8")
    (codigo / "decisoes.csv").write_text("arquivo;legitimo\n", encoding="utf-8")
    (codigo / "movimentacoes.csv").write_text("arquivo;legitimo\n", encoding="utf-8")
    (codigo / "perfil.json").write_text('{"documento": "legitimo"}', encoding="utf-8")
    (codigo / "Orquestrador.spec").write_text("FIXTURE = True\n", encoding="utf-8")
    (codigo / "documento-legitimo.txt").write_text("Conteudo ficticio.", encoding="utf-8")

    monkeypatch.setattr(core, "BASE_DIR", app)
    monkeypatch.setattr(core, "AKIRA_DIR", app)
    monkeypatch.setattr(core, "PERFIL_FILE", perfil_aplicacao)
    monkeypatch.setattr(core, "LOG_DIR", app)
    monkeypatch.setattr(core, "LOG_FILE", log)
    monkeypatch.setattr(core, "PAINEL_FILE", painel)
    perfil = {
        "usuario_windows": "Teste",
        "pastas_entrada": [
            {"caminho": str(entrada), "monitorar": True},
            {"caminho": str(codigo), "monitorar": True},
        ],
        "territorio_documental": [{
            "caminho": str(destino),
            "papel": "DESTINO",
            "pode_receber_arquivos": True,
        }],
    }
    artefatos = {
        "painel.html": painel,
        "decisoes.csv": log,
        "movimentacoes.csv": movimentacoes,
        "perfil.json": perfil_aplicacao,
        "config.py": configuracao_aplicacao,
        "Orquestrador.spec": spec_aplicacao,
    }
    caminhos_legitimos = {
        entrada / "config.py",
        codigo / "painel.html",
        codigo / "decisoes.csv",
        codigo / "movimentacoes.csv",
        codigo / "perfil.json",
        codigo / "Orquestrador.spec",
        codigo / "documento-legitimo.txt",
    }
    try:
        resultados = []
        for _ in range(2):
            resultado = core.executar_orquestracao(
                perfil=perfil,
                log_file=log,
                painel_file=painel,
                abrir_navegador=False,
            )
            nomes_analisados = {
                registro["arquivo"] for registro in resultado["registros"]
            }
            caminhos_analisados = {
                Path(registro["caminho"]).resolve()
                for registro in resultado["registros"]
            }
            assert nomes_analisados == nomes_semelhantes
            assert caminhos_analisados.isdisjoint(
                caminho.resolve() for caminho in artefatos.values()
            )
            assert caminhos_legitimos <= caminhos_analisados
            assert resultado["total_analisados"] == len(nomes_semelhantes)
            resultados.append(caminhos_analisados)

        assert all(caminho.is_file() for caminho in artefatos.values())
        assert painel.is_file()
        assert log.is_file()
        assert movimentacoes.is_file()
        print(f"Diretorio temporario: {tmp_path}")
        print(
            "Artefatos fisicamente presentes:",
            sorted(str(caminho.resolve()) for caminho in artefatos.values()),
        )
        print(
            "Caminhos identificados na analise inicial:",
            sorted(str(caminho) for caminho in resultados[0]),
        )
        print(
            "Caminhos identificados apos reanalise:",
            sorted(str(caminho) for caminho in resultados[1]),
        )
    finally:
        limpar_documentos_autorizados()
        core._SESSION_RECORDS = []
        core._SESSION_PROFILE = None
        core._SESSION_PANEL_FILE = None
        core._SESSION_LOG_FILE = None
