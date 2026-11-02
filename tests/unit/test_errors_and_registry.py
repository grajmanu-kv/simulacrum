from __future__ import annotations

import pytest

from simulacrum.core.registry import Registry, brains
from simulacrum.errors import (
    PerturbationError,
    PluginSecurityError,
    ProviderConfigError,
    ReplayMismatch,
    SimulacrumError,
    UnknownComponentError,
)


def test_domain_errors_stay_compatible_with_builtin_handlers() -> None:
    assert issubclass(UnknownComponentError, KeyError)
    assert issubclass(PerturbationError, ValueError)
    assert issubclass(PluginSecurityError, PermissionError)
    assert issubclass(ReplayMismatch, RuntimeError)
    assert issubclass(ProviderConfigError, RuntimeError)
    assert all(issubclass(e, SimulacrumError) for e in (UnknownComponentError, PerturbationError, ReplayMismatch))


def test_unknown_component_message_lists_what_is_registered() -> None:
    with pytest.raises(UnknownComponentError) as exc:
        brains.get("no_such_brain")
    msg = str(exc.value)
    assert "no_such_brain" in msg and "grazer" in msg
    assert not msg.startswith(("'", '"'))  # KeyError would have wrapped it in quotes


def test_last_registration_wins_so_plugins_can_override() -> None:
    reg = Registry("thing")
    reg.register("a")(1)
    reg.register("a")(2)
    assert reg.get("a") == 2 and "a" in reg and reg.names() == ["a"]
