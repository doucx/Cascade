import pytest
from cascade.foundation.identity.fingerprint import Fingerprint, InvalidFingerprintKeyError

def test_fingerprint_validation():
    # Valid key
    fp = Fingerprint()
    fp["baseline_code_structure_hash"] = "abc1234"
    assert fp["baseline_code_structure_hash"] == "abc1234"

    # Invalid keys
    with pytest.raises(InvalidFingerprintKeyError):
        fp["invalid_key"] = "val"
    
    with pytest.raises(InvalidFingerprintKeyError):
        fp["baseline_code_structure_text"] = "val" # ends with text, but middle is wrong

def test_fingerprint_immutability_simulation():
    # Fingerprints should support dict-like operations but validate on every step
    data = {"baseline_code_structure_hash": "hash1"}
    fp = Fingerprint.from_dict(data)
    
    assert "baseline_code_structure_hash" in fp
    assert fp.get("baseline_code_structure_hash") == "hash1"
    
    # Export
    exported = fp.to_dict()
    assert exported == data
    assert exported is not fp._hashes  # Should be a copy