"""Standard library of components, registered by importing the submodules.

Built-ins use exactly the same registries a third-party plugin would; there is no private API.
Depends on ``core`` and ``llm`` only.
"""

from simulacrum.library import (  # noqa: F401  (imported for their registration side effects)
    actions,
    brains,
    environment,
    factions,
    generators,
    perturbations,
    systems,
)
