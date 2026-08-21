import pytest

from app.tools.policy_engine import evaluate


def test_policy_engine_evaluate_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="Policy evaluation is not implemented yet"):
        evaluate({"verification_result": "pending"})
