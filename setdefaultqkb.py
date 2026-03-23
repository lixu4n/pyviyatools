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


#import

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
        raise RuntimeError(f"No config found for {engine}")

    for item in config_data["items"]:
        if item.get("name") == item_name:
            return item, item.get("contents", "")

    raise RuntimeError(f"Could not find correct config item for {engine}")


# ---------------------------
# Step 3: Parse Current Values
# ---------------------------
def parse_qkb(contents):
    locale = None
    qkb = None

    for line in contents.splitlines():
        line = line.strip()

        if "DQLOCALE" in line:
            if '"' in line:
                locale = line.split('"')[1]
            elif "(" in line:
                locale = line.split("(")[1].split(")")[0]

        if "DQSETUPLOC" in line:
            if '"' in line:
                qkb = line.split('"')[1]
            elif "'" in line:
                qkb = line.split("'")[1]

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
# Step 5: Update Contents (UPDATED LOGIC)
# ---------------------------
def update_contents(contents, new_locale, new_qkb, engine):
    updated_lines = []
    found_locale = False
    found_qkb = False

    for line in contents.splitlines():
        stripped = line.strip()

        # ---- FORCE COMPUTE FORMAT ----
        if engine == "compute":
            if "DQLOCALE" in stripped:
                line = f"-DQLOCALE ({new_locale})"
                found_locale = True

            elif "DQSETUPLOC" in stripped:
                line = f"-DQSETUPLOC '{new_qkb}'"
                found_qkb = True

        # ---- CAS FORMAT ----
        elif engine == "cas":
            if "DQLOCALE" in stripped:
                line = f'cas.DQLOCALE="{new_locale}"'
                found_locale = True

            elif "DQSETUPLOC" in stripped:
                line = f'cas.DQSETUPLOC="{new_qkb}"'
                found_qkb = True

        updated_lines.append(line)

    # Add if missing
    if not found_locale:
        if engine == "compute":
            updated_lines.append(f"-DQLOCALE ({new_locale})")
        else:
            updated_lines.append(f'cas.DQLOCALE="{new_locale}"')

    if not found_qkb:
        if engine == "compute":
            updated_lines.append(f"-DQSETUPLOC '{new_qkb}'")
        else:
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
    import os

    # Copy current environment
    env = os.environ.copy()

    # Override CLI path
    env["SAS_CLI_HOME"] = "/usr/local/bin"
    env["PATH"] = "/usr/local/bin:" + env["PATH"]

    cmd = [
        "python3",
        "setconfigurationproperties.py",
        "--file",
        filepath
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, env=env)

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

    updated_contents = update_contents(contents, locale, qkb, engine)

    print("\n--- Updated Preview ---")
    print(updated_contents)

    payload = build_payload(item, updated_contents)
    write_payload(payload, output_file)

    print(f"\nPayload written to {output_file}")

    # COMMENT THIS FIRST FOR TESTING
    apply_config(output_file)


# ---------------------------
# Step 10: Main
# ---------------------------
def main():
    args = parse_args()

    for engine in args.engine:
        output_file = args.output_file

        if len(args.engine) > 1:
            output_file = f"/tmp/qkb_update_{engine}.json"

        process_engine(
            engine=engine,
            locale=args.locale,
            qkb=args.qkb,
            output_file=output_file
        )


if __name__ == "__main__":
    main()