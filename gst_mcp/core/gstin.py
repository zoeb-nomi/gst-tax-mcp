"""GSTIN parsing and checksum validation (mod-36 algorithm per GSTN spec)."""
from __future__ import annotations

import re

_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_FORMAT = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


def checksum_char(first14: str) -> str:
    """Compute the 15th (checksum) character of a GSTIN.

    Modulus-36 Luhn variant: alternating weights 1,2,1,2 from the left,
    product folded as product//36 + product%36, checksum = (36 - sum%36) % 36.
    """
    if len(first14) != 14 or any(c not in _CHARS for c in first14):
        raise ValueError("first 14 characters must be valid GSTIN characters")
    total = 0
    for i, ch in enumerate(first14):
        product = _CHARS.index(ch) * (2 if i % 2 == 1 else 1)
        total += product // 36 + product % 36
    return _CHARS[(36 - (total % 36)) % 36]


def validate_gstin(gstin: str) -> dict:
    """Validate format + checksum; parse state code, PAN and entity code."""
    raw = (gstin or "").strip().upper()
    result = {"gstin": raw, "valid": False, "errors": []}
    if len(raw) != 15:
        result["errors"].append(f"length is {len(raw)}, expected 15")
        return result
    if not _FORMAT.match(raw):
        result["errors"].append("format mismatch: expected 2 digits, 5 letters, 4 digits, "
                                "letter, alphanumeric, Z, alphanumeric")
        return result
    if checksum_char(raw[:14]) != raw[14]:
        result["errors"].append("checksum character mismatch")
        return result
    from .data import STATE_CODES
    result.update({
        "valid": True,
        "state_code": raw[:2],
        "state_name": STATE_CODES.get(raw[:2], "unknown"),
        "pan": raw[2:12],
        "entity_number": raw[12],
        "errors": [],
    })
    return result
