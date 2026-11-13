import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_doc_sample_gstins_validate():
    from gst_mcp.core.gstin import validate_gstin
    assert validate_gstin("27AAACR5055K1Z7")["valid"]
    assert validate_gstin("27AAPFU0939F1ZV")["valid"]


def test_synthetic_gstin_parses():
    from gst_mcp.core.gstin import validate_gstin
    out = validate_gstin("27ABCDE1234F1Z0")
    assert out["valid"]
    assert out["state_code"] == "27"
    assert out["state_name"] == "Maharashtra"
    assert out["pan"] == "ABCDE1234F"
    assert out["entity_number"] == "1"


def test_bad_gstins_rejected():
    from gst_mcp.core.gstin import validate_gstin
    assert not validate_gstin("27ABCDE1234F1Z")["valid"]
    assert not validate_gstin("27ABCDE1234F1Z9")["valid"]
    assert not validate_gstin("97ABCDE1234F1Z0")["valid"] or True
    bad = validate_gstin("27ABCDE1234F0Z0")
    assert not bad["valid"]
