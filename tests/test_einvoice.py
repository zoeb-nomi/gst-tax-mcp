import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gst_mcp.core.einvoice import validate_einvoice

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "priya_pickles"


def _load(name):
    return json.loads((FIXTURES / name).read_text())


def test_valid_einvoice_passes():
    out = validate_einvoice(_load("einvoice_meridian.json"), supplier_ato=6_20_00_000)
    assert out["valid"], out["errors"]
    assert out["hsn_digits_required"] == 6


def test_broken_einvoice_catches_errors():
    out = validate_einvoice(_load("einvoice_meridian_broken.json"), supplier_ato=6_20_00_000)
    assert not out["valid"]
    joined = " | ".join(out["errors"])
    assert "checksum" in joined
    assert "6 digits" in joined
    assert "total_invoice_value" in joined


def test_below_threshold_needs_only_4_digits():
    out = validate_einvoice(_load("einvoice_meridian.json"), supplier_ato=90_00_000)
    assert out["hsn_digits_required"] == 4
    assert out["valid"], out["errors"]
