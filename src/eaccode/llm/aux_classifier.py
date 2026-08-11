"""Auxiliary classifier client (B.1) — bash risk classification for safeAuto.

The classifier is a provider flagged in providers.yaml with
``extra: {classifier: "true"}``. When no such provider exists (or the
call fails), ``classify_command`` returns None and the caller decides —
per the plan, safeAuto fails OPEN to the manual (ASK) path, it never
auto-allows on uncertainty.

The verdict prompt asks for strict JSON; parsing is tolerant (the
reasoning model may wrap it in fences).
"""

from __future__ import annotations

import json
import re
from typing import Any

CLASSIFIER_PROMPT = (
    "You are a shell-command risk classifier. Reply with ONLY a JSON object: "
    '{"verdict": "safe" | "risky", "reason": "<short english reason>"}. '
    'Safe = read-only or low-impact commands (ls, grep, pytest, git status, '
    'pip install of known packages). Risky = destructive, exfiltration, '
    'credential access, privilege escalation, or anything writing outside '
    'the project (rm -rf, curl | bash, base64 decode, chmod 777, ssh, '
    "wget to disk, echo > /etc/..., git push --force)."
)

CLASSIFIER_TIMEOUT_S = 10.0


def _classifier_provider() -> Any | None:
    """First provider flagged ``extra: {classifier: "true"}``, else None."""
    from eaccode.config.paths import EaccodePaths
    from eaccode.config.providers import load_providers

    providers = load_providers(EaccodePaths().providers_file)
    return next((p for p in providers if p.extra.get("classifier") == "true"),
                None)


def parse_verdict(text: str) -> str | None:
    """Extract 'safe'|'risky' from a (possibly fenced, noisy) LLM reply."""
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except ValueError:
        return None
    verdict = str(data.get("verdict", "")).strip().lower()
    return verdict if verdict in ("safe", "risky") else None


def classify_command(command: str, timeout: float = CLASSIFIER_TIMEOUT_S) -> str | None:
    """'safe' | 'risky' for *command*, or None when the aux model is
    unavailable — the caller must then fail open to manual approval."""
    provider = _classifier_provider()
    if provider is None:
        return None
    try:
        from litellm import completion

        resp = completion(
            model=provider.model,
            messages=[
                {"role": "system", "content": CLASSIFIER_PROMPT},
                {"role": "user", "content": f"Command: {command[:500]}"},
            ],
            api_key=provider.api_key.get_secret_value() if provider.api_key else None,
            base_url=provider.base_url or None,
            timeout=timeout,
            temperature=0,
            max_tokens=80,
        )
        text = resp.choices[0].message.content or ""
        return parse_verdict(text)
    except Exception:
        return None
