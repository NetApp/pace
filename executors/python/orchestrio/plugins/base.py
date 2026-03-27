# Copyright 2026 NetApp, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Plugin base class and registry."""

from __future__ import annotations

import abc
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from orchestrio.models import StepDefinition, StepResult

# ── Global registry ────────────────────────────────────────────────

_registry: dict[str, type[StepPlugin]] = {}


class StepPlugin(abc.ABC):
    """Abstract base for all step execution plugins.

    Subclasses implement *execute* for a specific step type and
    register themselves via the ``@StepPlugin.register`` decorator.
    """

    @abc.abstractmethod
    async def execute(
        self,
        step: StepDefinition,
        context: dict[str, Any],
    ) -> StepResult:
        """Run the step and return a result."""
        ...

    # ── Registration helpers ───────────────────────────────────────

    @classmethod
    def register(cls, step_type: str):
        """Class decorator that registers a plugin under *step_type*."""
        def decorator(plugin_cls: type[StepPlugin]) -> type[StepPlugin]:
            _registry[step_type] = plugin_cls
            return plugin_cls
        return decorator


def get_plugin(step_type: str) -> StepPlugin:
    """Instantiate and return the plugin for *step_type*."""
    if step_type not in _registry:
        raise ValueError(
            f"No plugin registered for step type '{step_type}'. "
            f"Available: {list(_registry.keys())}"
        )
    return _registry[step_type]()


def list_plugins() -> list[str]:
    """Return all registered plugin type names."""
    return list(_registry.keys())
