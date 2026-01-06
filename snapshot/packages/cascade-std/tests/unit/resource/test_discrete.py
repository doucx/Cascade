import pytest
from unittest.mock import MagicMock
from cascade.spec.physical.nodes import Token
from cascade.std.resource.discrete import (
    discrete_allocator,
    discrete_reclaimer,
    DiscreteLedger,
)


@pytest.fixture
def available_ledger() -> DiscreteLedger:
    return DiscreteLedger(total=10, available=5)


@pytest.fixture
def starved_ledger() -> DiscreteLedger:
    return DiscreteLedger(total=10, available=1)


def test_discrete_allocator_grants_when_available(available_ledger):
    inputs = {"ledger_in": Token(payload=available_ledger), "req_in": Token(payload=2)}
    outputs = discrete_allocator(inputs, MagicMock(), MagicMock())

    assert "gnt_out" in outputs
    assert outputs["gnt_out"].payload == 2
    updated_ledger = outputs["ledger_out"].payload
    assert updated_ledger.available == 3
    assert "req_out" not in outputs


def test_discrete_allocator_recirculates_when_starved(starved_ledger):
    req_token = Token(payload=5)
    inputs = {"ledger_in": Token(payload=starved_ledger), "req_in": req_token}
    outputs = discrete_allocator(inputs, MagicMock(), MagicMock())

    assert "gnt_out" not in outputs
    assert "req_out" in outputs
    assert outputs["req_out"] is req_token
    updated_ledger = outputs["ledger_out"].payload
    assert updated_ledger.available == 1


def test_discrete_reclaimer_releases_resource(available_ledger):
    inputs = {"ledger_in": Token(payload=available_ledger), "rel_in": Token(payload=3)}
    outputs = discrete_reclaimer(inputs, MagicMock(), MagicMock())

    updated_ledger = outputs["ledger_out"].payload
    assert updated_ledger.available == 8


def test_sequential_rel_and_req():
    ledger = DiscreteLedger(total=10, available=2)
    mock_node = MagicMock()
    mock_resources = MagicMock()

    rel_outputs = discrete_reclaimer(
        {"ledger_in": Token(payload=ledger), "rel_in": Token(payload=3)},
        mock_node,
        mock_resources,
    )
    new_ledger = rel_outputs["ledger_out"].payload

    alloc_outputs = discrete_allocator(
        {"ledger_in": Token(payload=new_ledger), "req_in": Token(payload=4)},
        mock_node,
        mock_resources,
    )

    assert "gnt_out" in alloc_outputs
    assert alloc_outputs["ledger_out"].payload.available == 1
