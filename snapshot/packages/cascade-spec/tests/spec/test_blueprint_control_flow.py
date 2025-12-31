import pytest
from dataclasses import is_dataclass
from cascade.spec.blueprint import Instruction, Jump, JumpIfFalse, Register

def test_control_flow_instructions_structure():
    """
    Verify that control flow instructions are defined and follow the Instruction protocol.
    This defines the contract for Phase 6 (Feature Parity).
    """
    # 1. Jump (Unconditional)
    # Should hold a relative offset (int)
    jump = Jump(offset=5)
    assert isinstance(jump, Instruction)
    assert is_dataclass(jump)
    assert jump.offset == 5

    # 2. JumpIfFalse (Conditional)
    # Should hold a condition register and a relative offset
    cond_reg = Register(0)
    jump_if = JumpIfFalse(condition=cond_reg, offset=10)
    assert isinstance(jump_if, Instruction)
    assert is_dataclass(jump_if)
    assert jump_if.condition == cond_reg
    assert jump_if.offset == 10