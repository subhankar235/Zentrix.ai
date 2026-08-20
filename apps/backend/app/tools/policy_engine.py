"""Deterministic policy interface for guarded optimization deployment.

The rule implementation is intentionally deferred to the policy-engine step.
Agents may import this module now, but no policy decision is available until
those rules are implemented.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, NoReturn


def evaluate(verification_result: Mapping[str, Any]) -> NoReturn:
    """Evaluate verification evidence against deployment policy.

    This placeholder must not approve or block a deployment.  The complete
    deterministic rule set will be added in Feature 2.
    """
    raise NotImplementedError("Policy evaluation is not implemented yet")
