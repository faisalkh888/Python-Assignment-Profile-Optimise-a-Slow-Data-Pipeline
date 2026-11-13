from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path


def generate(rows: int, output: Path, catalogue_path: Path, seed: int = 20261114) -> None:
    """Generate reproducible synthetic events and a small JSON catalogue."""
    rng = random.Random(seed)
    products = [{"sku": f"SKU-{i:04d}", "category": f"category-{i % 12:02d}"} for i in range(500)]
    with catalogue_path.open("w", encoding="utf-8") as handle:
        json.dump(products, handle, separators=(",", ":"), sort_keys=True)
    start = datetime(2025, 1, 1)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("timestamp", "user_id", "event", "sku", "price"))
        for _ in range(rows):
            when = start + timedelta(seconds=rng.randrange(90 * 86400))
            writer.writerow((when.strftime("%Y-%m-%dT%H:%M:%S"), f"U{rng.randrange(100_000):06d}",
                             rng.choices(("view", "cart", "purchase"), weights=(70, 15, 15))[0],
                             f"SKU-{rng.randrange(500):04d}", f"{rng.uniform(0.01, 999.99):.2f}"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=1_000_000)
    parser.add_argument("--output", type=Path, default=Path("events.csv"))
    parser.add_argument("--catalogue", type=Path, default=Path("catalogue.json"))
    parser.add_argument("--seed", type=int, default=20261114)
    args = parser.parse_args()
    generate(args.rows, args.output, args.catalogue, args.seed)


if __name__ == "__main__":
    main()
