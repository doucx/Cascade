import pytest
from unittest.mock import MagicMock
from cascade.spec.physics import Token
from cascade.std.resource.discrete import discrete_broker, DiscreteLedger

async def test_discrete_broker_grants_when_available():
    # Ledger: Total 10, Available 5
    ledger = DiscreteLedger(total=10, available=5)
    
    inputs = {
        "ledger_in": Token(payload=ledger),
        "req_in": Token(payload=2)
    }
    
    outputs = await discrete_broker(inputs, MagicMock())
    
    # Check Grant
    assert "gnt_out" in outputs
    assert outputs["gnt_out"].payload == 2
    
    # Check Ledger Update
    updated_ledger = outputs["ledger_out"].payload
    assert updated_ledger.available == 3
    assert "req_out" not in outputs

async def test_discrete_broker_recirculates_when_starved():
    # Ledger: Total 10, Available 1
    ledger = DiscreteLedger(total=10, available=1)
    
    req_token = Token(payload=5)
    inputs = {
        "ledger_in": Token(payload=ledger),
        "req_in": req_token
    }
    
    outputs = await discrete_broker(inputs, MagicMock())
    
    # Check No Grant
    assert "gnt_out" not in outputs
    
    # Check Recirculation
    assert "req_out" in outputs
    assert outputs["req_out"] is req_token # Identity check
    
    # Check Ledger Unchanged
    updated_ledger = outputs["ledger_out"].payload
    assert updated_ledger.available == 1

async def test_discrete_broker_releases_resource():
    # Ledger: Total 10, Available 5
    ledger = DiscreteLedger(total=10, available=5)
    
    inputs = {
        "ledger_in": Token(payload=ledger),
        "rel_in": Token(payload=3)
    }
    
    outputs = await discrete_broker(inputs, MagicMock())
    
    # Check Ledger Update
    updated_ledger = outputs["ledger_out"].payload
    assert updated_ledger.available == 8

async def test_discrete_broker_simultaneous_rel_and_req():
    # Ledger: Available 2. Request 4. Release 3.
    # Logic: Release happens first, so Available becomes 2+3=5. Then Request 4 succeeds.
    ledger = DiscreteLedger(total=10, available=2)
    
    inputs = {
        "ledger_in": Token(payload=ledger),
        "req_in": Token(payload=4),
        "rel_in": Token(payload=3)
    }
    
    outputs = await discrete_broker(inputs, MagicMock())
    
    # Check Grant
    assert "gnt_out" in outputs
    
    # Check Ledger: 2 + 3 - 4 = 1
    updated_ledger = outputs["ledger_out"].payload
    assert updated_ledger.available == 1