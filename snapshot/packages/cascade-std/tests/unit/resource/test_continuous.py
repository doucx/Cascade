import pytest
from unittest.mock import MagicMock
from cascade.spec.physics import Token
from cascade.std.resource.continuous import (
    continuous_allocator,
    continuous_reclaimer,
    ContinuousLedger,
)


async def test_continuous_allocator_grants_memory():
    # Ledger: Total 16.0GB, Available 4.5GB
    ledger = ContinuousLedger(total=16.0, available=4.5)

    inputs = {
        "ledger_in": Token(payload=ledger),
        "req_in": Token(payload=2.1),  # Request 2.1GB
    }

    outputs = await continuous_allocator(inputs, MagicMock())

    assert "gnt_out" in outputs
    assert outputs["gnt_out"].payload == 2.1

    updated = outputs["ledger_out"].payload
    # 4.5 - 2.1 = 2.4
    assert updated.available == pytest.approx(2.4)


async def test_continuous_allocator_recirculates_large_request():
    # Ledger: Available 1.0GB
    ledger = ContinuousLedger(total=16.0, available=1.0)

    req_token = Token(payload=1.1)
    inputs = {"ledger_in": Token(payload=ledger), "req_in": req_token}

    outputs = await continuous_allocator(inputs, MagicMock())

    assert "gnt_out" not in outputs
    assert outputs["req_out"] is req_token

    assert outputs["ledger_out"].payload.available == 1.0


async def test_continuous_reclaimer_replenish():
    # Ledger: Available 0.5. Release 1.2.
    ledger = ContinuousLedger(total=16.0, available=0.5)

    inputs = {
        "ledger_in": Token(payload=ledger),
        "rel_in": Token(payload=1.2),
    }

    outputs = await continuous_reclaimer(inputs, MagicMock())

    updated = outputs["ledger_out"].payload
    assert updated.available == pytest.approx(1.7)
