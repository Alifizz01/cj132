# -*- coding: utf-8 -*-
"""Panel substrate model.

A *substrate* is the physical board a solar panel is built on (here an aluminium
honeycomb sandwich). For the thermal model it contributes four optical
properties (front/rear solar absorptivity ``alpha`` and infrared emissivity
``epsilon``) and a through-thickness conduction term derived from its thermal
``conductivity`` and ``thickness``.

This module gives those raw JSON fields a named, typed home (a dataclass) and a
single derived quantity, ``c_cond = conductivity / thickness`` [W/m^2K], which is
exactly the conduction coefficient the 2-node thermal balance needs.

The JSON schema (see ``data/substrates/*.json``) matches the legacy
``datamgmt.getSubstrateData`` reader::

    {"name", "alpha_front", "alpha_rear", "conductivity",
     "epsilon_front", "epsilon_rear", "thickness"}

Status: standalone (numpy/stdlib only) — importable and tested in isolation.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Substrate:
    """Immutable optical + thermal properties of a panel substrate.

    Attributes
    ----------
    name
        Human-readable identifier, e.g. ``"SRP MSRO Case 2"``.
    alpha_front, alpha_rear
        Solar absorptivity of the front/rear face (0-1).
    epsilon_front, epsilon_rear
        Infrared emissivity of the front/rear face (0-1).
    conductivity
        Through-thickness thermal conductivity [W/(m*K)].
    thickness
        Substrate thickness [m].
    """

    name: str
    alpha_front: float
    alpha_rear: float
    epsilon_front: float
    epsilon_rear: float
    conductivity: float
    thickness: float

    @property
    def c_cond(self) -> float:
        """Front<->rear conduction coefficient [W/(m^2*K)] = conductivity / thickness."""
        if self.thickness <= 0:
            raise ValueError("substrate thickness must be > 0, got %r" % self.thickness)
        return self.conductivity / self.thickness


_REQUIRED = (
    "name", "alpha_front", "alpha_rear",
    "epsilon_front", "epsilon_rear", "conductivity", "thickness",
)


def from_dict(cfg: dict) -> Substrate:
    """Build a :class:`Substrate` from a raw config dict, validating keys early."""
    missing = [k for k in _REQUIRED if k not in cfg]
    if missing:
        raise KeyError("substrate config missing keys: %s" % ", ".join(missing))
    return Substrate(
        name=str(cfg["name"]),
        alpha_front=float(cfg["alpha_front"]),
        alpha_rear=float(cfg["alpha_rear"]),
        epsilon_front=float(cfg["epsilon_front"]),
        epsilon_rear=float(cfg["epsilon_rear"]),
        conductivity=float(cfg["conductivity"]),
        thickness=float(cfg["thickness"]),
    )


def load_substrate(name: str, local_file: bool = False) -> Substrate:
    """Load a substrate by catalogue name (``data/substrates/<name>.json``).

    Parameters
    ----------
    name
        Catalogue name (without ``.json``), or a path stem if ``local_file``.
    local_file
        If True, read ``<name>.json`` from the working directory instead of the
        packaged ``data/substrates`` folder.
    """
    if local_file:
        path = name + ".json"
    else:
        path = os.path.join(os.path.dirname(__file__), "..", "data", "substrates", name + ".json")
    with open(path, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    return from_dict(cfg)
