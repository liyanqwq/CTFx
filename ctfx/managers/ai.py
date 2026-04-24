"""Shared AI provider helpers."""

from __future__ import annotations

import json
from typing import Any

from ctfx.managers.config import ConfigManager

OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"
ANTHROPIC_DEFAULT_BASE_URL = "https://api.anthropic.com"


def get_provider(cfg: ConfigManager) -> str:
    return (cfg.get("ai_provider") or "openai").lower()


def get_model(cfg: ConfigManager) -> str:
    return cfg.get("ai_model") or "gpt-5.4"


def get_base_url(cfg: ConfigManager, provider: str) -> str:
    if provider == "openai":
        return cfg.get("ai_openai_base_url") or OPENAI_DEFAULT_BASE_URL
    if provider == "anthropic":
        return (
            cfg.get("ai_anthropic_base_url")
            or cfg.get("ai_endpoint")
            or ANTHROPIC_DEFAULT_BASE_URL
        )
    raise RuntimeError(f"Unsupported ai_provider '{provider}'")


def get_api_key(cfg: ConfigManager, provider: str) -> str:
    key = cfg.get("ai_api_key") or cfg.get("anthropic_api_key")
    if key:
        return key

    raise RuntimeError(
        "No AI API key found. Save ai_api_key in your global config."
    )


def get_api_key_source(cfg: ConfigManager) -> str:
    if cfg.get("ai_api_key"):
        return "config.ai_api_key"
    if cfg.get("anthropic_api_key"):
        return "config.anthropic_api_key"
    return "missing"


def run_prompt(
    cfg: ConfigManager,
    prompt: str,
    *,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    provider = get_provider(cfg)
    model = get_model(cfg)
    api_key = get_api_key(cfg, provider)
    base_url = get_base_url(cfg, provider)

    if provider == "openai":
        text = _run_openai(prompt, model, api_key, base_url, max_tokens)
    elif provider == "anthropic":
        text = _run_anthropic(prompt, model, api_key, base_url, max_tokens)
    else:
        raise RuntimeError(f"Unsupported ai_provider '{provider}'")

    return {
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "text": text.strip(),
    }


def test_connection(cfg: ConfigManager) -> dict[str, Any]:
    result = run_prompt(
        cfg,
        "Reply with exactly OK.",
        max_tokens=16,
    )
    result["ok"] = result["text"].strip() == "OK"
    return result


def extract_challenge_data(content: str, cfg: ConfigManager) -> dict[str, Any]:
    schema_example = json.dumps(
        {
            "name": "baby_pwn",
            "category": "pwn",
            "description": "Overflow the buffer and get shell.",
            "attachments": [{"name": "chall", "url": "https://..."}],
            "flag_format": "flag{...}",
            "remote": "nc chall.ctf.org 1337",
            "points": 100,
        },
        indent=2,
    )

    prompt = (
        "Extract CTF challenge information from the following text and output ONLY valid JSON "
        "matching this schema (no preamble, no markdown fences):\n\n"
        f"{schema_example}\n\n"
        "Use null for missing fields. Category must be one of: pwn, crypto, web, forensics, rev, misc.\n\n"
        f"Text to extract from:\n---\n{content[:8000]}\n---"
    )

    result = run_prompt(cfg, prompt, max_tokens=1024)
    raw = result["text"]
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(raw)


def _run_openai(
    prompt: str,
    model: str,
    api_key: str,
    base_url: str,
    max_tokens: int,
) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai package not installed. Run: pip install CTFx[llm]") from exc

    client = OpenAI(api_key=api_key, base_url=base_url)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
    )
    content = resp.choices[0].message.content
    if not content:
        raise RuntimeError("OpenAI-compatible provider returned empty content")
    return content


def _run_anthropic(
    prompt: str,
    model: str,
    api_key: str,
    base_url: str,
    max_tokens: int,
) -> str:
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError("anthropic package not installed. Run: pip install CTFx[llm]") from exc

    client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text
