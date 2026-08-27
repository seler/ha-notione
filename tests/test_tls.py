"""TLS behavior: the client must reject untrusted certificates (fail closed)."""
import json
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import pytest
import trustme

from custom_components.notione.api import NotiOneApiError, NotiOneClient

from homeassistant.helpers.aiohttp_client import async_get_clientsession


class _TokenHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.dumps({"access_token": "should-never-be-reached"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def _start_untrusted_tls_server():
    """Serve the token endpoint behind a certificate no client trusts."""
    ca = trustme.CA()
    cert = ca.issue_cert("127.0.0.1")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    cert.configure_cert(context)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _TokenHandler)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, server.server_address[1]


async def test_untrusted_certificate_fails_closed(hass, socket_enabled):
    """A server with a self-signed (untrusted) certificate must be rejected."""
    server, port = _start_untrusted_tls_server()
    try:
        with patch(
            "custom_components.notione.api.TOKEN_URL",
            f"https://127.0.0.1:{port}/oauth/token",
        ):
            client = NotiOneClient(
                async_get_clientsession(hass), "user@example.com", "pw"
            )
            with pytest.raises(NotiOneApiError) as excinfo:
                await client.async_authenticate()
    finally:
        server.shutdown()
        server.server_close()

    cause_chain = []
    err = excinfo.value
    while err is not None:
        cause_chain.append(type(err).__name__)
        err = err.__cause__
    assert any("Certificate" in name or "SSL" in name for name in cause_chain), (
        f"expected a certificate verification failure in the cause chain, "
        f"got {cause_chain}"
    )
