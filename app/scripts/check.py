from __future__ import annotations

import csv
from pathlib import Path
from typing import cast

import polars as pl

NUMERIC_COLUMNS = ("quantity", "entry_price", "exit_price", "profit_loss", "balance")
REQUIRED_COLUMNS = set(NUMERIC_COLUMNS)

# Script-level settings (edit these directly)
ABS_TOLERANCE = 1e-2
ZERO_DIV_EPSILON = 1e-12
FALLBACK_QUANTITY = 1.0
REPO_ROOT = Path(__file__).resolve().parents[2]
CSV_FILES_TO_CHECK = [
    REPO_ROOT / "datasets" / "calm_trader.csv",
    REPO_ROOT / "datasets" / "loss_averse_trader.csv",
    REPO_ROOT / "datasets" / "overtrader.csv",
    REPO_ROOT / "datasets" / "revenge_trader.csv",
]

def load_raw_rows(csv_path: Path) -> list[dict[str, str]]:
    raw_rows: list[dict[str, str]] = []

    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            normalized_row = {key: (value or "") for key, value in row.items()}
            raw_rows.append(normalized_row)

    return raw_rows

def source_label(raw_value: str) -> str:
    text = raw_value.strip()
    if not text:
        return "missing"
    return f"invalid '{text}'"


def infer_trade_single_missing(
    quantity: float | None,
    entry_price: float | None,
    exit_price: float | None,
    profit_loss: float | None,
) -> tuple[str, float] | None:
    if (
        profit_loss is None
        and quantity is not None
        and entry_price is not None
        and exit_price is not None
    ):
        return ("profit_loss", quantity * (exit_price - entry_price))

    if (
        quantity is None
        and profit_loss is not None
        and entry_price is not None
        and exit_price is not None
    ):
        price_delta = exit_price - entry_price
        if abs(price_delta) > ZERO_DIV_EPSILON:
            return ("quantity", profit_loss / price_delta)
        return None

    if (
        entry_price is None
        and profit_loss is not None
        and quantity is not None
        and exit_price is not None
        and abs(quantity) > ZERO_DIV_EPSILON
    ):
        return ("entry_price", exit_price - (profit_loss / quantity))

    if (
        exit_price is None
        and profit_loss is not None
        and quantity is not None
        and entry_price is not None
        and abs(quantity) > ZERO_DIV_EPSILON
    ):
        return ("exit_price", entry_price + (profit_loss / quantity))

    return None


def fix_file(
    csv_path: Path,
    *,
    abs_tolerance: float,
    fallback_quantity: float,
) -> tuple[int, int, int, int, int, list[str], str | None]:
    df = pl.read_csv(csv_path)

    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    raw_rows = load_raw_rows(csv_path)
    if len(raw_rows) != df.height:
        raise ValueError("Row count mismatch while loading raw CSV values")

    quantity = cast(
        list[float | None], df["quantity"].cast(pl.Float64, strict=False).to_list()
    )
    entry_price = cast(
        list[float | None], df["entry_price"].cast(pl.Float64, strict=False).to_list()
    )
    exit_price = cast(
        list[float | None], df["exit_price"].cast(pl.Float64, strict=False).to_list()
    )
    profit_loss = cast(
        list[float | None], df["profit_loss"].cast(pl.Float64, strict=False).to_list()
    )
    balance = cast(
        list[float | None], df["balance"].cast(pl.Float64, strict=False).to_list()
    )

    corrected_quantity: list[float | None] = []
    corrected_entry_price: list[float | None] = []
    corrected_exit_price: list[float | None] = []
    corrected_profit_loss: list[float | None] = []
    corrected_balance: list[float | None] = []
    warnings: list[str] = []

    quantity_fills = 0
    entry_price_fills = 0
    exit_price_fills = 0
    profit_loss_fixes = 0
    balance_fixes = 0

    for i in range(df.height):
        raw_row = raw_rows[i]

        raw_values = {
            "quantity": raw_row.get("quantity", ""),
            "entry_price": raw_row.get("entry_price", ""),
            "exit_price": raw_row.get("exit_price", ""),
            "profit_loss": raw_row.get("profit_loss", ""),
            "balance": raw_row.get("balance", ""),
        }
        values: dict[str, float | None] = {
            "quantity": quantity[i],
            "entry_price": entry_price[i],
            "exit_price": exit_price[i],
            "profit_loss": profit_loss[i],
            "balance": balance[i],
        }

        def set_recovered(column: str, inferred_value: float, reason: str = "") -> None:
            nonlocal quantity_fills, entry_price_fills, exit_price_fills
            nonlocal profit_loss_fixes, balance_fixes

            values[column] = float(inferred_value)
            if column == "quantity":
                quantity_fills += 1
            elif column == "entry_price":
                entry_price_fills += 1
            elif column == "exit_price":
                exit_price_fills += 1
            elif column == "profit_loss":
                profit_loss_fixes += 1
            elif column == "balance":
                balance_fixes += 1

            suffix = f" {reason}" if reason else ""
            warnings.append(
                f"[WARN] {csv_path.name} row {i}, column {column}: "
                f"{source_label(raw_values[column])} -> {values[column]}{suffix}"
            )

        for column_name in NUMERIC_COLUMNS:
            raw_value = raw_values[column_name]
            parsed_value = values[column_name]
            if raw_value.strip() and parsed_value is None:
                warnings.append(
                    f"[WARN] {csv_path.name} row {i}, column {column_name}: "
                    f"non-numeric value '{raw_value}'"
                )

        previous_balance = corrected_balance[i - 1] if i > 0 else None

        for _ in range(12):
            changed = False

            if (
                values["profit_loss"] is None
                and previous_balance is not None
                and values["balance"] is not None
            ):
                set_recovered(
                    "profit_loss", values["balance"] - previous_balance, "(from balance)"
                )
                changed = True

            inferred = infer_trade_single_missing(
                values["quantity"],
                values["entry_price"],
                values["exit_price"],
                values["profit_loss"],
            )
            if inferred is not None:
                inferred_column, inferred_value = inferred
                if values[inferred_column] is None:
                    set_recovered(inferred_column, inferred_value)
                    changed = True

            if (
                values["balance"] is None
                and previous_balance is not None
                and values["profit_loss"] is not None
            ):
                set_recovered("balance", previous_balance + values["profit_loss"])
                changed = True

            if not changed:
                break

        if values["quantity"] is None and values["profit_loss"] is not None:
            if values["entry_price"] is None and values["exit_price"] is not None:
                set_recovered("quantity", fallback_quantity, "(fallback assumption)")
                quantity_now = values["quantity"]
                if quantity_now is not None:
                    set_recovered(
                        "entry_price",
                        values["exit_price"] - (values["profit_loss"] / quantity_now),
                        f"(derived using fallback quantity={fallback_quantity})",
                    )
            elif values["exit_price"] is None and values["entry_price"] is not None:
                set_recovered("quantity", fallback_quantity, "(fallback assumption)")
                quantity_now = values["quantity"]
                if quantity_now is not None:
                    set_recovered(
                        "exit_price",
                        values["entry_price"] + (values["profit_loss"] / quantity_now),
                        f"(derived using fallback quantity={fallback_quantity})",
                    )

        for _ in range(8):
            changed = False
            inferred = infer_trade_single_missing(
                values["quantity"],
                values["entry_price"],
                values["exit_price"],
                values["profit_loss"],
            )
            if inferred is not None:
                inferred_column, inferred_value = inferred
                if values[inferred_column] is None:
                    set_recovered(inferred_column, inferred_value)
                    changed = True

            if (
                values["balance"] is None
                and previous_balance is not None
                and values["profit_loss"] is not None
            ):
                set_recovered("balance", previous_balance + values["profit_loss"])
                changed = True

            if not changed:
                break

        if (
            values["quantity"] is not None
            and values["entry_price"] is not None
            and values["exit_price"] is not None
        ):
            expected_profit_loss = values["quantity"] * (
                values["exit_price"] - values["entry_price"]
            )

            if values["profit_loss"] is None:
                set_recovered("profit_loss", expected_profit_loss)
            else:
                if not (abs(values["profit_loss"] - expected_profit_loss) <= abs_tolerance):
                    previous_profit = values["profit_loss"]
                    values["profit_loss"] = expected_profit_loss
                    profit_loss_fixes += 1
                    warnings.append(
                        f"[WARN] {csv_path.name} row {i}, column profit_loss: "
                        f"{previous_profit} -> {expected_profit_loss}"
                    )

        if i > 0:
            if previous_balance is not None and values["profit_loss"] is not None:
                expected_balance = previous_balance + values["profit_loss"]
                if values["balance"] is None:
                    set_recovered("balance", expected_balance)
                else:
                    if not (abs(values["balance"] - expected_balance) <= abs_tolerance):
                        previous_balance_value = values["balance"]
                        values["balance"] = expected_balance
                        balance_fixes += 1
                        warnings.append(
                            f"[WARN] {csv_path.name} row {i}, column balance: "
                            f"{previous_balance_value} -> {expected_balance}"
                        )

        for column_name in NUMERIC_COLUMNS:
            if values[column_name] is None:
                error_message = (
                    f"[ERROR] {csv_path.name} row {i}, column {column_name}: "
                    "could not recover value from available fields; halting this file"
                )
                return (
                    quantity_fills,
                    entry_price_fills,
                    exit_price_fills,
                    profit_loss_fixes,
                    balance_fixes,
                    warnings,
                    error_message,
                )

        corrected_quantity.append(values["quantity"])
        corrected_entry_price.append(values["entry_price"])
        corrected_exit_price.append(values["exit_price"])
        corrected_profit_loss.append(values["profit_loss"])
        corrected_balance.append(values["balance"])

    return (
        quantity_fills,
        entry_price_fills,
        exit_price_fills,
        profit_loss_fixes,
        balance_fixes,
        warnings,
        None,
    )


def main() -> int:
    if abs(FALLBACK_QUANTITY) <= ZERO_DIV_EPSILON:
        raise ValueError("FALLBACK_QUANTITY must be non-zero.")

    csv_files = CSV_FILES_TO_CHECK
    if not csv_files:
        print("No CSV files configured in CSV_FILES_TO_CHECK")
        return 0

    total_entry_fills = 0
    total_exit_fills = 0
    total_profit_fixes = 0
    total_balance_fixes = 0
    total_quantity_fills = 0
    total_empty_cells = 0
    files_with_warnings = 0
    errored_files = 0

    for csv_path in csv_files:
        if not csv_path.exists():
            errored_files += 1
            print(f"[ERROR] {csv_path}: file does not exist")
            continue

        empty_cells = sum(not v.strip() for row in load_raw_rows(csv_path) for v in row.values())

        try:
            (
                quantity_fills,
                entry_fills,
                exit_fills,
                profit_fixes,
                balance_fixes,
                warnings,
                error_message,
            ) = fix_file(
                csv_path,
                abs_tolerance=ABS_TOLERANCE,
                fallback_quantity=FALLBACK_QUANTITY,
            )
        except Exception as exc:  # noqa: BLE001
            errored_files += 1
            print(f"[ERROR] {csv_path.name}: {exc}")
            continue

        if warnings:
            files_with_warnings += 1
            print(
                f"[WARN] {csv_path.name}: "
                f"empty cells={empty_cells}, "
                f"filled {quantity_fills} quantity rows, "
                f"{entry_fills} entry_price rows, "
                f"{exit_fills} exit_price rows, "
                f"fixed {profit_fixes} profit_loss rows, "
                f"{balance_fixes} balance rows"
            )
            for warning in warnings:
                print(warning)
        else:
            print(f"[OK] {csv_path.name}: empty cells={empty_cells}, no discrepancies found")

        if error_message:
            errored_files += 1
            print(error_message)
            continue

        total_quantity_fills += quantity_fills
        total_entry_fills += entry_fills
        total_exit_fills += exit_fills
        total_profit_fixes += profit_fixes
        total_balance_fixes += balance_fixes
        total_empty_cells += empty_cells

    print(
        f"\nSummary: files with warnings={files_with_warnings}, "
        f"empty cells={total_empty_cells}, "
        f"quantity fills={total_quantity_fills}, "
        f"entry_price fills={total_entry_fills}, "
        f"exit_price fills={total_exit_fills}, "
        f"profit_loss fixes={total_profit_fixes}, "
        f"balance fixes={total_balance_fixes}, errors={errored_files}"
    )

    return 1 if errored_files else 0


if __name__ == "__main__":
    raise SystemExit(main())
