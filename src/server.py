"""Servidor local HTTP para o painel interativo do Orquestrador."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import json
import webbrowser
from urllib.parse import parse_qs, urlparse
import re
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from src.config import PAINEL_FILE, carregar_perfil
from src.actions.file_mover import (
    mover_arquivo_seguro,
    desfazer_ultima_movimentacao,
    obter_historico_movimentacoes,
)
from src.core import executar_orquestracao
from src.document_access import obter_documento_autorizado


class OrquestradorRequestHandler(BaseHTTPRequestHandler):
    """Manipulador de requisições HTTP do painel."""

    def _responder_json(self, status_code: int, dados: dict):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(corpo)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def _responder_texto(self, status_code: int, mensagem: str, content_type: str = "text/plain; charset=utf-8"):
        corpo = mensagem.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _servir_pdf_autorizado(self, identificador: str):
        if not re.fullmatch(r"[0-9a-f]{64}", identificador or ""):
            self._responder_texto(404, "Documento não autorizado.")
            return

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
        parsed = urlparse(self.path)

        if parsed.path in {"/", "/index.html", "/painel.html"}:
            if not PAINEL_FILE.exists():
                executar_orquestracao(abrir_navegador=False)

            conteudo = PAINEL_FILE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(conteudo)))
            self.end_headers()
            self.wfile.write(conteudo)
            return

        if parsed.path == "/api/status":
            self._responder_json(200, {
                "status": "online",
                "historico": obter_historico_movimentacoes(),
            })
            return

        if parsed.path.startswith("/api/documento/"):
            identificador = parsed.path[len("/api/documento/"):].strip("/")
            self._servir_pdf_autorizado(identificador)
            return

        self.send_error(404, "Recurso não encontrado")

    def do_POST(self):
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"

        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            payload = {}

        if parsed.path == "/api/mover":
            origem_str = payload.get("origem")
            destino_str = payload.get("destino")

            if not origem_str or not destino_str:
                self._responder_json(400, {
                    "sucesso": False,
                    "erro": "Origem e destino são obrigatórios."
                })
                return

            resultado = mover_arquivo_seguro(
                origem=Path(origem_str),
                destino_pasta=Path(destino_str),
            )
            self._responder_json(200 if resultado.get("sucesso") else 500, resultado)
            return

        if parsed.path == "/api/desfazer":
            resultado = desfazer_ultima_movimentacao()
            self._responder_json(200 if resultado.get("sucesso") else 400, resultado)
            return

        if parsed.path == "/api/reanalisar":
            res = executar_orquestracao(abrir_navegador=False)
            self._responder_json(200, {
                "sucesso": True,
                "total": res["total_analisados"],
            })
            return

        self.send_error(404, "Endpoint não encontrado")


def iniciar_servidor(porta: int = 8080, abrir_navegador: bool = True):
    """Inicia o servidor HTTP do painel interativo."""
    endereco = ("127.0.0.1", porta)
    try:
        servidor = ThreadingHTTPServer(endereco, OrquestradorRequestHandler)
    except OSError:
        # Se a porta estiver em uso, tenta uma porta alternativa
        porta = porta + 1
        endereco = ("127.0.0.1", porta)
        servidor = ThreadingHTTPServer(endereco, OrquestradorRequestHandler)

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
