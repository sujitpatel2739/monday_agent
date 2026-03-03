import os
import json
import pandas as pd
from api import fetch_board_data
from cleaning import clean_deals_data, clean_workorder_data

DEALS_BOARD_ID = int(os.getenv("DEALS_BOARD_ID", "0"))
WORK_ORDERS_BOARD_ID = int(os.getenv("WORK_ORDERS_BOARD_ID", "0"))

_cache = {}

def _get_board(board: str) -> tuple[pd.DataFrame, list[str]]:
    if board in _cache:
        return _cache[board]
    if board == "deals":
        raw = fetch_board_data(DEALS_BOARD_ID)
        df, caveats = clean_deals_data(raw)
    elif board == "work_orders":
        raw = fetch_board_data(WORK_ORDERS_BOARD_ID)
        df, caveats = clean_workorder_data(raw)
    else:
        return pd.DataFrame(), [f"Unknown board: {board}"]
    _cache[board] = (df, caveats)
    return df, caveats

def clear_cache():
    _cache.clear()

def _safe_str(val) -> str:
    """Convert any value to string safely, treating None/NaN as empty."""
    if val is None:
        return ""
    try:
        if pd.isna(val):
            return ""
    except (TypeError, ValueError):
        pass
    return str(val).strip()

def _match_column(name: str, columns) -> str | None:
    """Fuzzy column name matcher."""
    if not name:
        return None
    cols = list(columns)
    if name in cols:
        return name
    lower_map = {c.lower(): c for c in cols}
    if name.lower() in lower_map:
        return lower_map[name.lower()]
    for col in cols:
        if name.lower() in col.lower() or col.lower() in name.lower():
            return col
    return None

def _sanitize_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Replace all None / NaN / NaT with safe defaults before any operation.
    Numeric cols → 0, everything else → empty string.
    """
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        else:
            df[col] = df[col].apply(_safe_str)
    return df


# ── TOOL 1: get_board_schema ──────────────────────────────────────────────
def get_board_schema(board: str) -> tuple[str, list[dict]]:
    trace = [{
        "type": "tool_call",
        "message": f"get_board_schema → {board}",
        "detail": "Fetching columns, row count, unique categoricals"
    }]
    try:
        df, caveats = _get_board(board)
        df = _sanitize_df(df)
    except Exception as e:
        trace.append({"type": "error", "message": str(e)})
        return json.dumps({"error": str(e)}), trace

    cat_keywords = ['sector', 'status', 'stage', 'type', 'nature',
                    'probability', 'document', 'priority', 'personnel', 'owner']
    categoricals = {}
    for col in df.columns:
        if any(k in col.lower() for k in cat_keywords):
            unique_vals = [v for v in df[col].unique().tolist() if v != ""]
            if len(unique_vals) <= 30:
                categoricals[col] = sorted(unique_vals)

    result = {
        "board": board,
        "total_rows": len(df),
        "columns": list(df.columns),
        "categorical_values": categoricals,
        "data_quality_caveats": caveats
    }
    trace.append({
        "type": "api_response",
        "message": f"✓ Schema ready — {len(df)} rows, {len(df.columns)} columns",
        "detail": f"Columns: {list(df.columns)}"
    })
    return json.dumps(result, default=str), trace


# ── TOOL 2: filter_board ──────────────────────────────────────────────────
def filter_board(board: str, filters: dict, columns: list = None,
                 limit: int = 50) -> tuple[str, list[dict]]:
    trace = [{
        "type": "tool_call",
        "message": f"filter_board → {board}",
        "detail": f"Filters: {filters} | Columns: {columns} | Limit: {limit}"
    }]
    try:
        df, caveats = _get_board(board)
        df = _sanitize_df(df)
    except Exception as e:
        trace.append({"type": "error", "message": str(e)})
        return json.dumps({"error": str(e)}), trace

    filters  = filters  or {}
    columns  = columns  or []
    limit    = limit    or 50

    filtered = df.copy()

    for col, val in filters.items():
        matched_col = _match_column(col, filtered.columns)
        if not matched_col:
            trace.append({"type": "processing",
                          "message": f"⚠ Column '{col}' not found, skipping"})
            continue
        if isinstance(val, list):
            val_lower = [str(v).lower().strip() for v in val if v is not None]
            filtered = filtered[
                filtered[matched_col].str.lower().isin(val_lower)
            ]
        else:
            filtered = filtered[
                filtered[matched_col].str.lower()
                .str.contains(str(val).lower().strip(), na=False)
            ]

    if columns:
        valid_cols = [_match_column(c, filtered.columns) for c in columns]
        valid_cols = [c for c in valid_cols if c]
        if valid_cols:
            filtered = filtered[valid_cols]

    total_matched = len(filtered)
    filtered = filtered.head(int(limit))

    trace.append({
        "type": "api_response",
        "message": f"✓ {total_matched} rows matched, returning {len(filtered)}",
        "detail": f"Filters: {filters}"
    })

    result = {
        "board": board,
        "filters_applied": filters,
        "total_matched": total_matched,
        "rows_returned": len(filtered),
        "data": filtered.to_dict(orient="records"),
        "data_quality_caveats": caveats
    }
    return json.dumps(result, default=str), trace


# ── TOOL 3: aggregate_board ───────────────────────────────────────────────
def aggregate_board(board: str, group_by: str, metrics: list = None,
                    filters: dict = None) -> tuple[str, list[dict]]:
    trace = [{
        "type": "tool_call",
        "message": f"aggregate_board → {board}",
        "detail": f"Group by: {group_by} | Metrics: {metrics} | Filters: {filters}"
    }]
    try:
        df, caveats = _get_board(board)
        df = _sanitize_df(df)
    except Exception as e:
        trace.append({"type": "error", "message": str(e)})
        return json.dumps({"error": str(e)}), trace

    metrics = metrics or ["count:Deal Name"]
    filters = filters or {}

    # Apply pre-filters
    for col, val in filters.items():
        matched_col = _match_column(col, df.columns)
        if not matched_col:
            continue
        if isinstance(val, list):
            val_lower = [str(v).lower().strip() for v in val if v is not None]
            df = df[df[matched_col].str.lower().isin(val_lower)]
        else:
            df = df[df[matched_col].str.lower()
                    .str.contains(str(val).lower().strip(), na=False)]

    group_col = _match_column(group_by, df.columns)
    if not group_col:
        result = {"error": f"Column '{group_by}' not found. Available: {list(df.columns)}"}
        return json.dumps(result), trace

    # Remove empty group keys
    df = df[df[group_col] != ""]

    # Build named aggregations
    agg_dict = {}
    for metric in metrics:
        if not metric or ":" not in metric:
            continue
        parts = metric.split(":", 1)
        func, col = parts[0].strip(), parts[1].strip()
        matched_col = _match_column(col, df.columns)
        if not matched_col:
            continue
        safe_func = func if func in ("sum", "mean", "min", "max") else "count"
        key = f"{func}_{matched_col}".replace(" ", "_")
        agg_dict[key] = pd.NamedAgg(column=matched_col, aggfunc=safe_func)

    # Always include count
    first_col = df.columns[0]
    agg_dict["count"] = pd.NamedAgg(column=first_col, aggfunc="count")

    try:
        grouped = df.groupby(group_col, dropna=True).agg(**agg_dict).reset_index()
        # Sort by first metric descending
        sort_col = list(agg_dict.keys())[0]
        if sort_col in grouped.columns:
            grouped = grouped.sort_values(sort_col, ascending=False)
    except Exception as e:
        return json.dumps({"error": f"Aggregation failed: {str(e)}"}), trace

    trace.append({
        "type": "api_response",
        "message": f"✓ {len(grouped)} groups returned",
        "detail": f"Grouped '{board}' by '{group_col}'"
    })

    result = {
        "board": board,
        "group_by": group_col,
        "total_groups": len(grouped),
        "data": grouped.to_dict(orient="records"),
        "data_quality_caveats": caveats
    }
    return json.dumps(result, default=str), trace


# ── TOOL 4: get_board_chunk ───────────────────────────────────────────────
def get_board_chunk(board: str, offset: int = 0, limit: int = 50,
                    columns: list = None) -> tuple[str, list[dict]]:
    trace = [{
        "type": "tool_call",
        "message": f"get_board_chunk → {board}",
        "detail": f"Offset: {offset} | Limit: {limit} | Columns: {columns}"
    }]
    try:
        df, caveats = _get_board(board)
        df = _sanitize_df(df)
    except Exception as e:
        trace.append({"type": "error", "message": str(e)})
        return json.dumps({"error": str(e)}), trace

    offset  = int(offset or 0)
    limit   = int(limit  or 50)
    columns = columns or []

    if columns:
        valid_cols = [_match_column(c, df.columns) for c in columns]
        valid_cols = [c for c in valid_cols if c]
        if valid_cols:
            df = df[valid_cols]

    chunk    = df.iloc[offset: offset + limit]
    has_more = (offset + limit) < len(df)

    trace.append({
        "type": "api_response",
        "message": f"✓ Rows {offset}–{offset+len(chunk)} of {len(df)} returned",
        "detail": f"has_more: {has_more}"
    })

    result = {
        "board": board,
        "total_rows": len(df),
        "offset": offset,
        "rows_returned": len(chunk),
        "has_more": has_more,
        "next_offset": offset + limit if has_more else None,
        "data": chunk.to_dict(orient="records"),
        "data_quality_caveats": caveats
    }
    return json.dumps(result, default=str), trace


# ── HELPER ────────────────────────────────────────────────────────────────
def _match_column(name: str, columns) -> str | None:
    """
    Fuzzy column matcher — handles slight name mismatches.
    Tries exact match first, then case-insensitive, then partial.
    """
    cols = list(columns)
    # Exact
    if name in cols:
        return name
    # Case-insensitive exact
    lower_map = {c.lower(): c for c in cols}
    if name.lower() in lower_map:
        return lower_map[name.lower()]
    # Partial match
    for col in cols:
        if name.lower() in col.lower() or col.lower() in name.lower():
            return col
    return None