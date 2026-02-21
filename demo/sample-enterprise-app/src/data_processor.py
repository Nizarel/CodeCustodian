"""Data processing module — legacy patterns throughout."""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional


# TODO: migrate to pd.concat() before pandas 3.0 removes append — added 2024-01-15
def merge_inventory_batches(batches: List[Dict]) -> pd.DataFrame:
    """Merge incoming inventory batches into a single DataFrame."""
    result = pd.DataFrame()
    for batch in batches:
        row = pd.DataFrame([batch])
        result = result.append(row, ignore_index=True)
    return result


# FIXME: iteritems() is deprecated since pandas 1.5 — use items() instead
def summarize_columns(df: pd.DataFrame) -> dict:
    summary = {}
    for col_name, col_data in df.iteritems():
        summary[col_name] = {
            "mean": col_data.mean() if col_data.dtype in [np.float(64), np.int(64)] else None,
            "count": len(col_data),
        }
    return summary


def cast_legacy_types(values):
    """Convert values using deprecated numpy type aliases."""
    results = []
    for v in values:
        results.append(np.float(v))
    return results


# HACK: this entire function is a workaround for broken upstream API
def normalize_prices(df, region, currency, tax_rate, discount, rounding, verbose):
    """Normalize product prices — too many parameters, deeply nested logic."""
    output = []
    for _, row in df.iterrows():
        price = row["price"]
        if region == "US":
            if currency == "USD":
                if tax_rate > 0:
                    if discount > 0:
                        if rounding:
                            price = round(price * (1 + tax_rate) * (1 - discount), 2)
                        else:
                            price = price * (1 + tax_rate) * (1 - discount)
                    else:
                        price = price * (1 + tax_rate)
                else:
                    price = price
            else:
                price = price * 1.1
        elif region == "EU":
            if currency == "EUR":
                if tax_rate > 0:
                    price = price * (1 + tax_rate * 1.2)
                else:
                    price = price
            else:
                price = price * 1.15
        elif region == "APAC":
            price = price * 1.05
        else:
            price = price

        if verbose:
            print(f"Processed price: {price}")

        output.append(price)
    return output


def _unused_legacy_helper():
    """Dead code — this was replaced by normalize_prices but never removed."""
    pass


def _old_batch_merger():
    """Dead code — superseded by merge_inventory_batches."""
    pass
