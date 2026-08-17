"""Qiskit transpiler stage plugins.

This module wires the toolkit's layout and routing passes into Qiskit's
:class:`~qiskit.transpiler.preset_passmanagers.plugin.PassManagerStagePlugin`
interface, so they're usable directly through :func:`qiskit.transpile`
without importing anything from this package:

.. code-block:: python

    from qiskit import transpile

    transpiled = transpile(
        circuit,
        coupling_map=coupling_map,
        layout_method="qqm_isomorphism",
        routing_method="qqm_lookahead",
    )

The plugins are registered via setuptools entry points in ``pyproject.toml``
under the ``qiskit.transpiler.layout`` and ``qiskit.transpiler.routing``
namespaces, and become discoverable once the package is installed (no
import of this module is required by the user):

.. code-block:: python

    from qiskit.transpiler.preset_passmanagers.plugin import list_stage_plugins

    list_stage_plugins("layout")    # includes "qqm_isomorphism", "qqm_walk_based"
    list_stage_plugins("routing")   # includes "qqm_baseline", "qqm_lookahead"

Plugin names are prefixed with ``qqm_`` (qiskit-qubit-mapping) rather than
using the toolkit's plain class names, because entry point names are global
across every installed package and several natural names collide with
Qiskit's own built-in plugins -- most notably ``"lookahead"``, which is
already a reserved built-in routing method name (alongside ``"sabre"``,
``"basic"``, ``"default"``, and ``"none"``; the built-in layout stage
similarly reserves ``"trivial"``, ``"dense"``, ``"sabre"``, and
``"default"``).
"""

from __future__ import annotations

from qiskit.transpiler import PassManager
from qiskit.transpiler.exceptions import TranspilerError
from qiskit.transpiler.preset_passmanagers import common
from qiskit.transpiler.preset_passmanagers.plugin import PassManagerStagePlugin

from qiskit_qubit_mapping.layout import IsomorphismLayout, WalkBasedLayout
from qiskit_qubit_mapping.routing import BaselineSwapRouter, LookaheadSwapRouter


def _require_coupling_map(pass_manager_config, plugin_name: str):
    coupling_map = pass_manager_config.coupling_map
    if coupling_map is None:
        raise TranspilerError(
            f"The '{plugin_name}' plugin requires a coupling map. Pass one "
            "explicitly via transpile(circuit, coupling_map=..., ...) or "
            "target a backend that provides one."
        )
    return coupling_map


class _LayoutPluginBase(PassManagerStagePlugin):
    """Shared implementation for the toolkit's layout stage plugins.

    Subclasses set ``layout_pass_cls`` to one of this package's
    ``AnalysisPass`` layout heuristics. The returned pass manager runs
    that heuristic to populate ``property_set["layout"]``, then appends
    Qiskit's standard embedding sequence
    (:func:`~qiskit.transpiler.preset_passmanagers.common.generate_embed_passmanager`)
    to actually expand the circuit to the coupling map's full physical
    width and allocate ancillas -- matching what every built-in layout
    stage plugin does, and what the layout stage of ``transpile()``'s
    pipeline expects to receive.
    """

    layout_pass_cls: type = None

    def pass_manager(self, pass_manager_config, optimization_level=None) -> PassManager:
        coupling_map = _require_coupling_map(pass_manager_config, type(self).__name__)
        layout_pm = PassManager([self.layout_pass_cls(coupling_map)])
        layout_pm += common.generate_embed_passmanager(coupling_map)
        return layout_pm


class IsomorphismLayoutPlugin(_LayoutPluginBase):
    """Layout stage plugin wrapping :class:`~qiskit_qubit_mapping.layout.IsomorphismLayout`.

    Registered as ``"qqm_isomorphism"`` under the ``qiskit.transpiler.layout``
    entry point group.
    """

    layout_pass_cls = IsomorphismLayout


class WalkBasedLayoutPlugin(_LayoutPluginBase):
    """Layout stage plugin wrapping :class:`~qiskit_qubit_mapping.layout.WalkBasedLayout`.

    Registered as ``"qqm_walk_based"`` under the ``qiskit.transpiler.layout``
    entry point group.
    """

    layout_pass_cls = WalkBasedLayout


class _RoutingPluginBase(PassManagerStagePlugin):
    """Shared implementation for the toolkit's routing stage plugins.

    Subclasses set ``router_pass_cls`` to one of this package's
    ``TransformationPass`` routers. Unlike the layout stage, routing
    stage plugins don't need any additional embedding step -- the
    incoming circuit is already at full physical width by the time
    routing runs.
    """

    router_pass_cls: type = None

    def pass_manager(self, pass_manager_config, optimization_level=None) -> PassManager:
        coupling_map = _require_coupling_map(pass_manager_config, type(self).__name__)
        return PassManager([self.router_pass_cls(coupling_map)])


class BaselineSwapRouterPlugin(_RoutingPluginBase):
    """Routing stage plugin wrapping :class:`~qiskit_qubit_mapping.routing.BaselineSwapRouter`.

    Registered as ``"qqm_baseline"`` under the ``qiskit.transpiler.routing``
    entry point group.
    """

    router_pass_cls = BaselineSwapRouter


class LookaheadSwapRouterPlugin(_RoutingPluginBase):
    """Routing stage plugin wrapping :class:`~qiskit_qubit_mapping.routing.LookaheadSwapRouter`.

    Registered as ``"qqm_lookahead"`` under the ``qiskit.transpiler.routing``
    entry point group. This is the toolkit's strongest routing option --
    see ``docs/algorithm_notes.md`` for measured comparisons against Sabre.
    """

    router_pass_cls = LookaheadSwapRouter
