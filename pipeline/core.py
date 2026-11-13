from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime
from functools import lru_cache
from pathlib import Path

try:
    import numpy as np
except ImportError:  # pragma: no cover - packaging installs numpy
    np = None  # type: ignore[assignment]


FIELDS = ("timestamp", "user_id", "event", "sku", "price")
OUT_FIELDS = ("day", "sku", "category", "revenue")


def clean_row(row: list[str], catalogue: dict[str, str]) -> tuple[str, str, str, float, str] | None:
    """Validate a CSV row and return day, SKU, category, price and event."""
    if len(row) != len(FIELDS):
        return None
    timestamp, _user_id, event, raw_sku, raw_price = row
    sku = raw_sku.strip()
    try:
        price = float(raw_price)
        if not sku or price < 0 or not price < float("inf"):
            return None
        category = catalogue.get(sku)
        if category is None:
            return None
        day = _parse_day(timestamp)
    except (ValueError, OverflowError):
        return None
    return day, sku, category, price, event


@lru_cache(maxsize=8192)
def _parse_day(timestamp: str) -> str:
    return datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S").date().isoformat()


def run(input_csv: Path, catalogue_json: Path, output_csv: Path, *, chunk_size: int = 65536) -> None:
    """Stream events and aggregate purchase revenue; output deterministic CSV."""
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    with catalogue_json.open(encoding="utf-8") as handle:
        raw_catalogue = json.load(handle)
    catalogue = {str(item["sku"]): str(item["category"]) for item in raw_catalogue}
    totals: dict[tuple[str, str, str], float] = defaultdict(float)
    batch: list[tuple[str, str, str, float]] = []

    def flush() -> None:
        if not batch:
            return
        # NumPy groups each bounded batch in native code; the cross-batch
        # accumulator remains a compact dictionary keyed by output dimensions.
        if np is not None:
            keys = [(day, sku, category) for day, sku, category, _ in batch]
            prices = np.fromiter((price for _, _, _, price in batch), dtype=np.float64, count=len(batch))
            unique, inverse = np.unique(np.asarray(keys, dtype=str), axis=0, return_inverse=True)
            sums = np.bincount(inverse, weights=prices)
            for index, key in enumerate(unique):
                totals[(str(key[0]), str(key[1]), str(key[2]))] += float(sums[index])
        else:  # equivalent fallback, useful for running directly from source
            for day, sku, category, price in batch:
                totals[(day, sku, category)] += price
        batch.clear()

    with input_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header != list(FIELDS):
            raise ValueError(f"expected CSV header {list(FIELDS)!r}")
        for row in reader:
            cleaned = clean_row(row, catalogue)
            if cleaned is None:
                continue
            day, sku, category, price, event = cleaned
            totals.setdefault((day, sku, category), 0.0)
            if event == "purchase":
                batch.append((day, sku, category, price))
                if len(batch) >= chunk_size:
                    flush()
    flush()

    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(OUT_FIELDS)
        for (day, sku, category), revenue in sorted(totals.items()):
            writer.writerow((day, sku, category, repr(revenue)))


def main() -> None:
    parser = argparse.ArgumentParser(prog="pipeline")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("catalogue_json", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--chunk-size", type=int, default=65536)
    args = parser.parse_args()
    run(args.input_csv, args.catalogue_json, args.output_csv, chunk_size=args.chunk_size)


if __name__ == "__main__":
    main()
