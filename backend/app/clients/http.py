from __future__ import annotations

import ssl

import truststore

truststore.inject_into_ssl()

import httpx

_SSL: ssl.SSLContext | None = None


def ssl_context() -> ssl.SSLContext:
    """Verify certs via the OS trust store. Ignore peers that skip TLS close_notify.

    Python 3.13+ / OpenSSL 3 treat a sudden EOF as fatal. Zoho Cliq (and some CDNs)
    close that way; the handshake was still valid.
    """
    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    if hasattr(ssl, "OP_IGNORE_UNEXPECTED_EOF"):
        ctx.options |= ssl.OP_IGNORE_UNEXPECTED_EOF
    return ctx


def _verify() -> ssl.SSLContext:
    global _SSL
    if _SSL is None:
        _SSL = ssl_context()
    return _SSL


def client(**kwargs) -> httpx.Client:
    kwargs.setdefault("timeout", 45)
    kwargs.setdefault("verify", _verify())
    kwargs.setdefault("http2", False)
    return httpx.Client(**kwargs)


def get(url: str, **kwargs):
    kwargs.setdefault("timeout", 45)
    kwargs.setdefault("verify", _verify())
    return httpx.get(url, **kwargs)


def post(url: str, **kwargs):
    kwargs.setdefault("timeout", 45)
    kwargs.setdefault("verify", _verify())
    return httpx.post(url, **kwargs)
