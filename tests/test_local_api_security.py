import json
import http.client
from http.server import ThreadingHTTPServer
from pathlib import Path
import os
import shutil
import subprocess
from threading import Thread
import urllib.error
import urllib.request

import pytest
from pypdf import PdfWriter

from src.actions.file_mover import limpar_historico
from src.actions.file_mover import obter_historico_movimentacoes
from src.document_access import (
    autorizar_arquivo,
    autorizar_documento,
    identificador_destino,
    inicializar_autorizacoes,
    limpar_documentos_autorizados,
    autorizar_destino,
)
from src.server import MAX_CORPO_HTTP_BYTES, OrquestradorRequestHandler


@pytest.fixture
def api(tmp_path, monkeypatch):
    import src.actions.file_mover as file_mover
    import src.core as core

    monkeypatch.setattr(file_mover, "LOG_DIR", tmp_path / "logs")
    core._SESSION_RECORDS = []
    core._SESSION_PROFILE = None
    core._SESSION_PANEL_FILE = None
    core._SESSION_LOG_FILE = None
    limpar_documentos_autorizados()
    limpar_historico()

    entrada = tmp_path / "downloads"
    entrada.mkdir()
    destino = tmp_path / "revisar"
    destino.mkdir()
    fora = tmp_path / "fora"
    fora.mkdir()
    perfil = {
        "pastas_entrada": [{"caminho": str(entrada), "monitorar": True}],
        "territorio_documental": [{
            "caminho": str(destino),
            "papel": "DESTINO",
            "pode_receber_arquivos": True,
        }],
    }
    inicializar_autorizacoes(perfil)

    arquivo = entrada / "documento.txt"
    arquivo.write_text("conteudo de teste", encoding="utf-8")
    arquivo_id = autorizar_arquivo(arquivo)
    destino_id = identificador_destino(destino)

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), OrquestradorRequestHandler)
    servidor.csrf_token = "csrf-fixture-token"
    thread = Thread(
        target=lambda: servidor.serve_forever(poll_interval=0.01),
        daemon=True,
    )
    thread.start()

    yield {
        "base": f"http://127.0.0.1:{servidor.server_port}",
        "port": servidor.server_port,
        "server": servidor,
        "thread": thread,
        "entrada": entrada,
        "destino": destino,
        "fora": fora,
        "perfil": perfil,
        "arquivo": arquivo,
        "arquivo_id": arquivo_id,
        "destino_id": destino_id,
        "token": servidor.csrf_token,
    }

    servidor.shutdown()
    servidor.server_close()
    thread.join(timeout=5)
    limpar_documentos_autorizados()
    limpar_historico()
    core._SESSION_RECORDS = []
    core._SESSION_PROFILE = None
    core._SESSION_PANEL_FILE = None
    core._SESSION_LOG_FILE = None


def requisitar(api, rota, body=None, headers=None, host=None):
    cabecalhos = dict(headers or {})
    if host:
        cabecalhos["Host"] = host
    data = body
    if isinstance(body, dict):
        data = json.dumps(body).encode("utf-8")
    requisicao = urllib.request.Request(
        api["base"] + rota,
        data=data,
        headers=cabecalhos,
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(requisicao, timeout=5) as resposta:
            return resposta.status, dict(resposta.headers), resposta.read()
    except urllib.error.HTTPError as erro:
        return erro.code, dict(erro.headers), erro.read()


def cabecalhos_validos(api):
    return {
        "Origin": api["base"],
        "Content-Type": "application/json",
        "X-CSRF-Token": api["token"],
    }


def payload_mover(api, arquivo_id=None, destino_id=None):
    return {
        "arquivo_id": arquivo_id or api["arquivo_id"],
        "destino_id": destino_id or api["destino_id"],
    }


def test_api_mover_arquivo_autorizado_e_oculta_caminhos(api):
    status, _, corpo = requisitar(
        api,
        "/api/mover",
        payload_mover(api),
        cabecalhos_validos(api),
    )
    resposta = json.loads(corpo)
    assert status == 200
    assert resposta["sucesso"] is True
    assert resposta["nome_final"] == "documento.txt"
    assert "origem" not in resposta
    assert str(api["entrada"]) not in corpo.decode("utf-8")
    assert not api["arquivo"].exists()
    assert (api["destino"] / "documento.txt").exists()


@pytest.mark.parametrize(
    "arquivo_id,destino_id,esperado",
    [
        ("A" * 43, None, 404),
        (None, "B" * 43, 403),
        ("../" + "A" * 40, None, 400),
    ],
)
def test_api_rejeita_origem_destino_e_identificador_nao_autorizados(
    api, arquivo_id, destino_id, esperado
):
    status, _, _ = requisitar(
        api,
        "/api/mover",
        payload_mover(api, arquivo_id, destino_id),
        cabecalhos_validos(api),
    )
    assert status == esperado
    assert api["arquivo"].exists()


def test_api_rejeita_host_origin_csrf_e_content_type_incorretos(api):
    payload = json.dumps(payload_mover(api)).encode("utf-8")
    headers = cabecalhos_validos(api)

    status, _, _ = requisitar(
        api, "/api/mover", payload, headers,
        host=f"malicioso.example:{api['port']}",
    )
    assert status == 403

    headers_origem_externa = dict(headers, Origin=f"http://malicioso.example:{api['port']}")
    status, _, _ = requisitar(api, "/api/mover", payload, headers_origem_externa)
    assert status == 403

    headers_sem_token = dict(headers)
    headers_sem_token.pop("X-CSRF-Token")
    status, _, _ = requisitar(api, "/api/mover", payload, headers_sem_token)
    assert status == 403

    headers_token_invalido = dict(headers, **{"X-CSRF-Token": "token-invalido"})
    status, _, _ = requisitar(api, "/api/mover", payload, headers_token_invalido)
    assert status == 403

    headers_tipo_invalido = dict(headers, **{"Content-Type": "text/plain"})
    status, _, _ = requisitar(api, "/api/mover", payload, headers_tipo_invalido)
    assert status == 415
    assert api["arquivo"].exists()


def test_api_rejeita_origin_ausente_e_corpo_excessivo(api):
    payload = json.dumps(payload_mover(api)).encode("utf-8")
    headers_sem_origem = cabecalhos_validos(api)
    headers_sem_origem.pop("Origin")
    status, _, _ = requisitar(api, "/api/mover", payload, headers_sem_origem)
    assert status == 403

    headers = cabecalhos_validos(api)
    body = b" " * (MAX_CORPO_HTTP_BYTES + 1)
    status, _, _ = requisitar(api, "/api/mover", body, headers)
    assert status == 413
    assert api["arquivo"].exists()


def test_api_reversao_legitima_e_status_sem_caminhos_absolutos(api):
    status, _, _ = requisitar(
        api, "/api/mover", payload_mover(api), cabecalhos_validos(api)
    )
    assert status == 200

    status, _, corpo = requisitar(
        api, "/api/desfazer", b"{}", cabecalhos_validos(api)
    )
    resposta = json.loads(corpo)
    assert status == 200
    assert resposta["sucesso"] is True
    assert str(api["entrada"]) not in corpo.decode("utf-8")
    assert api["arquivo"].exists()

    requisitar(api, "/api/mover", payload_mover(api), cabecalhos_validos(api))
    status, _, corpo = requisitar(api, "/api/status")
    assert status == 200
    assert str(api["entrada"]) not in corpo.decode("utf-8")
    assert str(api["destino"]) not in corpo.decode("utf-8")


def test_api_reanalise_legitima_e_painel_recebe_token_csrf(api, monkeypatch, tmp_path):
    import src.server as server_module

    chamada = []
    monkeypatch.setattr(
        server_module,
        "executar_orquestracao",
        lambda abrir_navegador=False: chamada.append(abrir_navegador)
        or {"total_analisados": 7},
    )
    status, _, corpo = requisitar(
        api, "/api/reanalisar", b"{}", cabecalhos_validos(api)
    )
    assert status == 200
    assert json.loads(corpo)["total"] == 7
    assert chamada == [False]

    painel = tmp_path / "painel.html"
    painel.write_text("<html><head></head><body></body></html>", encoding="utf-8")
    monkeypatch.setattr(server_module, "PAINEL_FILE", painel)
    status, _, corpo = requisitar(api, "/")
    assert status == 200
    assert f'name="csrf-token" content="{api["token"]}"'.encode() in corpo
    assert api["server"].server_address[0] == "127.0.0.1"
    api["server"].homologacao = True
    status, _, corpo = requisitar(api, "/")
    assert status == 200
    assert b"AMBIENTE DE HOMOLOGACAO - SOMENTE DADOS FICTICIOS" in corpo
    api["server"].homologacao = False


def test_movimentacao_e_reversao_sincronizam_painel_sem_reanalisar(
    api, monkeypatch, tmp_path
):
    import src.server as server_module
    import src.core as core

    painel = tmp_path / "painel.html"
    log = tmp_path / "logs" / "decisoes.csv"
    monkeypatch.setattr(server_module, "PAINEL_FILE", painel)
    resultado = core.executar_orquestracao(
        perfil=api["perfil"],
        log_file=log,
        painel_file=painel,
        abrir_navegador=False,
    )
    registro = resultado["registros"][0]
    destino_id = identificador_destino(api["destino"])

    status, _, corpo = requisitar(
        api,
        "/api/mover",
        payload_mover(api, registro["id_arquivo"], destino_id),
        cabecalhos_validos(api),
    )
    resposta = json.loads(corpo)
    assert status == 200
    assert resposta["estado_operacional"] == "MOVIDO"
    assert resposta["contadores"]["aguardando"] == 0
    assert resposta["contadores"]["movimentados"] == 1
    assert (api["destino"] / "documento.txt").exists()
    assert "Movimentado" in painel.read_text(encoding="utf-8")
    assert 'data-contagem-estado="AGUARDANDO_DECISAO_HUMANA">0' in painel.read_text(
        encoding="utf-8"
    )

    status, _, corpo = requisitar(
        api,
        "/api/desfazer",
        b"{}",
        cabecalhos_validos(api),
    )
    resposta = json.loads(corpo)
    assert status == 200
    assert resposta["estado_operacional"] == "AGUARDANDO_DECISAO_HUMANA"
    assert resposta["contadores"]["aguardando"] == 1
    assert api["arquivo"].exists()
    assert not (api["destino"] / "documento.txt").exists()
    assert "Aguardando decisão" in painel.read_text(encoding="utf-8")


def test_reversao_falha_preserva_historico_e_nao_sobrescreve(api):
    status, _, _ = requisitar(
        api, "/api/mover", payload_mover(api), cabecalhos_validos(api)
    )
    assert status == 200
    caminho_movido = api["destino"] / "documento.txt"
    caminho_movido.write_text("conteudo alterado", encoding="utf-8")

    status, _, corpo = requisitar(
        api, "/api/desfazer", b"{}", cabecalhos_validos(api)
    )
    assert status == 409
    resposta = json.loads(corpo)
    assert "histórico foi preservado" in resposta["erro"]
    assert obter_historico_movimentacoes()
    assert caminho_movido.exists()
    assert not api["arquivo"].exists()


def test_reanalise_regenera_fichas_com_arquivos_atuais(api, monkeypatch, tmp_path):
    import src.server as server_module
    import src.core as core

    painel = tmp_path / "painel-reanalise.html"
    monkeypatch.setattr(server_module, "PAINEL_FILE", painel)
    monkeypatch.setattr(
        server_module,
        "executar_orquestracao",
        lambda abrir_navegador=False: core.executar_orquestracao(
            perfil=api["perfil"],
            log_file=tmp_path / "logs" / "decisoes.csv",
            painel_file=painel,
            abrir_navegador=abrir_navegador,
        ),
    )
    resultado = core.executar_orquestracao(
        perfil=api["perfil"],
        log_file=tmp_path / "logs" / "decisoes.csv",
        painel_file=painel,
        abrir_navegador=False,
    )
    assert resultado["total_analisados"] == 1

    api["arquivo"].unlink()
    (api["entrada"] / "novo.txt").write_text("novo documento", encoding="utf-8")
    status, _, corpo = requisitar(
        api, "/api/reanalisar", b"{}", cabecalhos_validos(api)
    )
    assert status == 200
    assert json.loads(corpo)["total"] == 1
    assert "novo.txt" in painel.read_text(encoding="utf-8")
    assert "documento.txt" not in painel.read_text(encoding="utf-8")


def test_api_pdf_autorizado_preserva_preview_e_rejeita_id_invalido(api):
    arquivo_pdf = api["entrada"] / "relatorio.pdf"
    escritor = PdfWriter()
    escritor.add_blank_page(width=200, height=200)
    with arquivo_pdf.open("wb") as arquivo:
        escritor.write(arquivo)
    documento_id = autorizar_documento(arquivo_pdf)
    assert documento_id

    status, headers, corpo = requisitar(api, f"/api/documento/{documento_id}")
    assert status == 200
    assert headers["Content-Type"] == "application/pdf"
    assert corpo.startswith(b"%PDF")

    status, _, _ = requisitar(api, "/api/documento/../../Windows/win.ini")
    assert status == 404


def test_arquivo_modificado_apos_analise_nao_e_movido(api):
    api["arquivo"].write_text("conteudo alterado com tamanho diferente", encoding="utf-8")
    status, _, _ = requisitar(
        api,
        "/api/mover",
        payload_mover(api),
        cabecalhos_validos(api),
    )
    assert status == 409
    assert api["arquivo"].exists()
    assert not (api["destino"] / "documento.txt").exists()


def test_arquivo_alterado_atualiza_estado_e_bloqueia_movimentacao(
    api, monkeypatch, tmp_path
):
    import src.server as server_module
    import src.core as core

    painel = tmp_path / "painel-alterado.html"
    monkeypatch.setattr(server_module, "PAINEL_FILE", painel)
    core.executar_orquestracao(
        perfil=api["perfil"],
        log_file=tmp_path / "logs" / "decisoes.csv",
        painel_file=painel,
        abrir_navegador=False,
    )
    api["arquivo"].write_text("conteudo externo modificado", encoding="utf-8")

    registro = core._SESSION_RECORDS[0]
    status, _, corpo = requisitar(
        api,
        "/api/mover",
        payload_mover(api, registro["id_arquivo"], identificador_destino(api["destino"])),
        cabecalhos_validos(api),
    )
    resposta = json.loads(corpo)
    assert status == 409
    assert resposta["estado_operacional"] == "ALTERADO_EXTERNAMENTE"
    assert resposta["contadores"]["aguardando"] == 0
    assert "Alterado externamente" in painel.read_text(encoding="utf-8")
    assert api["arquivo"].exists()
    assert not (api["destino"] / "documento.txt").exists()


def test_autorizacao_recusa_caminhos_fora_da_raiz_e_junctions(api):
    arquivo_externo = api["fora"] / "privado.txt"
    arquivo_externo.write_text("fora da entrada", encoding="utf-8")
    assert autorizar_arquivo(arquivo_externo) is None

    if os.name != "nt":
        pytest.skip("Teste de junction disponível somente no Windows.")
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        pytest.skip("PowerShell não está disponível para criar junction de fixture.")

    junction_entrada = api["entrada"] / "atalho"
    junction_destino = api["destino"]
    destino_original = api["destino"].with_name("revisar-original")
    junction_destino.rename(destino_original)

    def criar_junction(link: Path, target: Path):
        quote = lambda value: "'" + str(value).replace("'", "''") + "'"
        script = (
            "New-Item -ItemType Junction -Path "
            + quote(link)
            + " -Target "
            + quote(target)
            + " | Out-Null"
        )
        return subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=10,
        )

    try:
        entrada_resultado = criar_junction(junction_entrada, api["fora"])
        if entrada_resultado.returncode != 0:
            pytest.skip("Não foi possível criar junction temporária de entrada.")
        (api["fora"] / "privado.txt").write_text("fora da entrada", encoding="utf-8")
        assert autorizar_arquivo(junction_entrada / "privado.txt") is None

        destino_resultado = criar_junction(junction_destino, api["fora"])
        if destino_resultado.returncode != 0:
            pytest.skip("Não foi possível criar junction temporária de destino.")
        assert autorizar_destino(api["destino_id"]) is None
    finally:
        if junction_entrada.exists():
            junction_entrada.rmdir()
        if junction_destino.exists():
            junction_destino.rmdir()
        if destino_original.exists():
            destino_original.rename(junction_destino)


def test_identificadores_renderizados_nao_expoem_caminhos_de_acao(api, tmp_path):
    from src.core import analisar_arquivo
    from src.dashboard.generator import gerar_painel_html

    registro = analisar_arquivo(api["arquivo"], perfil=api["perfil"])
    registro["destino_caminho"] = str(api["destino"])
    saida = tmp_path / "painel-fixture.html"
    gerar_painel_html([registro], caminho_saida=saida, perfil=api["perfil"])
    painel = saida.read_text(encoding="utf-8")
    assert f'data-arquivo-id="{registro["id_arquivo"]}"' in painel
    assert f'data-destino-id="{api["destino_id"]}"' in painel
    assert "data-origem=" not in painel
    assert "data-destino=" not in painel


def test_api_rejeita_json_malformado_e_campos_extra(api):
    headers = cabecalhos_validos(api)
    status, _, _ = requisitar(api, "/api/mover", b"{", headers)
    assert status == 400

    payload = payload_mover(api)
    payload["origem"] = str(api["arquivo"])
    status, _, _ = requisitar(api, "/api/mover", payload, headers)
    assert status == 400
    assert api["arquivo"].exists()


def test_api_exige_content_length(api):
    conexao = http.client.HTTPConnection("127.0.0.1", api["port"], timeout=5)
    conexao.putrequest("POST", "/api/mover", skip_host=True)
    conexao.putheader("Host", f"127.0.0.1:{api['port']}")
    conexao.putheader("Origin", api["base"])
    conexao.putheader("Content-Type", "application/json")
    conexao.putheader("X-CSRF-Token", api["token"])
    conexao.endheaders()
    resposta = conexao.getresponse()
    assert resposta.status == 411
    resposta.read()
    conexao.close()


@pytest.mark.parametrize(
    "nome,primeiro,segundo,esperado",
    [
        ("Host", "127.0.0.1:{port}", "malicioso.example:{port}", 403),
        ("Origin", "{base}", "http://malicioso.example:{port}", 403),
        ("Content-Type", "application/json", "text/plain", 415),
        ("X-CSRF-Token", "{token}", "token-invalido", 403),
    ],
)
def test_api_rejeita_cabecalhos_de_seguranca_duplicados(
    api, nome, primeiro, segundo, esperado
):
    valores = {
        "port": api["port"],
        "base": api["base"],
        "token": api["token"],
    }
    conexao = http.client.HTTPConnection("127.0.0.1", api["port"], timeout=5)
    conexao.putrequest("POST", "/api/mover", skip_host=True)
    conexao.putheader("Host", f"127.0.0.1:{api['port']}")
    conexao.putheader("Origin", api["base"])
    conexao.putheader("Content-Type", "application/json")
    conexao.putheader("X-CSRF-Token", api["token"])
    conexao.putheader(nome, primeiro.format(**valores))
    conexao.putheader(nome, segundo.format(**valores))
    corpo = json.dumps(payload_mover(api)).encode("utf-8")
    conexao.putheader("Content-Length", str(len(corpo)))
    conexao.endheaders(corpo)
    resposta = conexao.getresponse()
    assert resposta.status == esperado
    resposta.read()
    conexao.close()
    assert api["arquivo"].exists()
