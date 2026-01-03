import pytest
from unittest.mock import MagicMock
from cascade.spec.physics import Token
from cascade.std.resource.continuous import continuous_broker, ContinuousLedger


async def test_continuous_broker_grants_memory():
    # Ledger: Total 16.0GB, Available 4.5GB
    ledger = ContinuousLedger(total=16.0, available=4.5)

    inputs = {
        "ledger_in": Token(payload=ledger),
        "req_in": Token(payload=2.1),  # Request 2.1GB
    }

    outputs = await continuous_broker(inputs, MagicMock())

    assert "gnt_out" in outputs
    assert outputs["gnt_out"].payload == 2.1

    updated = outputs["ledger_out"].payload
    # 4.5 - 2.1 = 2.4
    assert updated.available == pytest.approx(2.4)


async def test_continuous_broker_recirculates_large_request():
    # Ledger: Available 1.0GB
    ledger = ContinuousLedger(total=16.0, available=1.0)

    req_token = Token(payload=1.1)
    inputs = {"ledger_in": Token(payload=ledger), "req_in": req_token}

    outputs = await continuous_broker(inputs, MagicMock())

    assert "gnt_out" not in outputs
    assert outputs["req_out"] is req_token

    assert outputs["ledger_out"].payload.available == 1.0


async def test_continuous_broker_replenish_and_grant():
    # Ledger: Available 0.5. Request 1.5. Release 1.2.
    # Logic: 0.5 + 1.2 = 1.7. 1.7 >= 1.5. Grant.
    ledger = ContinuousLedger(total=16.0, available=0.5)

    inputs = {
        "ledger_in": Token(payload=ledger),
        "req_in": Token(payload=1.5),
        "rel_in": Token(payload=1.2),
    }

    outputs = await continuous_broker(inputs, MagicMock())

    assert "gnt_out" in outputs
    updated = outputs["ledger_out"].payload
    # 0.5 + 1.2 - 1.5 = 0.2
    assert updated.available == pytest.approx(0.2)
