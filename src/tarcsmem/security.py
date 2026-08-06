"""Dependency-light security gates for enterprise memory ingestion.

The default policy blocks likely credentials and redacts common PII before a
record reaches durable storage. Optional external DLP/PII products can replace
the detector without changing the GuardWrite contract.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass


class SecurityViolation(ValueError):
    """Raised when content is unsafe to persist even as pending memory."""


@dataclass(frozen=True, slots=True)
class SecurityFinding:
    category: str
    start: int
    end: int
    severity: str


@dataclass(frozen=True, slots=True)
class SecurityDecision:
    allowed: bool
    text: str
    counts: dict[str, int]
    redacted: bool
    reason: str


_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("private_key", "critical", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("openai_api_key", "critical", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")),
    ("github_token", "critical", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("aws_access_key", "critical", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    (
        "assigned_secret",
        "critical",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|secret|password)\s*[:=]\s*"
            r"['\"]?[A-Za-z0-9_./+=-]{12,}"
        ),
    ),
    ("email", "high", re.compile(r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("cn_mobile", "high", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    (
        "cn_identity_number",
        "critical",
        re.compile(
            r"(?<!\d)\d{6}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[0-9Xx](?!\d)"
        ),
    ),
)

_SECRET_CATEGORIES = {
    "private_key",
    "openai_api_key",
    "github_token",
    "aws_access_key",
    "assigned_secret",
}


def scan_sensitive_text(text: str) -> list[SecurityFinding]:
    """Return locations and types only; never include matched sensitive values."""
    findings: list[SecurityFinding] = []
    occupied: list[tuple[int, int]] = []
    for category, severity, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.span()
            if any(start < prior_end and prior_start < end for prior_start, prior_end in occupied):
                continue
            findings.append(SecurityFinding(category, start, end, severity))
            occupied.append((start, end))
    return sorted(findings, key=lambda item: (item.start, item.end))


def _redact(text: str, findings: list[SecurityFinding]) -> str:
    rendered = text
    for finding in sorted(findings, key=lambda item: item.start, reverse=True):
        marker = f"[REDACTED_{finding.category.upper()}]"
        rendered = rendered[: finding.start] + marker + rendered[finding.end :]
    return rendered


class SecurityGate:
    """Apply a small, deterministic DLP policy before durable memory writes.

    Modes:
    - ``redact`` (default): block credentials, redact detected PII.
    - ``reject``: block any sensitive finding.
    - ``audit``: record counts but keep text unchanged (development only).
    - ``off``: disable this reference gate; an external gate must take over.
    """

    def __init__(self, mode: str = "redact") -> None:
        normalized = mode.strip().lower()
        if normalized not in {"redact", "reject", "audit", "off"}:
            raise ValueError("security mode must be redact, reject, audit, or off")
        self.mode = normalized

    @classmethod
    def from_environment(cls) -> SecurityGate:
        return cls(os.getenv("TARCSMEM_SECURITY_MODE", "redact"))

    def evaluate(self, text: str) -> SecurityDecision:
        if self.mode == "off":
            return SecurityDecision(True, text, {}, False, "security gate delegated")
        findings = scan_sensitive_text(text)
        counts = dict(Counter(item.category for item in findings))
        if not findings:
            return SecurityDecision(True, text, {}, False, "no sensitive pattern detected")
        has_secret = any(item.category in _SECRET_CATEGORIES for item in findings)
        if has_secret or self.mode == "reject":
            return SecurityDecision(
                False,
                "",
                counts,
                False,
                "credential-like content detected" if has_secret else "sensitive content rejected",
            )
        if self.mode == "audit":
            return SecurityDecision(True, text, counts, False, "audit-only finding")
        return SecurityDecision(True, _redact(text, findings), counts, True, "PII redacted")
