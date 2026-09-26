"""SMTP against real servers on real sockets, both TLS dialects.

This exists because of a live failure: Hostinger's submission port is 465,
the code opened it with plain smtplib.SMTP, and the two sides deadlocked —
we waited for a greeting that never comes in the clear, the server waited
for a ClientHello. It surfaced as "Connection unexpectedly closed: timed
out", which reads like a firewall and sent the search in the wrong
direction entirely.

Mocking smtplib cannot catch that: the bug is in the wire protocol, so the
test has to be an actual server doing an actual handshake.
"""

import base64
import socket
import ssl
import subprocess
import threading
from pathlib import Path

import pytest

CERT_DIR = Path(__file__).parent / "_smtp_certs"


@pytest.fixture(scope="module")
def certs():
    """A self-signed cert with a SAN for localhost, so the client's ordinary
    verification stays switched on rather than being disabled for the test."""
    CERT_DIR.mkdir(exist_ok=True)
    cert, key = CERT_DIR / "cert.pem", CERT_DIR / "key.pem"
    if not cert.exists():
        subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "rsa:2048",
             "-keyout", str(key), "-out", str(cert), "-days", "3650", "-nodes",
             "-subj", "/CN=localhost",
             "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1"],
            check=True, capture_output=True,
        )
    return cert, key


class SmtpServer(threading.Thread):
    """Enough of RFC 5321 to greet, advertise, upgrade and authenticate."""

    daemon = True

    def __init__(self, certs, *, implicit: bool):
        super().__init__()
        cert, key = certs
        self.ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.ctx.load_cert_chain(cert, key)
        self.implicit = implicit
        self.logged_in = False
        self.saw_starttls = False
        self.stopping = False

        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        # accept() blocked forever holds a reference to the fd, so close()
        # from another thread would not actually release the port.
        self.sock.settimeout(0.5)
        self.port = self.sock.getsockname()[1]

    def stop(self):
        self.stopping = True
        self.join(timeout=5)
        self.sock.close()

    def run(self):
        while not self.stopping:
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn):
        try:
            if self.implicit:
                conn = self.ctx.wrap_socket(conn, server_side=True)
            self._session(conn)
        except (ssl.SSLError, OSError):
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def _session(self, conn):
        secured = self.implicit
        f = conn.makefile("rwb")
        f.write(b"220 test.local ESMTP\r\n")
        f.flush()
        while True:
            line = f.readline()
            if not line:
                return
            cmd = line.decode("utf-8", "replace").strip()
            up = cmd.upper()

            if up.startswith(("EHLO", "HELO")):
                caps = [b"250-test.local", b"250-AUTH PLAIN LOGIN"]
                if not secured:
                    caps.append(b"250-STARTTLS")
                caps.append(b"250 OK")
                f.write(b"\r\n".join(caps) + b"\r\n")
            elif up == "STARTTLS":
                f.write(b"220 Go ahead\r\n")
                f.flush()
                self.saw_starttls = secured = True
                conn = self.ctx.wrap_socket(conn, server_side=True)
                f = conn.makefile("rwb")
                continue
            elif up.startswith("AUTH PLAIN"):
                parts = cmd.split(" ", 2)
                blob = base64.b64decode(parts[2]) if len(parts) > 2 else b""
                self.logged_in = blob.split(b"\x00")[-1] == b"correct-horse"
                f.write(b"235 OK\r\n" if self.logged_in else b"535 Bad credentials\r\n")
            elif up.startswith("AUTH LOGIN"):
                f.write(b"334 VXNlcm5hbWU6\r\n")
                f.flush()
                f.readline()
                f.write(b"334 UGFzc3dvcmQ6\r\n")
                f.flush()
                self.logged_in = base64.b64decode(f.readline().strip()) == b"correct-horse"
                f.write(b"235 OK\r\n" if self.logged_in else b"535 Bad credentials\r\n")
            elif up.startswith(("MAIL", "RCPT")):
                f.write(b"250 OK\r\n")
            elif up == "DATA":
                f.write(b"354 End with .\r\n")
                f.flush()
                while f.readline() not in (b".\r\n", b""):
                    pass
                f.write(b"250 Queued\r\n")
            elif up == "QUIT":
                f.write(b"221 Bye\r\n")
                f.flush()
                return
            else:
                f.write(b"250 OK\r\n")
            f.flush()


@pytest.fixture
def smtp_env(monkeypatch, certs):
    """Point the app at a live server, with the test cert in the trust store
    so TLS verification behaves exactly as it does in production."""
    def _start(*, implicit: bool, password: str = "correct-horse"):
        server = SmtpServer(certs, implicit=implicit)
        server.start()

        monkeypatch.setenv("SSL_CERT_FILE", str(certs[0]))
        from app.core import config

        settings = config.get_settings()
        for attr, value in {
            "SMTP_HOST": "localhost",
            "SMTP_PORT": server.port,
            "SMTP_USERNAME": "digest@jobquickai.site",
            "SMTP_PASSWORD": password,
            "SMTP_FROM_EMAIL": "digest@jobquickai.site",
            "SMTP_USE_TLS": True,
            # The port is ephemeral, so the dialect is stated outright rather
            # than inferred from it.
            "SMTP_USE_SSL": implicit,
        }.items():
            monkeypatch.setattr(settings, attr, value, raising=False)
        return server

    started: list[SmtpServer] = []
    yield lambda **kw: started.append(_start(**kw)) or started[-1]
    for s in started:
        s.stop()


def test_implicit_tls_port_sends(smtp_env):
    """The Hostinger case: TLS from the first byte, no STARTTLS."""
    from app.services import notifications

    server = smtp_env(implicit=True)
    assert notifications.send_email("someone@example.com", "Digest", "3 matches") is True
    assert server.logged_in
    assert not server.saw_starttls


def test_starttls_port_sends(smtp_env):
    from app.services import notifications

    server = smtp_env(implicit=False)
    assert notifications.send_email("someone@example.com", "Digest", "3 matches") is True
    assert server.logged_in
    assert server.saw_starttls


def test_plain_smtp_against_an_implicit_tls_server_is_the_bug_we_fixed(smtp_env):
    """The original failure, pinned so it cannot come back: speaking plain
    SMTP to a TLS-only port hangs rather than erroring, because each side is
    waiting for the other to speak first."""
    import smtplib

    server = smtp_env(implicit=True)
    with pytest.raises((smtplib.SMTPServerDisconnected, OSError)):
        smtplib.SMTP("localhost", server.port, timeout=3)


@pytest.mark.parametrize("implicit", [True, False])
def test_the_health_check_agrees_with_the_sender(smtp_env, implicit):
    """A check that opened its connection differently from the sender could
    go green against a server the digest cannot actually use."""
    from app.services import integration_checks, notifications

    smtp_env(implicit=implicit)
    assert integration_checks.check_smtp().ok is True
    assert notifications.send_email("someone@example.com", "s", "b") is True


def test_a_rejected_password_is_reported_as_such_not_as_a_connection_error(smtp_env):
    from app.services import integration_checks

    smtp_env(implicit=True, password="wrong")
    result = integration_checks.check_smtp()
    assert result.ok is False
    assert "rejected" in result.detail


def test_a_server_that_is_not_there_returns_false_rather_than_raising(monkeypatch, certs):
    """The digest loop must not abandon everyone else because the relay is
    down, so a transport failure is a False, not an exception."""
    from app.core import config
    from app.services import notifications

    # Bind and immediately release, so the port is real but nothing answers.
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    dead_port = probe.getsockname()[1]
    probe.close()

    settings = config.get_settings()
    for attr, value in {
        "SMTP_HOST": "localhost", "SMTP_PORT": dead_port,
        "SMTP_USERNAME": "u", "SMTP_PASSWORD": "p",
        "SMTP_FROM_EMAIL": "digest@jobquickai.site",
        "SMTP_USE_TLS": True, "SMTP_USE_SSL": False,
    }.items():
        monkeypatch.setattr(settings, attr, value, raising=False)

    assert notifications.send_email("someone@example.com", "Digest", "body") is False
