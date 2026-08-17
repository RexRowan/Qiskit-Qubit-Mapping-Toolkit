import qiskit_qubit_mapping as qqm


def test_public_api_importable():
    assert hasattr(qqm, "IsomorphismLayout")
    assert hasattr(qqm, "WalkBasedLayout")
    assert hasattr(qqm, "BaselineSwapRouter")
    assert hasattr(qqm, "LookaheadSwapRouter")


def test_version_is_a_string():
    assert isinstance(qqm.__version__, str)
