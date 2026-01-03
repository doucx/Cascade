import pytest
from unittest.mock import MagicMock
from cascade.spec.physics import Token
from cascade.std.resource.continuous import (
    continuous_allocator,
    continuous_reclaimer,
    ContinuousLedger,
)


@pytest.fixture
def partial_ledger() -> ContinuousLedger:
    """Ledger with 16.0 total, 4.5 available."""
    return ContinuousLedger(total=16.0, available=4.5)


@pytest.fixture
def starved_ledger() -> ContinuousLedger:
    """Ledger with 16.0 total, 1.0 available."""
    return ContinuousLedger(total=16.0, available=1.0)


async def test_continuous_allocator_grants_memory(partial_ledger):
    inputs = {
        "ledger_in": Token(payload=partial_ledger),
        "req_in": Token(payload=2.1),
    }
    outputs = await continuous_allocator(inputs, MagicMock(), MagicMock())

    assert "gnt_out" in outputs
    assert outputs["gnt_out"].payload == 2.1
    updated = outputs["ledger_out"].payload
    assert updated.available == pytest.approx(2.4)


async def test_continuous_allocator_recirculates_large_request(starved_ledger):
    req_token = Token(payload=1.1)
    inputs = {"ledger_in": Token(payload=starved_ledger), "req_in": req_token}
    outputs = await continuous_allocator(inputs, MagicMock(), MagicMock())

    assert "gnt_out" not in outputs
    assert outputs["req_out"] is req_token
    assert outputs["ledger_out"].payload.available == 1.0


async def test_continuous_reclaimer_replenish():
    ledger = ContinuousLedger(total=16.0, available=0.5)
    inputs = {"ledger_in": Token(payload=ledger), "rel_in": Token(payload=1.2)}
    outputs = await continuous_reclaimer(inputs, MagicMock(), MagicMock())

    updated = outputs["ledger_out"].payload
    assert updated.available == pytest.approx(1.7)