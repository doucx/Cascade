from cascade.common.messaging import MessageStore, MessageBus


def test_message_store_loads_defaults():
    """Test that the message store loads default locale messages."""
    store = MessageStore(locale="en")
    # We expect some basic keys to be present from runtime_events.json
    # We don't check exact values to avoid brittleness, just key existence/format
    msg = store.get("run.started", target_tasks=["t1"])
    assert "t1" in msg


def test_message_bus_renderer_delegation():
    """Test that the bus delegates to the renderer."""
    store = MessageStore()
    store._messages["test.msg"] = "Value: {val}"
    bus = MessageBus(store)

    received = []

    class MockRenderer:
        def render(self, msg_id, level, **kwargs):
            received.append((msg_id, level, kwargs))

    bus.set_renderer(MockRenderer())

    bus.info("test.msg", val=42)

    assert len(received) == 1
    assert received[0][0] == "test.msg"
    assert received[0][1] == "info"
    assert received[0][2]["val"] == 42
