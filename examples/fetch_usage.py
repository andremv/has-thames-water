#!/usr/bin/env python3
"""Standalone example: fetch Thames Water usage without Home Assistant."""

from __future__ import annotations

import importlib.util
import json
import os
import sys

import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
_COMPONENT_DIR = os.path.abspath(
    os.path.join(_HERE, "..", "custom_components", "thames_water")
)
_API_PATH = os.path.join(_COMPONENT_DIR, "api.py")

# Allow api.py's standalone "from const import ..." fallback to resolve.
sys.path.insert(0, _COMPONENT_DIR)


def _load_client():
    """Import api.py directly (bypassing the HA-dependent package init)."""
    spec = importlib.util.spec_from_file_location("thames_water_api", _API_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ThamesWaterClient


def main() -> None:
    email = os.environ.get("THAMES_EMAIL", "")
    password = os.environ.get("THAMES_PASSWORD", "")
    account = os.environ.get("THAMES_ACCOUNT", "")

    if not password:
        print("Set THAMES_PASSWORD to your My Account password.")
        sys.exit(1)

    client_class = _load_client()
    client = client_class(requests.Session(), email, password, account)
    data = client.get_usage()

    print(json.dumps(data, indent=2, default=str))


if __name__ == "__main__":
    main()
