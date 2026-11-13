from __future__ import annotations

import csv
import json
from pathlib import Path

from hypothesis import given, strategies as st

from pipeline.core import clean_row, run
from pipeline_slow import run as slow_run


@given(sku=st.text(max_size=12), price=st.floats(allow_nan=False, allow_infinity=False, width=32))
def test_cleaning_never_returns_negative_price_or_empty_sku(sku: str, price: float) -> None:
    catalogue = {sku.strip(): "category"} if sku.strip() else {}
    row = ["2025-01-01T12:00:00", "u1", "purchase", sku, str(price)]
    result = clean_row(row, catalogue)
    assert result is None or (result[1] != "" and result[3] >= 0)


def test_outputs_match_on_10000_rows(tmp_path: Path) -> None:
    from generate_data import generate
    events, catalogue = tmp_path / "events.csv", tmp_path / "catalogue.json"
    generate(10_000, events, catalogue)
    slow, fast = tmp_path / "slow.csv", tmp_path / "fast.csv"
    slow_run(events, catalogue, slow)
    run(events, catalogue, fast)
    assert list(csv.reader(slow.open(newline=""))) == list(csv.reader(fast.open(newline="")))


def test_empty_input_and_malformed_rows(tmp_path: Path) -> None:
    catalogue = tmp_path / "catalogue.json"
    catalogue.write_text(json.dumps([{"sku": "A", "category": "x"}]), encoding="utf-8")
    source, output = tmp_path / "events.csv", tmp_path / "out.csv"
    source.write_text("timestamp,user_id,event,sku,price\n", encoding="utf-8")
    run(source, catalogue, output)
    assert output.read_text(encoding="utf-8") == "day,sku,category,revenue\n"
    source.write_text("timestamp,user_id,event,sku,price\nnope\n2025-01-01T00:00:00,u,purchase,A,-1\n", encoding="utf-8")
    run(source, catalogue, output)
    assert output.read_text(encoding="utf-8") == "day,sku,category,revenue\n"
