#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Shape-aware mutation operators for ML-generated ndarrays (nested lists).

These functions port the mutation behaviour of the old ``NdArrayStatement``
(class-based test-case model) onto plain nested Python lists, so the
libcst-based ``MLTestFactory`` can mutate ndarray literals in place.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

import pynguin.configuration as config
import pynguin.utils.pynguinml.ml_parsing_utils as mlpu
from pynguin.utils import mutation_utils, randomness

if TYPE_CHECKING:
    from collections.abc import Callable

MLScalar = int | float | bool | complex


def replacement_value(np_dtype: str, low: float, high: float) -> MLScalar:
    """Draw a fresh leaf value for the given dtype within ``[low, high]``.

    Args:
        np_dtype: The numpy dtype name, e.g. ``"int32"``.
        low: The lower bound of the value range.
        high: The upper bound of the value range.

    Returns:
        A freshly drawn scalar value matching the dtype kind.
    """
    return _replacement_supplier(np.dtype(np_dtype).kind, low, high)(0)


def _replacement_supplier(
    np_dtype_kind: str, low: float, high: float
) -> Callable[[MLScalar], MLScalar]:
    """Build a per-leaf replacement supplier for the given dtype kind."""

    def supplier(element: MLScalar) -> MLScalar:
        if np_dtype_kind in {"i", "u"}:
            return randomness.next_int(int(low), int(high) + 1)
        if np_dtype_kind == "f":
            value = low + (high - low) * randomness.next_float()
            precision = randomness.next_int(0, 7)
            return round(value, precision)
        if np_dtype_kind == "c":
            real = low + (high - low) * randomness.next_float()
            imag = low + (high - low) * randomness.next_float()
            precision_real = randomness.next_int(0, 7)
            precision_imag = randomness.next_int(0, 7)
            return complex(round(real, precision_real), round(imag, precision_imag))
        if np_dtype_kind == "b":
            return randomness.next_bool()
        return element

    return supplier


def random_deletion(elements: list) -> tuple[list, bool]:
    """Randomly remove indices along one axis while keeping the shape valid.

    Args:
        elements: The nested list to mutate.

    Returns:
        A tuple of the (possibly new) nested list and whether it changed.
    """
    shape = mlpu.get_shape(elements)

    deletable_axes = [axis for axis, size in enumerate(shape) if size > 0]
    if not deletable_axes:
        return elements, False

    axis_index = randomness.next_int(0, len(deletable_axes))
    chosen_axis = deletable_axes[axis_index]

    axis_size = shape[chosen_axis]

    deletion_indices = [i for i in range(axis_size) if randomness.next_float() >= 0.5]

    if not deletion_indices:
        return elements, False

    deletion_indices.sort(reverse=True)

    return (
        mutation_utils.remove_indices_at_axis(elements, chosen_axis, deletion_indices),
        True,
    )


def random_replacement(elements: list, np_dtype: str, low: float, high: float) -> tuple[list, bool]:
    """Randomly replace leaf values while keeping the shape valid.

    Args:
        elements: The nested list to mutate.
        np_dtype: The numpy dtype name of the leaves.
        low: The lower bound of the value range.
        high: The upper bound of the value range.

    Returns:
        A tuple of the (possibly new) nested list and whether it changed.
    """
    shape = mlpu.get_shape(elements)
    if shape[-1] == 0:
        return elements, False

    total_leaves = math.prod(shape)
    p = max(1.0 / total_leaves**0.5, 0.05)

    supplier = _replacement_supplier(np.dtype(np_dtype).kind, low, high)
    return mutation_utils.apply_random_replacement(elements, p, supplier)


def random_insertion(elements: list, np_dtype: str, low: float, high: float) -> tuple[list, bool]:
    """Randomly insert fresh values while keeping the array rectangular.

    Args:
        elements: The nested list to mutate.
        np_dtype: The numpy dtype name of the leaves.
        low: The lower bound of the value range.
        high: The upper bound of the value range.

    Returns:
        A tuple of the (possibly new) nested list and whether it changed.
    """
    shape = mlpu.get_shape(elements)
    supplier = _replacement_supplier(np.dtype(np_dtype).kind, low, high)
    return mutation_utils.multiple_alpha_exponent_insertion(elements, shape, lambda: supplier(0))


def mutate_ndarray(elements: list, np_dtype: str, low: float, high: float) -> tuple[list, bool]:
    """Apply deletion/replacement/insertion mutations to a nested list.

    Reproduces the operator scheduling of the old ``CollectionStatement.mutate``:
    each operator fires with its configured probability, and the results are
    combined.

    Args:
        elements: The nested list to mutate.
        np_dtype: The numpy dtype name of the leaves.
        low: The lower bound of the value range.
        high: The upper bound of the value range.

    Returns:
        A tuple of the (possibly new) nested list and whether it changed.
    """
    changed = False
    if (
        randomness.next_float() < config.configuration.search_algorithm.test_delete_probability
        and len(elements) > 0
    ):
        elements, deleted = random_deletion(elements)
        changed |= deleted

    if (
        randomness.next_float() < config.configuration.search_algorithm.test_change_probability
        and len(elements) > 0
    ):
        elements, replaced = random_replacement(elements, np_dtype, low, high)
        changed |= replaced

    if randomness.next_float() < config.configuration.search_algorithm.test_insert_probability:
        elements, inserted = random_insertion(elements, np_dtype, low, high)
        changed |= inserted

    return elements, changed
