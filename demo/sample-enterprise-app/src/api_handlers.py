"""API handlers — missing type annotations and legacy patterns."""

import json
from pathlib import Path


# NOTE: this module needs complete type annotation pass before release
def get_inventory(warehouse_id, page, limit, sort_by, include_archived):
    """Fetch inventory items — no type hints on any parameter."""
    items = _load_items(warehouse_id)
    if include_archived:
        return items[page * limit : (page + 1) * limit]
    return [i for i in items if not i.get("archived")][page * limit : (page + 1) * limit]


def update_stock(item_id, quantity, reason, updated_by):
    """Update stock level — no type hints."""
    record = {"item_id": item_id, "qty": quantity, "reason": reason, "by": updated_by}
    _save_record(record)
    return record


def delete_item(item_id, soft_delete, reason):
    """Delete an inventory item — no type hints."""
    if soft_delete:
        return {"item_id": item_id, "archived": True, "reason": reason}
    return {"item_id": item_id, "deleted": True}


def search_items(query, category, min_price, max_price, in_stock_only):
    """Search inventory — no type hints, too many parameters."""
    results = []
    all_items = _load_items("all")
    for item in all_items:
        if query.lower() in item.get("name", "").lower():
            if category and item.get("category") != category:
                continue
            if min_price and item.get("price", 0) < min_price:
                continue
            if max_price and item.get("price", 0) > max_price:
                continue
            if in_stock_only and item.get("stock", 0) <= 0:
                continue
            results.append(item)
    return results


def export_report(warehouse_id, format, start_date, end_date):
    """Export inventory report — no type hints."""
    items = _load_items(warehouse_id)
    if format == "json":
        return json.dumps(items)
    elif format == "csv":
        lines = []
        if items:
            lines.append(",".join(items[0].keys()))
            for item in items:
                lines.append(",".join(str(v) for v in item.values()))
        return "\n".join(lines)
    return str(items)


def _load_items(warehouse_id):
    return [
        {"id": 1, "name": "Widget A", "price": 9.99, "stock": 50, "category": "parts"},
        {"id": 2, "name": "Widget B", "price": 14.50, "stock": 0, "category": "parts", "archived": True},
        {"id": 3, "name": "Gadget C", "price": 29.99, "stock": 12, "category": "devices"},
    ]


def _save_record(record):
    pass
