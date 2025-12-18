#!/usr/bin/env python3
"""
Infer an "observed" JSON Schema (plus optional flattened path/type map) from one or
more JSON documents.

This is meant for documenting dynamic payloads (like `final_result`) where upstream
providers (e.g., Rightmove, ML services) can add/remove fields over time.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


JsonValue = Any


def _json_type(value: JsonValue) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    # Fallback: JSON doesn't have these types, but Python might.
    return "string"


def _merge_type_sets(existing: Set[str], incoming: Set[str]) -> Set[str]:
    merged = set(existing) | set(incoming)
    # If we saw both integer + number, normalize to number.
    if "number" in merged and "integer" in merged:
        merged.discard("integer")
    return merged


@dataclass
class ObservedSchema:
    types: Set[str] = field(default_factory=set)
    properties: Dict[str, "ObservedSchema"] = field(default_factory=dict)
    required_counts: Dict[str, int] = field(default_factory=dict)
    samples_seen: int = 0
    object_samples_seen: int = 0
    items: Optional["ObservedSchema"] = None

    def observe(self, value: JsonValue, *, max_array_items: int) -> None:
        value_type = _json_type(value)
        self.types = _merge_type_sets(self.types, {value_type})
        self.samples_seen += 1

        if value_type == "object" and isinstance(value, dict):
            self.object_samples_seen += 1
            for key, child_value in value.items():
                if key not in self.properties:
                    self.properties[key] = ObservedSchema()
                self.properties[key].observe(child_value, max_array_items=max_array_items)
                self.required_counts[key] = self.required_counts.get(key, 0) + 1

        if value_type == "array" and isinstance(value, list):
            if self.items is None:
                self.items = ObservedSchema()
            for item in value[:max_array_items]:
                self.items.observe(item, max_array_items=max_array_items)

    def to_jsonschema(self) -> Dict[str, Any]:
        schema: Dict[str, Any] = {"type": sorted(self.types) if self.types else ["null"]}
        # JSON Schema expects a string for single-type `type`
        if isinstance(schema["type"], list) and len(schema["type"]) == 1:
            schema["type"] = schema["type"][0]

        if "object" in self.types:
            schema["properties"] = {
                key: child.to_jsonschema() for key, child in sorted(self.properties.items())
            }
            required = sorted(
                [k for k, c in self.required_counts.items() if c == self.object_samples_seen]
            )
            if required:
                schema["required"] = required
            schema["additionalProperties"] = True

        if "array" in self.types:
            schema["items"] = (self.items or ObservedSchema(types={"null"})).to_jsonschema()

        return schema


def _iter_json_files(paths: List[str]) -> Iterable[str]:
    for input_path in paths:
        if os.path.isdir(input_path):
            for root, _, files in os.walk(input_path):
                for name in files:
                    if name.lower().endswith(".json"):
                        yield os.path.join(root, name)
        else:
            yield input_path


def _load_samples_from_file(
    file_path: str, *, unwrap_key: Optional[str]
) -> List[JsonValue]:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    samples: List[JsonValue]
    if isinstance(data, list):
        samples = data
    else:
        samples = [data]

    if unwrap_key:
        unwrapped: List[JsonValue] = []
        for item in samples:
            if isinstance(item, dict) and unwrap_key in item:
                unwrapped.append(item[unwrap_key])
        samples = unwrapped

    return samples


def _flatten_paths(
    schema: ObservedSchema, prefix: str = ""
) -> List[Tuple[str, str]]:
    types_str = "|".join(sorted(schema.types)) if schema.types else "null"
    rows: List[Tuple[str, str]] = [(prefix or "$", types_str)]

    if "object" in schema.types:
        for key, child in sorted(schema.properties.items()):
            child_prefix = f"{prefix}.{key}" if prefix else key
            rows.extend(_flatten_paths(child, child_prefix))

    if "array" in schema.types and schema.items is not None:
        child_prefix = f"{prefix}[]" if prefix else "[]"
        rows.extend(_flatten_paths(schema.items, child_prefix))

    return rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Infer an observed JSON Schema from JSON files.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        help="One or more JSON files or directories (directories scanned recursively).",
    )
    parser.add_argument(
        "--unwrap-key",
        default=None,
        help="If provided, only infer schema from this key within each top-level object (useful for `final_result`).",
    )
    parser.add_argument(
        "--max-array-items",
        type=int,
        default=50,
        help="Max items to sample per array (prevents huge arrays from dominating inference).",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="Where to write JSON Schema (`-` for stdout).",
    )
    parser.add_argument(
        "--paths-output",
        default=None,
        help="Optional output file for flattened path/type rows (TSV).",
    )

    args = parser.parse_args()

    if not args.inputs:
        default_input = os.path.join("output", "final_output.json")
        if os.path.exists(default_input):
            args.inputs = [default_input]
            if args.unwrap_key is None:
                args.unwrap_key = "final_result"
        else:
            parser.error(
                "No inputs provided and default `output/final_output.json` not found. "
                "Pass one or more JSON files/directories."
            )

    root = ObservedSchema()
    total_samples = 0
    for json_path in _iter_json_files(args.inputs):
        for sample in _load_samples_from_file(json_path, unwrap_key=args.unwrap_key):
            root.observe(sample, max_array_items=args.max_array_items)
            total_samples += 1

    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Observed schema (inferred)",
        "description": (
            "This schema is inferred from example payloads and may not include fields "
            "that did not appear in the sample set."
        ),
        "type": "object" if "object" in root.types else (sorted(root.types)[0] if root.types else "null"),
        **root.to_jsonschema(),
    }
    schema.pop("type", None)  # ensure `to_jsonschema()` controls final type
    schema.update(root.to_jsonschema())

    out_text = json.dumps(schema, indent=2, sort_keys=True)
    if args.output == "-":
        print(out_text)
    else:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out_text + "\n")

    if args.paths_output:
        rows = _flatten_paths(root)
        with open(args.paths_output, "w", encoding="utf-8") as f:
            f.write("path\ttypes\n")
            for path, types_str in rows:
                f.write(f"{path}\t{types_str}\n")

    return 0 if total_samples else 2


if __name__ == "__main__":
    raise SystemExit(main())
