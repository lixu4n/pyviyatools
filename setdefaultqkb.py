#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# setconsetdefaultqkb.py
# March 2026
#
# 
# Change History
#python3 setdefaultqkb.py --engine cas compute --locale ENUSA --qkb "QKB CI 33"
#
# march2026 Initial version

# imports
from __future__ import print_function
import argparse
import json
import subprocess

from sharedfunctions import getconfigurationproperty


# ---------------------------
# Step 1: Parse Inputs
# ---------------------------
def parse_args():
    parser = argparse.ArgumentParser(
        description="Set default QKB locale and QKB name for CAS and/or Compute"
    )

    parser.add_argument(
        "--engine",
        nargs="*",
        choices=["cas", "compute"],
        required=True,
        help="Engine(s) to update: cas, compute"
    )

    parser.add_argument(
        "--locale",
        required=True,
        help="Target DQ locale (ex: ENUSA)"
    )

    parser.add_argument(
        "--qkb",
        required=True,
        help="Target QKB name (ex: QKB CI 33)"
    )

    parser.add_argument(
        "--output-file",
        default="/tmp/qkb_update.json",
        help="Output JSON payload file"
    )

    return parser.parse_args()


# ---------------------------
# Step 2: Get Engine Config
# ---------------------------
def get_engine_config(engine):
    if engine == "cas":
        config_def = "sas.cas.instance.config"
        item_name = "config"
    elif engine == "compute":
        config_def = "sas.compute.server"
        item_name = "configuration_options"
    else:
        raise ValueError("Invalid engine")

    config_data = getconfigurationproperty(config_def)

    if not config_data or "items" not in config_data:
        raise RuntimeError("No config found")

    for item in config_data["items"]:
        if item.get("name") == item_name:
            return item, item.get("contents", "")

    raise RuntimeError("Could not find correct config item")


# ---------------------------
# Step 3: Parse Current Values
# ---------------------------
def parse_qkb(contents):
    locale = None
    qkb = None

    for line in contents.splitlines():
        line = line.strip()

        if "DQLOCALE" in line:
            first = line.find('"')
            last = line.rfind('"')
            if first != -1 and last != -1:
                locale = line[first + 1:last]
            else:
                first = line.find("(")
                last = line.rfind(")")
                if first != -1 and last != -1:
                    locale = line[first + 1:last]

        if "DQSETUPLOC" in line:
            first = line.find('"')
            last = line.rfind('"')
            if first != -1 and last != -1:
                qkb = line[first + 1:last]
            else:
                first = line.find("'")
                last = line.rfind("'")
                if first != -1 and last != -1:
                    qkb = line[first + 1:last]

    return {"locale": locale, "qkb": qkb}


# ---------------------------
# Step 4: Check if Update Needed
# ---------------------------
def needs_update(current, target_locale, target_qkb):
    return not (
        current["locale"] == target_locale and
        current["qkb"] == target_qkb
    )


# ---------------------------
# Step 5: Update Contents
# ---------------------------
def update_contents(contents, new_locale, new_qkb):
    updated_lines = []
    found_locale = False
    found_qkb = False

    for line in contents.splitlines():
        stripped = line.strip()

        if "DQLOCALE" in stripped:
            if stripped.startswith("cas."):
                line = f'cas.DQLOCALE="{new_locale}"'
            else:
                line = f'-DQLOCALE ({new_locale})'
            found_locale = True

        elif "DQSETUPLOC" in stripped:
            if stripped.startswith("cas."):
                line = f'cas.DQSETUPLOC="{new_qkb}"'
            else:
                line = f"-DQSETUPLOC '{new_qkb}'"
            found_qkb = True

        updated_lines.append(line)

    if not found_locale:
        updated_lines.append(f'cas.DQLOCALE="{new_locale}"')

    if not found_qkb:
        updated_lines.append(f'cas.DQSETUPLOC="{new_qkb}"')

    return "\n".join(updated_lines)


# ---------------------------
# Step 6: Build Payload
# ---------------------------
def build_payload(original_item, updated_contents):
    updated_item = dict(original_item)
    updated_item["contents"] = updated_contents

    return {"items": [updated_item]}


# ---------------------------
# Step 7: Write JSON File
# ---------------------------
def write_payload(payload, filepath):
    with open(filepath, "w") as f:
        json.dump(payload, f, indent=4)


# ---------------------------
# Step 8: Apply Config
# ---------------------------
def apply_config(filepath):
    cmd = [
        "python3",
        "setconfigurationproperties.py",
        "--file",
        filepath
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    if result.returncode != 0:
        raise RuntimeError("Failed to apply configuration")


# ---------------------------
# Step 9: Full Engine Flow
# ---------------------------
def process_engine(engine, locale, qkb, output_file):
    print(f"\nProcessing {engine.upper()}...")

    item, contents = get_engine_config(engine)

    current = parse_qkb(contents)
    print("Current:", current)

    if not needs_update(current, locale, qkb):
        print("No changes needed ✅")
        return

    updated_contents = update_contents(contents, locale, qkb)

    print("\n--- Updated Preview ---")
    print(updated_contents)

    payload = build_payload(item, updated_contents)
    write_payload(payload, output_file)

    print(f"\nPayload written to {output_file}")

    # 🔴 Uncomment when ready
    # apply_config(output_file)


# ---------------------------
# Step 10: Main
# ---------------------------
def main():
    args = parse_args()

    for engine in args.engine:
        output_file = args.output_file

        if len(args.engine) > 1:
            output_file = f"/tmp/qkb_update_{engine}.json"

        process_engine(engine, args.locale, args.qkb, output_file)


if __name__ == "__main__":
    main()