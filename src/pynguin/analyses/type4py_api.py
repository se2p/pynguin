#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Interact with Type4Py API."""

from __future__ import annotations

import logging
import typing

import requests

import pynguin.configuration as config


# Try to add some type information to model a response from Type4Py.
# Full layout here: https://github.com/saltudelft/type4py/wiki/Using-Type4Py-Rest-API
class Type4pyData(typing.TypedDict):
    """Model Type4Py Response."""

    error: str
    response: Type4pyResponse


class Type4pyResponse(typing.TypedDict):
    """Model Type4Py Response."""

    classes: list[Type4pyClassData]
    funcs: list[Type4pyFunctionData]


class Type4pyClassData(typing.TypedDict):
    """Model Type4Py Response."""

    funcs: list[Type4pyFunctionData]
    name: str
    q_name: str


class Type4pyFunctionData(typing.TypedDict):
    """Model Type4Py Response."""

    name: str
    q_name: str
    # List of predicted return types with confidence value
    ret_type_p: list[tuple[str, float]]
    # List of predicted return types with confidence value
    params_p: dict[str, list[tuple[str, float]]]


def find_predicted_signature(
    data: Type4pyData | None, q_func_name: str, q_class_name: str | None = None
) -> Type4pyFunctionData | None:
    """Find function data for given class/function.

    Args:
        data: The data to search in
        q_func_name: the fully qualified function name
        q_class_name: the fully qualified class name

    Returns:
        The found data or None
    """
    if data is None or data["error"] is not None:
        return None

    search_in: Type4pyResponse | Type4pyClassData = data["response"]
    if q_class_name is not None:
        search_in = _find_class(search_in, q_class_name)
        if search_in is None:
            return None

    # TODO(fk) there can be multiple signatures for overloaded functions...
    return _find_func(search_in, q_func_name)


def _find_class(data: Type4pyResponse, q_class_name: str) -> Type4pyClassData | None:
    for klass in data["classes"]:
        if klass["q_name"] == q_class_name:
            return klass
    return None


def _find_func(
    data: Type4pyResponse | Type4pyClassData, q_func_name: str
) -> Type4pyFunctionData | None:
    for func in data["funcs"]:
        if func["q_name"] == q_func_name:
            return func
    return None


LOGGER = logging.getLogger(__name__)


def query_type4py_api(module_name: str, source_code: str) -> Type4pyData | None:
    """Query the configured Type4Py Server for predicted signatures.

    Args:
        module_name: the name of the module
        source_code: the source code of the module

    Returns:
        The response from Type4Py.
    """
    try:
        LOGGER.info("Retrieving Type4Py data for %s", module_name)
        # param tc=0 -> No type checks (currently not implemented by Type4Py)
        # param fp=0 -> Don't filter resulting types based on existing imports
        return requests.post(
            config.configuration.type_inference.type4py_uri + "api/predict?tc=0&fp=0",
            source_code.encode("utf-8"),
            timeout=config.configuration.type_inference.type4py_timeout,
        ).json()
    except (requests.JSONDecodeError, requests.RequestException) as error:
        LOGGER.info(
            f"Failed to fetch Type4Py data for {module_name} ({error})"  # noqa: G004
        )
    return None
