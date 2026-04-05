"""Tests for ScaffoldManager."""

from __future__ import annotations

from ctfx.managers.scaffold import ScaffoldManager


def test_pwn_template_generated(comp_wm):
    chal_dir = comp_wm.create_challenge("pwn", "baby_pwn")
    ScaffoldManager.generate("pwn", chal_dir)
    text = (chal_dir / "solve" / "exploit.py").read_text(encoding="utf-8")
    assert "from pwn import *" in text


def test_pwn_patches_remote(comp_wm):
    chal_dir = comp_wm.create_challenge("pwn", "remote_pwn")
    ScaffoldManager.generate("pwn", chal_dir, remote="nc chall.ctf.org 31337")
    text = (chal_dir / "solve" / "exploit.py").read_text(encoding="utf-8")
    assert 'HOST = "chall.ctf.org"' in text
    assert "PORT = 31337" in text


def test_crypto_template(comp_wm):
    chal_dir = comp_wm.create_challenge("crypto", "rsa")
    ScaffoldManager.generate("crypto", chal_dir)
    assert "Crypto.Util.number" in (chal_dir / "solve" / "exploit.py").read_text(encoding="utf-8")


def test_forensics_template(comp_wm):
    chal_dir = comp_wm.create_challenge("forensics", "pcap")
    ScaffoldManager.generate("forensics", chal_dir)
    assert "SRC = Path" in (chal_dir / "solve" / "exploit.py").read_text(encoding="utf-8")


def test_rev_template(comp_wm):
    chal_dir = comp_wm.create_challenge("rev", "crackme")
    ScaffoldManager.generate("rev", chal_dir)
    assert "ghidra" in (chal_dir / "solve" / "exploit.py").read_text(encoding="utf-8")


def test_misc_template(comp_wm):
    chal_dir = comp_wm.create_challenge("misc", "quiz")
    ScaffoldManager.generate("misc", chal_dir)
    assert "--- solve here ---" in (chal_dir / "solve" / "exploit.py").read_text(encoding="utf-8")


def test_web_no_exploit(comp_wm):
    chal_dir = comp_wm.create_challenge("web", "xss")
    ScaffoldManager.generate("web", chal_dir)
    assert not (chal_dir / "solve" / "exploit.py").exists()


def test_case_insensitive_category(comp_wm):
    chal_dir = comp_wm.create_challenge("pwn", "casey")
    ScaffoldManager.generate("PWN", chal_dir)
    assert (chal_dir / "solve" / "exploit.py").exists()
