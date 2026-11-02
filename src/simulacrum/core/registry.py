"""Extension points.

Everything a user can add to a world is a named entry in one of these registries.
Ecosystem specs refer to entries by name; plugins register new ones with decorators.

    brains        fn(world, agent, rng, **brain_params) -> action | [actions] | None
    actions       fn(world, agent, action: dict, rng) -> None
    systems       fn(world, rng, **params) -> None            (aggregate rules, run each tick)
    env_agents    fn(world, rng, **params) -> None            (weather, seasons, signals ...)
    generators    fn(world, rng, **params) -> None            (fill world.terrain)
    perturbations PerturbationDef                              (user-injected external inputs)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from simulacrum.errors import UnknownComponentError

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


class Registry:
    def __init__(self, kind: str):
        self.kind = kind
        self._items: dict[str, Any] = {}

    def register(self, name: str) -> Callable[[T], T]:
        def deco(obj: T) -> T:
            self._items[name] = obj  # last registration wins, so plugins may override built-ins
            return obj

        return deco

    def get(self, name: str) -> Any:
        try:
            return self._items[name]
        except KeyError:
            raise UnknownComponentError(f"unknown {self.kind} {name!r}; registered: {sorted(self._items)}") from None

    def __contains__(self, name: str) -> bool:
        return name in self._items

    def names(self) -> list[str]:
        return sorted(self._items)

    def items(self):
        return self._items.items()


brains = Registry("brain")
actions = Registry("action")
systems = Registry("system")
env_agents = Registry("environment agent")
generators = Registry("generator")
perturbations = Registry("perturbation")


@dataclass
class PerturbationDef:
    """A typed external input. `params` drives both validation and the UI form.

    Param keys: type ("int"|"float"|"choice"), default, min, max, label,
    choices (list, or "@terrains" / "@agent_types"), role ("x"|"y" => filled by clicking the map).
    """

    name: str
    label: str
    description: str
    params: dict[str, dict[str, Any]]
    apply: Callable[..., str | None]  # apply(world, rng, **params) -> event text


def perturbation(
    name: str, label: str | None = None, description: str = "", params: dict[str, Any] | None = None
) -> Callable[[F], F]:
    def deco(fn: F) -> F:
        perturbations.register(name)(
            PerturbationDef(name, label or name.replace("_", " ").title(), description, params or {}, fn)
        )
        return fn

    return deco
