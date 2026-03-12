#!/usr/bin/env python3
"""

setdqdefaults.py
January Test 2026
March 10 th Test 2 2026

Helper tool pecialized to edit two lines inside contents, then write JSON out


Set the Default QKB and the Default Locale in SAS Viya Environemwent Manager
https://go.documentation.sas.com/doc/en/sasadmincdc/v_071/calqkb/p1e7c6cq2eubnzn160g6pvi9tgmx.htm#n1icsiqtv6avqzn1tmey5dm79x42

Works for:
- CAS:    definition sas.cas.instance.config, item name "config"
- Compute definition sas.compute.server,      item name "configuration_options"

Behavior:
- Default is APPEND-IF-MISSING (idempotent, no overwrites)
- Optional --replace to overwrite existing values

TEST : Celeste Duguay (Jan 12 2026)
TEST2 
"""

# ==============================
# Standard Library Imports
# ==============================

import argparse
import json
import re
import subprocess
import sys
from typing import Any, Dict, Tuple


# =====================================================
# Configuration Retrieval
# =====================================================

def run_get_config(configuration_def: str) -> Dict[str, Any]:
    """
    Execute getconfigurationproperties.py to retrieve
    configuration as JSON.

    Parameters:
        configuration_def (str): Config definition name
            e.g. 'sas.compute.server'

    Returns:
        Dict[str, Any]: Parsed JSON configuration

    Raises:
        RuntimeError: If script execution fails
        RuntimeError: If JSON parsing fails
    """

    cmd = ["python3", "getconfigurationproperties.py", "-c", configuration_def, "-o", "json"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"getconfigurationproperties.py failed:\n{p.stderr}")
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse JSON from getconfigurationproperties.py: {e}")
    
# =====================================================
# Item Selection Utilities
# =====================================================

def find_item_by_name(data: Dict[str, Any], item_name: str) -> Dict[str, Any]:
    """Find exactly one item in data['items'] with .name == item_name."""
    items = data.get("items", [])
    matches = [it for it in items if it.get("name") == item_name]
    if not matches:
        available = [it.get("name") for it in items]
        raise KeyError(f"Item name '{item_name}' not found. Available items: {available}")
    if len(matches) > 1:
        # Rare but handleable: choose exact match only; user can switch to id targeting if needed.
        ids = [m.get("id") for m in matches]
        raise ValueError(f"Multiple items named '{item_name}' found (ids={ids}). Use --item-id instead.")
    return matches[0]


def find_item_by_id(data: Dict[str, Any], item_id: str) -> Dict[str, Any]:
    items = data.get("items", [])
    matches = [it for it in items if it.get("id") == item_id]
    if not matches:
        ids = [it.get("id") for it in items]
        raise KeyError(f"Item id '{item_id}' not found. Available ids: {ids}")
    return matches[0]


# =====================================================
# Content Modification Logic
# =====================================================

def append_if_missing(contents: str, key: str, value: str) -> Tuple[str, bool]:
    """
    Append a config line if key does not exist.
    Returns (new_contents, changed)
    """
    if f"{key}=" in contents:
        return contents, False
    line = f"\n{key}='{value}'\n"
    return contents + line, True


def replace_or_append(contents: str, key: str, value: str) -> Tuple[str, bool]:
    """
    Replace existing key='...' or key=... with key='value'. If missing, append.
    """
    # Replace patterns like::
    # cas.DQSETUPLOC='something'
    # cas.DQSETUPLOC="something"
    # cas.DQSETUPLOC=something
    pattern = re.compile(rf"(^|\n){re.escape(key)}\s*=\s*(['\"]?)[^\n'\"]*\2", re.MULTILINE)
    if pattern.search(contents):
        new_contents = pattern.sub(rf"\1{key}='{value}'", contents)
        return new_contents, True
    else:
        return append_if_missing(contents, key, value)

# =====================================================
# Business Logic (user)
# =====================================================

def update_dq_defaults(
    data: Dict[str, Any],
    *,
    item_name: str = None,
    item_id: str = None,
    dqsetuploc: str,
    dqlocale: str,
    replace: bool,
) -> Tuple[Dict[str, Any], bool]:
    """
    Update DQ default settings in the selected configuration item.

    Exactly one of item_name or item_id must be provided.

    Returns:
        (updated_data, changed_flag)
    """
    if (item_name is None) == (item_id is None):
        raise ValueError("Provide exactly one of --item-name or --item-id.")

    item = find_item_by_id(data, item_id) if item_id else find_item_by_name(data, item_name)

    contents = item.get("contents", "")
    changed = False

    if replace:
        contents, c1 = replace_or_append(contents, "cas.DQSETUPLOC", dqsetuploc)
        contents, c2 = replace_or_append(contents, "cas.DQLOCALE", dqlocale)
        changed = c1 or c2
    else:
        contents, c1 = append_if_missing(contents, "cas.DQSETUPLOC", dqsetuploc)
        contents, c2 = append_if_missing(contents, "cas.DQLOCALE", dqlocale)
        changed = c1 or c2

    item["contents"] = contents
    return data, changed


# =====================================================
# CLI Interface
# =====================================================


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config-def", required=True, help="Config definition, e.g. sas.compute.server or sas.cas.instance.config")
    ap.add_argument("--item-name", help="Item name to modify, e.g. configuration_options or config")
    ap.add_argument("--item-id", help="Item id to modify (alternative to item-name)")
    ap.add_argument("--dqsetuploc", required=True, help="QKB name, e.g. QKB CI 33")
    ap.add_argument("--dqlocale", required=True, help="Locale, e.g. ENUSA")
    ap.add_argument("--replace", action="store_true", help="Replace existing values (default is append-if-missing)")
    ap.add_argument("--out", required=True, help="Output JSON file path")
    args = ap.parse_args()

    data = run_get_config(args.config_def)

    updated, changed = update_dq_defaults(
        data,
        item_name=args.item_name,
        item_id=args.item_id,
        dqsetuploc=args.dqsetuploc,
        dqlocale=args.dqlocale,
        replace=args.replace,
    )

    with open(args.out, "w") as f:
        json.dump(updated, f, indent=2)

    if changed:
        print(f"Wrote updated config to: {args.out}")
    else:
        print(f"No changes needed (keys already present). File still written: {args.out}")


# =====================================================
# Entry Point
# =====================================================

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


# =====================================================
# EXAMPLE


# python3 setdqdefault.py \
#   --config-def sas.compute.server \
#   --item-name configuration_options \
#   --dqsetuploc "QKB CI 33" \
#   --dqlocale "ENUSA" \
#   --out /tmp/configs/compute_config_updated.json


# sas-viya configuration configurations update \
#   --file /tmp/compute_config_test.json


# =====================================================
