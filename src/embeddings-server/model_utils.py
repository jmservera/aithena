"""Pure utility functions for model-family detection and text prefixing.

Kept separate from ``main.py`` so they can be imported in tests without
triggering model loading or ``sys.exit``.
"""


def detect_model_family(model_name: str) -> str:
    """Return the model family string based on the model name.

    E5-family models require query/passage prefixes; others do not.
    """
    name_lower = model_name.lower()
    if "e5" in name_lower:
        return "e5"
    return "generic"


def apply_prefix(texts: list[str], model_family: str, input_type: str) -> list[str]:
    """Prepend the appropriate prefix for e5-family models.

    For e5 models: ``"query: "`` when *input_type* is ``"query"``,
    ``"passage: "`` when *input_type* is ``"passage"``.
    For other model families the texts are returned unchanged.
    """
    if model_family != "e5":
        return texts
    prefix = "query: " if input_type == "query" else "passage: "
    return [prefix + t for t in texts]
