from cascade.interfaces.spec.common import Param


def test_param_placeholder():
    p = Param("env", default="dev")
    assert p.name == "env"
    assert p.default == "dev"
