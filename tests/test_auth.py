"""Tests for server auth primitives."""

from __future__ import annotations

import hashlib
import hmac
import time

from ctfx.server.auth import (
    TicketStore,
    make_session_cookie,
    verify_session_cookie,
)


def _make_ticket(token: str, version: int, ttl: int) -> str:
    import secrets
    nonce = secrets.token_hex(16)
    expires = int(time.time()) + ttl
    payload = f"{nonce}.{expires}.{version}"
    sig = hmac.new(token.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def test_valid_ticket_accepted():
    store = TicketStore()
    token = "a" * 64
    ticket = _make_ticket(token, 1, 60)
    assert store.validate_and_redeem(ticket, token, 1) is True


def test_expired_ticket_rejected():
    store = TicketStore()
    token = "a" * 64
    ticket = _make_ticket(token, 1, -1)
    assert store.validate_and_redeem(ticket, token, 1) is False


def test_wrong_version_rejected():
    store = TicketStore()
    token = "a" * 64
    ticket = _make_ticket(token, 2, 60)
    assert store.validate_and_redeem(ticket, token, 1) is False


def test_wrong_token_rejected():
    store = TicketStore()
    ticket = _make_ticket("a" * 64, 1, 60)
    assert store.validate_and_redeem(ticket, "b" * 64, 1) is False


def test_single_use_enforced():
    store = TicketStore()
    token = "a" * 64
    ticket = _make_ticket(token, 1, 60)
    assert store.validate_and_redeem(ticket, token, 1) is True
    assert store.validate_and_redeem(ticket, token, 1) is False


def test_malformed_ticket_rejected():
    store = TicketStore()
    assert store.validate_and_redeem("notavalidticket", "x" * 64, 1) is False
    assert store.validate_and_redeem("", "x" * 64, 1) is False
    assert store.validate_and_redeem("a.b.c", "x" * 64, 1) is False


def test_valid_cookie_accepted():
    token = "z" * 64
    cookie = make_session_cookie(token, 1, 3600)
    assert verify_session_cookie(cookie, token, 1, 3600) is True


def test_wrong_token_cookie_rejected():
    cookie = make_session_cookie("a" * 64, 1, 3600)
    assert verify_session_cookie(cookie, "b" * 64, 1, 3600) is False


def test_wrong_version_cookie_rejected():
    token = "z" * 64
    cookie = make_session_cookie(token, 1, 3600)
    assert verify_session_cookie(cookie, token, 2, 3600) is False


def test_expired_cookie_rejected():
    token = "z" * 64
    cookie = make_session_cookie(token, 1, 3600)
    assert verify_session_cookie(cookie, token, 1, -1) is False


def test_tampered_cookie_rejected():
    assert verify_session_cookie("garbage.value.here", "z" * 64, 1, 3600) is False
