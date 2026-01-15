# Thin wrapper for backward compatibility
from cascade.bus.feedback import FeedbackBus, MessageStore, bus

__all__ = ["bus", "FeedbackBus", "MessageStore"]