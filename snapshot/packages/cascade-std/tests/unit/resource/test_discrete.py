from unittest.mock import MagicMock
from cascade.spec.physics import Token
from cascade.std.resource.discrete import (
    discrete_allocator,
    discrete_reclaimer,
    DiscreteLedger,
)


async def test_discrete_allocator_grants_when_available():
    # Ledger: Total 10, Available 5
    ledger = DiscreteLedger(total=10, available=5)

    inputs = {"ledger_in": Token(payload=ledger), "req_in": Token(payload=2)}

    outputs = await discrete_allocator(inputs, MagicMock())

    # Check Grant
    assert "gnt_out" in outputs
    assert outputs["gnt_out"].payload == 2

    # Check Ledger Update
    updated_ledger = outputs["ledger_out"].payload
    assert updated_ledger.available == 3
    assert "req_out" not in outputs


async def test_discrete_allocator_recirculates_when_starved():
    # Ledger: Total 10, Available 1
    ledger = DiscreteLedger(total=10, available=1)

    req_token = Token(payload=5)
    inputs = {"ledger_in": Token(payload=ledger), "req_in": req_token}

    outputs = await discrete_allocator(inputs, MagicMock())

    # Check No Grant
    assert "gnt_out" not in outputs

    # Check Recirculation
    assert "req_out" in outputs
    assert outputs["req_out"] is req_token  # Identity check

    # Check Ledger Unchanged
    updated_ledger = outputs["ledger_out"].payload
    assert updated_ledger.available == 1


async def test_discrete_reclaimer_releases_resource():
    # Ledger: Total 10, Available 5
    ledger = DiscreteLedger(total=10, available=5)

    inputs = {"ledger_in": Token(payload=ledger), "rel_in": Token(payload=3)}

    outputs = await discrete_reclaimer(inputs, MagicMock())

    # Check Ledger Update
    updated_ledger = outputs["ledger_out"].payload
    assert updated_ledger.available == 8


async def test_sequential_rel_and_req():
    # 模拟物理场中的顺序执行
    ledger = DiscreteLedger(total=10, available=2)
    mock_node = MagicMock()

    # 1. Reclaimer fires first
    rel_outputs = await discrete_reclaimer(
        {"ledger_in": Token(payload=ledger), "rel_in": Token(payload=3)}, mock_node
    )
    new_ledger = rel_outputs["ledger_out"].payload

    # 2. Allocator fires second using the new ledger
    alloc_outputs = await discrete_allocator(
        {"ledger_in": Token(payload=new_ledger), "req_in": Token(payload=4)}, mock_node
    )

    # Check Grant
    assert "gnt_out" in alloc_outputs
    assert alloc_outputs["ledger_out"].payload.available == 1
