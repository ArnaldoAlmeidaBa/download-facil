"""Servidor local HTTP para o painel interativo do Orquestrador."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import json
import webbrowser
from urllib.parse import parse_qs, urlparse

from src.config import PAINEL_FILE, carregar_perfil
from src.actions.file_mover import (
    mover_arquivo_seguro,
    desfazer_ultima_movimentacao,
    obter_historico_movimentacoes,
)
from src.core import executar_orquestracao


class OrquestradorRequestHandler(BaseHTTPRequestHandler):
    """Manipulador de requisições HTTP do painel."""

    def _responder_json(self, status_code: int, dados: dict):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(corpo)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

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
