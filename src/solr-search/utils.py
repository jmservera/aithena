"""Shared utility helpers for the Solr search service."""

from __future__ import annotations

from typing import Any


def safe_numeric(value: Any, type_fn: type = float, default: int | float = 0) -> int | float:
    """Safely convert Solr response values to numeric types.

    Solr may return numeric fields as strings, ``None``, or native numeric
    types depending on the response handler and server configuration.  This
    helper normalises those values so callers never hit ``TypeError`` or
    ``ValueError`` when performing arithmetic on Solr data.

    Args:
        value: Raw value from a Solr response (``str``, ``int``, ``float``,
               or ``None``).
        type_fn: Target numeric type — typically ``float`` or ``int``.
        default: Fallback returned when *value* is ``None`` or cannot be
                 converted.

    Returns:
        The converted numeric value, or *default* on failure.
    """
    if value is None:
        return default
    try:
        return type_fn(value)
    except (TypeError, ValueError):
        return default
