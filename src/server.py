"""Servidor local HTTP para o painel interativo do Orquestrador."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import hmac
import json
import re
import secrets
import webbrowser
from threading import RLock
from urllib.parse import urlparse
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from src.config import PAINEL_FILE
from src.actions.file_mover import (
    mover_arquivo_seguro,
    desfazer_ultima_movimentacao,
    obter_historico_movimentacoes,
)
from src.core import (
    atualizar_estado_externo,
    executar_orquestracao,
    marcar_arquivo_movido,
    marcar_arquivo_restaurado,
    reconciliar_estado_operacional,
)
from src.document_access import (
    autorizar_destino,
    caminho_destino_autorizado,
    caminho_fonte_autorizado,
    classificar_arquivo_autorizado,
    obter_arquivo_autorizado,
    obter_arquivo_registrado,
    obter_destino_registrado,
    obter_documento_autorizado,
    restaurar_autorizacao_na_origem,
    SNAPSHOT_VALID,
    transferir_autorizacao_para_destino,
    validar_destino,
)

MAX_CORPO_HTTP_BYTES = 16 * 1024
HOSTS_LOOPBACK = {"localhost", "127.0.0.1"}
IDENTIFICADOR_RE = re.compile(r"[A-Za-z0-9_-]{43}\Z")
_OPERATIONS_LOCK = RLock()


class OrquestradorRequestHandler(BaseHTTPRequestHandler):
    """Manipulador de requisições HTTP do painel."""

    def _responder_json(self, status_code: int, dados: dict):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(corpo)

    def _host_valido(self) -> bool:
        hosts = self.headers.get_all("Host", [])
        if len(hosts) != 1:
            return False
        port = self.server.server_port
        permitidos = {
            f"{host}:{port}".lower()
            for host in HOSTS_LOOPBACK
        }
        if port == 80:
            permitidos.update(HOSTS_LOOPBACK)
        return hosts[0].strip().lower() in permitidos

    def _origin_valido(self, origin: str) -> bool:
        port = self.server.server_port
        permitidas = {
            f"http://{host}:{port}".lower()
            for host in HOSTS_LOOPBACK
        }
        if port == 80:
            permitidas.update(f"http://{host}" for host in HOSTS_LOOPBACK)
        return origin.lower() in permitidas

    def _validar_host_e_origem(self, exigir_origem: bool = False) -> bool:
        if not self._host_valido():
            self._responder_json(403, {"sucesso": False, "erro": "Host não autorizado."})
            return False
        host = self.headers.get("Host", "").strip().lower()
        origem = self.headers.get("Origin")
        origens = self.headers.get_all("Origin", [])
        if exigir_origem and not origem:
            self._responder_json(403, {"sucesso": False, "erro": "Origem da requisição não autorizada."})
            return False
        if len(origens) > 1:
            self._responder_json(403, {"sucesso": False, "erro": "Origem da requisição não autorizada."})
            return False
        if origem:
            origem_host = origem.lower().removeprefix("http://")
            if not self._origin_valido(origem) or origem_host != host:
                self._responder_json(403, {"sucesso": False, "erro": "Origem da requisição não autorizada."})
                return False
        return True

    def _validar_csrf(self) -> bool:
        tokens = self.headers.get_all("X-CSRF-Token", [])
        token = tokens[0] if len(tokens) == 1 else ""
        esperado = getattr(self.server, "csrf_token", "")
        if not token or not esperado or not hmac.compare_digest(token, esperado):
            self._responder_json(403, {"sucesso": False, "erro": "Token de segurança inválido."})
            return False
        return True

    def _content_length(self) -> tuple[int | None, int | None]:
        valores = self.headers.get_all("Content-Length", [])
        if len(valores) > 1:
            return None, 400
        valor = self.headers.get("Content-Length")
        if valor is None:
            return None, 411
        if not valor.isdigit():
            return None, 400
        if len(valor) > len(str(MAX_CORPO_HTTP_BYTES)):
            return None, 413
        tamanho = int(valor)
        if tamanho > MAX_CORPO_HTTP_BYTES:
            return None, 413
        if self.headers.get("Transfer-Encoding"):
            return None, 400
        return tamanho, None

    def _content_type_json(self) -> bool:
        content_types = self.headers.get_all("Content-Type", [])
        if len(content_types) != 1:
            return False
        content_type = content_types[0]
        return content_type.split(";", 1)[0].strip().lower() == "application/json"

    def _validar_requisicao_mutavel(self) -> int | None:
        if not self._validar_host_e_origem(exigir_origem=True):
            return 403
        if not self._validar_csrf():
            return 403
        if not self._content_type_json():
            self._responder_json(415, {"sucesso": False, "erro": "Content-Type deve ser application/json."})
            return 415
        _, erro_tamanho = self._content_length()
        if erro_tamanho is not None:
            mensagens = {
                400: "Content-Length inválido.",
                411: "Content-Length é obrigatório.",
                413: "Corpo da requisição excede o limite permitido.",
            }
            self._responder_json(erro_tamanho, {"sucesso": False, "erro": mensagens[erro_tamanho]})
            self.close_connection = True
            return erro_tamanho
        return None

    def handle_expect_100(self):
        if not self._validar_host_e_origem(exigir_origem=True):
            return False
        if not self._validar_csrf():
            return False
        if not self._content_type_json():
            self._responder_json(415, {"sucesso": False, "erro": "Content-Type deve ser application/json."})
            return False
        _, erro_tamanho = self._content_length()
        if erro_tamanho is not None:
            mensagens = {
                400: "Content-Length inválido.",
                411: "Content-Length é obrigatório.",
                413: "Corpo da requisição excede o limite permitido.",
            }
            self._responder_json(erro_tamanho, {"sucesso": False, "erro": mensagens[erro_tamanho]})
            self.close_connection = True
            return False
        self.send_response_only(100)
        self.end_headers()
        return True

    def _ler_json(self) -> dict | None:
        tamanho, erro = self._content_length()
        if erro is not None:
            return None
        corpo = self.rfile.read(tamanho or 0)
        if len(corpo) != tamanho:
            self._responder_json(400, {"sucesso": False, "erro": "Corpo da requisição incompleto."})
            return None
        try:
            payload = json.loads(corpo.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._responder_json(400, {"sucesso": False, "erro": "JSON inválido."})
            return None
        if not isinstance(payload, dict):
            self._responder_json(400, {"sucesso": False, "erro": "O corpo JSON deve ser um objeto."})
            return None
        return payload

    def do_OPTIONS(self):
        if self._validar_host_e_origem(exigir_origem=True):
            self._responder_json(405, {"sucesso": False, "erro": "CORS não é habilitado neste servidor."})

    def _responder_texto(self, status_code: int, mensagem: str, content_type: str = "text/plain; charset=utf-8"):
        corpo = mensagem.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(corpo)

    def _servir_pdf_autorizado(self, identificador: str):
        if not IDENTIFICADOR_RE.fullmatch(identificador or ""):
            self._responder_texto(404, "Documento não autorizado.")
            return

        estado_snapshot = classificar_arquivo_autorizado(identificador)
        if estado_snapshot != SNAPSHOT_VALID:
            atualizar_estado_externo(identificador, estado_snapshot)
        arquivo = obter_documento_autorizado(identificador)
        if arquivo is None:
            self._responder_texto(404, "Documento não autorizado.")
            return
        if not arquivo.exists():
            self._responder_texto(404, "Documento não encontrado.")
            return
        if not arquivo.is_file():
            self._responder_texto(404, "Documento não encontrado.")
            return

        try:
            leitor = PdfReader(str(arquivo))
            if getattr(leitor, "is_encrypted", False):
                self._responder_texto(423, "Documento PDF protegido por senha.")
                return
        except PdfReadError:
            self._responder_texto(422, "Documento PDF inválido.")
            return
        except (OSError, PermissionError):
            self._responder_texto(403, "Documento PDF inacessível.")
            return

        try:
            tamanho = arquivo.stat().st_size
            arquivo_aberto = arquivo.open("rb")
        except (OSError, PermissionError):
            self._responder_texto(403, "Documento PDF inacessível.")
            return

        inicio = 0
        fim = tamanho - 1
        status_code = 200
        faixa = self.headers.get("Range")
        if faixa:
            correspondencia = re.fullmatch(r"bytes=(\d*)-(\d*)", faixa.strip())
            if correspondencia:
                primeiro, ultimo = correspondencia.groups()
                try:
                    inicio = int(primeiro) if primeiro else max(0, tamanho - int(ultimo))
                    fim = int(ultimo) if ultimo else tamanho - 1
                except (TypeError, ValueError):
                    inicio = 0
                    fim = tamanho - 1
                inicio = max(0, inicio)
                fim = min(tamanho - 1, fim)
                if inicio > fim:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{tamanho}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    arquivo_aberto.close()
                    return
                status_code = 206

        comprimento = fim - inicio + 1
        self.send_response(status_code)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(comprimento))
        self.send_header("Accept-Ranges", "bytes")
        if status_code == 206:
            self.send_header("Content-Range", f"bytes {inicio}-{fim}/{tamanho}")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.end_headers()
        try:
            arquivo_aberto.seek(inicio)
            restante = comprimento
            while restante > 0:
                bloco = arquivo_aberto.read(min(1024 * 1024, restante))
                if not bloco:
                    break
                self.wfile.write(bloco)
                restante -= len(bloco)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            arquivo_aberto.close()

    def do_GET(self):
        if not self._validar_host_e_origem():
            return

        parsed = urlparse(self.path)

        if parsed.path in {"/", "/index.html", "/painel.html"}:
            reconciliar_estado_operacional()
            if not PAINEL_FILE.exists():
                executar_orquestracao(abrir_navegador=False)

            conteudo = PAINEL_FILE.read_bytes()
            if getattr(self.server, "homologacao", False):
                marcador_corpo = b"<body>"
                if marcador_corpo not in conteudo:
                    self._responder_texto(500, "O painel não possui a área principal esperada.")
                    return
                banner = (
                    b'<div role="status" id="aviso-homologacao" '
                    b'style="position:sticky;top:0;z-index:10000;padding:10px;'
                    b'background:#7a271a;color:#fff;text-align:center;'
                    b'font-weight:700;letter-spacing:.04em">'
                    b'AMBIENTE DE HOMOLOGACAO - SOMENTE DADOS FICTICIOS</div>'
                )
                conteudo = conteudo.replace(
                    marcador_corpo,
                    marcador_corpo + banner,
                    1,
                )
            token = getattr(self.server, "csrf_token", "")
            meta = f'<meta name="csrf-token" content="{token}">'.encode("ascii")
            marcador = b"</head>"
            if marcador not in conteudo:
                self._responder_texto(500, "O painel não possui o cabeçalho esperado.")
                return
            conteudo = conteudo.replace(marcador, meta + marcador, 1)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(conteudo)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "SAMEORIGIN")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(conteudo)
            return

        if parsed.path == "/api/status":
            historico = [
                {
                    "arquivo": Path(item["destino_atual"]).name,
                    "data_hora": item["data_hora"],
                }
                for item in obter_historico_movimentacoes()
            ]
            self._responder_json(200, {
                "status": "online",
                "historico": historico,
            })
            return

        if parsed.path.startswith("/api/documento/"):
            identificador = parsed.path[len("/api/documento/"):].strip("/")
            self._servir_pdf_autorizado(identificador)
            return

        self.send_error(404, "Recurso não encontrado")

    def do_POST(self):
        with _OPERATIONS_LOCK:
            self._processar_post()

    def _processar_post(self):
        erro_validacao = self._validar_requisicao_mutavel()
        if erro_validacao is not None:
            return

        parsed = urlparse(self.path)
        payload = self._ler_json()
        if payload is None:
            return
        if parsed.path in {"/api/mover", "/api/desfazer", "/api/reanalisar"}:
            reconciliar_estado_operacional()

        if parsed.path == "/api/mover":
            arquivo_id = payload.get("arquivo_id")
            destino_id = payload.get("destino_id")
            if (
                set(payload) != {"arquivo_id", "destino_id"}
                or not isinstance(arquivo_id, str)
                or not IDENTIFICADOR_RE.fullmatch(arquivo_id)
                or not isinstance(destino_id, str)
                or not IDENTIFICADOR_RE.fullmatch(destino_id)
            ):
                self._responder_json(400, {
                    "sucesso": False,
                    "erro": "Identificadores de arquivo e destino inválidos.",
                })
                return

            arquivo_registrado = obter_arquivo_registrado(arquivo_id)
            if arquivo_registrado is None:
                self._responder_json(404, {"sucesso": False, "erro": "Arquivo não autorizado."})
                return
            arquivo = obter_arquivo_autorizado(arquivo_id)
            if arquivo is None or not caminho_fonte_autorizado(arquivo.path):
                estado_snapshot = classificar_arquivo_autorizado(arquivo_id)
                estado = atualizar_estado_externo(arquivo_id, estado_snapshot)
                self._responder_json(409, {
                    "sucesso": False,
                    "erro": "O arquivo mudou desde a análise.",
                    **(estado or {}),
                })
                return

            destino_registrado = obter_destino_registrado(destino_id)
            if destino_registrado is None:
                self._responder_json(403, {"sucesso": False, "erro": "Destino não autorizado."})
                return
            destino = autorizar_destino(destino_id)
            if destino is None or not validar_destino(destino_registrado):
                self._responder_json(409, {"sucesso": False, "erro": "O destino mudou desde a análise."})
                return

            resultado = mover_arquivo_seguro(
                arquivo.path,
                destino.path,
                arquivo_autorizado=arquivo,
                destino_autorizado=destino,
                id_autorizacao=arquivo_id,
            )
            if not resultado.get("sucesso"):
                estado_snapshot = classificar_arquivo_autorizado(arquivo_id)
                estado = atualizar_estado_externo(arquivo_id, estado_snapshot)
                self._responder_json(409, {
                    "sucesso": False,
                    "erro": "Não foi possível mover o arquivo. Reanalise e tente novamente.",
                    **(estado or {}),
                })
                return
            autorizacao_transferida = transferir_autorizacao_para_destino(
                arquivo_id,
                destino_id,
                Path(resultado["destino"]),
            )
            estado = marcar_arquivo_movido(
                arquivo_id,
                Path(resultado["destino"]),
                autorizacao_transferida,
            )
            self._responder_json(200, {
                "sucesso": True,
                "nome_final": resultado["nome_final"],
                **(estado or {}),
                **({"aviso": resultado["aviso"]} if resultado.get("aviso") else {}),
            })
            return

        if parsed.path == "/api/desfazer":
            if payload:
                self._responder_json(400, {
                    "sucesso": False,
                    "erro": "A reversão não aceita campos no corpo.",
                })
                return
            historico = obter_historico_movimentacoes()
            if historico:
                ultima = historico[-1]
                if (
                    not caminho_fonte_autorizado(ultima["origem_original"])
                    or not caminho_destino_autorizado(ultima["destino_atual"])
                ):
                    self._responder_json(403, {
                        "sucesso": False,
                        "erro": "A reversão não pertence a uma operação autorizada.",
                    })
                    return
            resultado = desfazer_ultima_movimentacao()
            if not resultado.get("sucesso"):
                erro = resultado.get("erro", "")
                if "não encontrado" in erro.lower():
                    mensagem = "O arquivo movido não está no destino; o histórico foi preservado."
                elif "mudou desde" in erro.lower():
                    mensagem = "O arquivo foi alterado; a reversão foi interrompida e o histórico foi preservado."
                else:
                    mensagem = "A reversão falhou; o histórico foi preservado para nova tentativa."
                self._responder_json(409, {
                    "sucesso": False,
                    "erro": mensagem,
                    **({"aviso": resultado["aviso"]} if resultado.get("aviso") else {}),
                })
                return
            arquivo_id = resultado.get("id_autorizacao")
            caminho_restaurado = Path(resultado["arquivo_restaurado"])
            autorizacao_restaurada = bool(
                arquivo_id
                and restaurar_autorizacao_na_origem(arquivo_id, caminho_restaurado)
            )
            estado = marcar_arquivo_restaurado(
                arquivo_id,
                caminho_restaurado,
                autorizacao_restaurada,
                Path(resultado["origem_original"]),
            )
            self._responder_json(200, {
                "sucesso": True,
                "mensagem": "Arquivo restaurado para a pasta original.",
                **(estado or {}),
                **({"aviso": resultado["aviso"]} if resultado.get("aviso") else {}),
            })
            return

        if parsed.path == "/api/reanalisar":
            if payload:
                self._responder_json(400, {
                    "sucesso": False,
                    "erro": "A reanálise não aceita campos no corpo.",
                })
                return
            res = executar_orquestracao(abrir_navegador=False)
            self._responder_json(200, {
                "sucesso": True,
                "total": res["total_analisados"],
            })
            return

        self.send_error(404, "Endpoint não encontrado")


def iniciar_servidor(
    porta: int = 8080,
    abrir_navegador: bool = True,
    homologacao: bool = False,
):
    """Inicia o servidor HTTP do painel interativo."""
    endereco = ("127.0.0.1", porta)
    try:
        servidor = ThreadingHTTPServer(endereco, OrquestradorRequestHandler)
    except OSError:
        # Se a porta estiver em uso, tenta uma porta alternativa
        porta = porta + 1
        endereco = ("127.0.0.1", porta)
        servidor = ThreadingHTTPServer(endereco, OrquestradorRequestHandler)
    servidor.csrf_token = secrets.token_urlsafe(32)
    servidor.homologacao = homologacao

    url = f"http://localhost:{porta}/"
    print("\n" + "=" * 60)
    print(f"PAINEL INTERATIVO CONECTADO: {url}")
    print("Pressione Ctrl+C para encerrar o servidor.")
    print("=" * 60)

    if abrir_navegador:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado pelo usuário.")
    finally:
        servidor.server_close()
