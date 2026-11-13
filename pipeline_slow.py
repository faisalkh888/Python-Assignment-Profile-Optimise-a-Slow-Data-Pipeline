"""Intentionally inefficient reference implementation for the assignment."""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def run(input_csv: Path, catalogue_json: Path, output_csv: Path) -> None:
    # Deliberately materialise every row as a dict, then linearly scan the
    # catalogue for every event. This is the profiling baseline.
    with catalogue_json.open(encoding="utf-8") as handle:
        catalogue: list[dict[str, Any]] = json.load(handle)
    with input_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    cleaned: list[dict[str, Any]] = []
    for row in rows:
        try:
            day = datetime.strptime(row["timestamp"], "%Y-%m-%dT%H:%M:%S").date().isoformat()
            price = float(row["price"])
            sku = row["sku"].strip()
            if not sku or price < 0:
                continue
            product = None
            for candidate in catalogue:
                if candidate["sku"] == sku:
                    product = candidate
                    break
            if product is None:
                continue
            cleaned.append({"day": day, "sku": sku, "category": product["category"], "price": price,
                            "event": row["event"]})
        except (KeyError, ValueError, TypeError):
            continue

    # Re-scan the cleaned data for every distinct output key.
    keys: list[tuple[str, str, str]] = []
    for row in cleaned:
        key = (row["day"], row["sku"], row["category"])
        if key not in keys:
            keys.append(key)
    output_rows: list[dict[str, str]] = []
    for day, sku, category in keys:
        revenue = 0.0
        for row in cleaned:
            if row["day"] == day and row["sku"] == sku and row["category"] == category and row["event"] == "purchase":
                revenue += row["price"]
        output_rows.append({"day": day, "sku": sku, "category": category, "revenue": str(revenue)})

    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["day", "sku", "category", "revenue"])
        writer.writeheader()
        writer.writerows(sorted(output_rows, key=lambda item: (item["day"], item["sku"], item["category"])))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: pipeline_slow.py INPUT.csv CATALOGUE.json OUTPUT.csv")
    run(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
