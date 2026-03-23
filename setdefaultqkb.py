#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# setdefaultqkb.py
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
#  Use getdefaultqkb.py
# ---------------------------
def get_current_qkb_from_script(engine):
    cmd = [
        "python3",
        "getdefaultqkb.py",
        "--engine",
        engine,
        "--output",
        "json"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError("Failed to run getdefaultqkb.py")

    try:
        data = json.loads(result.stdout)
    except Exception:
        print("Raw output:", result.stdout)
        raise RuntimeError("Failed to parse JSON")

    if engine not in data:
        raise RuntimeError(f"No data for engine {engine}")

    engine_data = data[engine]

    return {
        "locale": engine_data.get("locale"),
        "qkb": engine_data.get("default QKB")
    }


# ---------------------------
# Step 1: Parse Inputs
# ---------------------------
def parse_args():
    parser = argparse.ArgumentParser(
        description="Set default QKB locale and QKB name"
    )

    parser.add_argument(
        "--engine",
        nargs="*",
        choices=["cas", "compute"],
        required=True
    )

    parser.add_argument("--locale", required=True)
    parser.add_argument("--qkb", required=True)

    parser.add_argument(
        "--output-file",
        default="/tmp/qkb_update.json"
    )

    return parser.parse_args()


# ---------------------------
# Step 2: Get Config
# ---------------------------
def get_engine_config(engine):
    if engine == "cas":
        config_def = "sas.cas.instance.config"
        item_name = "config"
    else:
        config_def = "sas.compute.server"
        item_name = "configuration_options"

    config_data = getconfigurationproperty(config_def)

    for item in config_data["items"]:
        if item.get("name") == item_name:
            return item, item.get("contents", "")

    raise RuntimeError("Config not found")


# ---------------------------
# Step 3: Compare
# ---------------------------
def needs_update(current, target_locale, target_qkb):
    return not (
        current["locale"] == target_locale and
        current["qkb"] == target_qkb
    )


# ---------------------------
# Step 4: Update Contents
# ---------------------------
def update_contents(contents, new_locale, new_qkb, engine):
    updated_lines = []
    found_locale = False
    found_qkb = False

    for line in contents.splitlines():
        stripped = line.strip()

        # COMPUTE → FORCE FORMAT
        if engine == "compute":
            if "DQLOCALE" in stripped:
                line = f"-DQLOCALE ({new_locale})"
                found_locale = True

            elif "DQSETUPLOC" in stripped:
                line = f"-DQSETUPLOC '{new_qkb}'"
                found_qkb = True

        # CAS → KEEP FORMAT
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
# Step 5: Build Payload
# ---------------------------
def build_payload(original_item, updated_contents):
    updated_item = dict(original_item)
    updated_item["contents"] = updated_contents
    return {"items": [updated_item]}


# ---------------------------
# Step 6: Write JSON
# ---------------------------
def write_payload(payload, filepath):
    with open(filepath, "w") as f:
        json.dump(payload, f, indent=4)


# ---------------------------
# Step 7: Apply Config
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
# Step 8: Process Engine
# ---------------------------
def process_engine(engine, locale, qkb, output_file):
    print(f"\nProcessing {engine.upper()}...")

    #  USE GET SCRIPT
    current = get_current_qkb_from_script(engine)
    print("Current (from getQKB):", current)

    if not needs_update(current, locale, qkb):
        print("No changes needed ✅")
        return

    item, contents = get_engine_config(engine)

    updated_contents = update_contents(contents, locale, qkb, engine)

    print("\n--- Updated Preview ---")
    print(updated_contents)

    payload = build_payload(item, updated_contents)
    write_payload(payload, output_file)

    print(f"\nPayload written to {output_file}")

    apply_config(output_file)

    # 🔥 VALIDATION STEP
    print("\n--- Validating ---")
    new_state = get_current_qkb_from_script(engine)
    print("Updated:", new_state)

    if new_state["locale"] == locale and new_state["qkb"] == qkb:
        print("✅ Validation successful")
    else:
        print("❌ Validation failed")


# ---------------------------
# Step 9: Main
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