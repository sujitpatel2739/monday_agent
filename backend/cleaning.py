import pandas as pd
import re

EMPTY_TAGS = ['None', 'none', 'Nan', 'nan', '', 'N/A', 'n/a', 'NA', 'na',
              'INF', 'inf', 'null', 'NULL', '-', '--']

def clean_currency(val):
    """Convert messy currency strings to float. e.g. '$12,000', '12K', '1.2L' → float"""
    if pd.isna(val) or str(val).strip() in EMPTY_TAGS:
        return pd.NA
    val_str = str(val).lower().replace('$', '').replace('₹', '').replace(',', '').strip()
    # Handle lakh (Indian numbering)
    if 'l' in val_str:
        try:
            return float(val_str.replace('l', '')) * 100000
        except ValueError:
            return pd.NA
    if 'k' in val_str:
        try:
            return float(val_str.replace('k', '')) * 1000
        except ValueError:
            return pd.NA
    try:
        return float(val_str)
    except ValueError:
        return pd.NA


def clean_deals_data(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Cleans the Deals board DataFrame.
    Returns (cleaned_df, caveats) where caveats is a list of human-readable warnings.
    """
    if df.empty:
        return df, ["Warning: Deals board returned no data."]

    cleaned = df.copy()
    caveats = []

    # ── Rename Item Name → Deal Name ──────────────────────────────────────
    if "Item Name" in cleaned.columns:
        cleaned.rename(columns={"Item Name": "Deal Name"}, inplace=True)

    # ── 1. Categorical columns ─────────────────────────────────────────────
    cat_cols = [c for c in cleaned.columns
                if any(x in c.lower() for x in ['sector', 'status', 'stage', 'priority', 'probability', 'product'])]
    for col in cat_cols:
        cleaned[col] = cleaned[col].astype(str).str.strip().str.title()
        missing = cleaned[col].isin([s.title() for s in EMPTY_TAGS] + EMPTY_TAGS).sum()
        if missing:
            cleaned[col] = cleaned[col].replace(
                {s: 'Unknown' for s in [s.title() for s in EMPTY_TAGS] + EMPTY_TAGS}
            )
            caveats.append(f"{missing} missing/invalid entries in '{col}' → set to 'Unknown'.")

    # ── 2. Numeric / financial columns ────────────────────────────────────
    num_cols = [c for c in cleaned.columns
                if any(x in c.lower() for x in ['value', 'amount', 'revenue', 'price', 'gst'])]
    for col in num_cols:
        cleaned[col] = cleaned[col].apply(clean_currency)
        cleaned[col] = pd.to_numeric(cleaned[col], errors='coerce')
        nan_count = cleaned[col].isna().sum()
        if nan_count:
            cleaned[col] = cleaned[col].fillna(0)
            caveats.append(f"{nan_count} missing/unreadable values in '{col}' → assumed ₹0.")

    # ── 3. Date columns ────────────────────────────────────────────────────
    date_cols = [c for c in cleaned.columns if 'date' in c.lower() or 'month' in c.lower()]
    for col in date_cols:
        pre_na = cleaned[col].isna().sum()
        cleaned[col] = pd.to_datetime(cleaned[col], errors='coerce')
        new_na = cleaned[col].isna().sum() - pre_na
        if new_na > 0:
            caveats.append(f"{new_na} unparseable dates in '{col}' → left as missing.")
        cleaned[col] = cleaned[col].dt.strftime('%Y-%m-%d').replace('NaT', 'Unknown')

    # ── 4. Deal Stage ordering hint ───────────────────────────────────────
    stage_order = {
        'A. Lead Generated': 1, 'B. Sales Qualified Leads': 2,
        'C. Demo Done': 3, 'D. Feasibility': 4,
        'E. Proposal/Commercials Sent': 5, 'F. Negotiations': 6,
        'G. Project Won': 7, 'H. Work Order Received': 8,
        'I. Poc': 9, 'J. Invoice Sent': 10,
        'K. Amount Accrued': 11, 'L. Project Lost': 12,
        'M. Projects On Hold': 13
    }
    if 'Deal Stage' in cleaned.columns:
        cleaned['Stage Order'] = cleaned['Deal Stage'].map(stage_order).fillna(99).astype(int)

    return cleaned, caveats


def clean_workorder_data(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Cleans the Work Orders board DataFrame.
    Returns (cleaned_df, caveats).
    """
    if df.empty:
        return df, ["Warning: Work Orders board returned no data."]

    cleaned = df.copy()
    caveats = []

    cleaned.columns = cleaned.columns.str.strip()

    if "Item Name" in cleaned.columns:
        cleaned.rename(columns={"Item Name": "Deal Name"}, inplace=True)

    # ── 1. Categorical columns ─────────────────────────────────────────────
    cat_cols = [c for c in cleaned.columns
                if any(x in c.lower() for x in ['status', 'priority', 'sector', 'type', 'nature', 'document'])]
    for col in cat_cols:
        cleaned[col] = cleaned[col].astype(str).str.strip().str.title()
        missing = cleaned[col].isin([s.title() for s in EMPTY_TAGS] + EMPTY_TAGS).sum()
        if missing:
            cleaned[col] = cleaned[col].replace(
                {s: 'Unknown' for s in [s.title() for s in EMPTY_TAGS] + EMPTY_TAGS}
            )
            caveats.append(f"{missing} missing entries in '{col}' → set to 'Unknown'.")

    # ── 2. Financial columns ───────────────────────────────────────────────
    fin_cols = [c for c in cleaned.columns
                if any(x in c.lower() for x in ['amount', 'billed', 'collected', 'receivable', 'gst', 'bill'])]
    for col in fin_cols:
        cleaned[col] = cleaned[col].apply(clean_currency)
        cleaned[col] = pd.to_numeric(cleaned[col], errors='coerce')
        nan_count = cleaned[col].isna().sum()
        if nan_count:
            cleaned[col] = cleaned[col].fillna(0)
            caveats.append(f"{nan_count} missing values in '{col}' → assumed ₹0.")

    # ── 3. Date columns ────────────────────────────────────────────────────
    date_cols = [c for c in cleaned.columns
                 if any(x in c.lower() for x in ['date', 'month', 'timeline', 'deadline'])]
    for col in date_cols:
        pre_na = cleaned[col].isna().sum()
        cleaned[col] = pd.to_datetime(cleaned[col], errors='coerce')
        new_na = cleaned[col].isna().sum() - pre_na
        if new_na > 0:
            caveats.append(f"{new_na} unparseable dates in '{col}' → left as missing.")
        cleaned[col] = cleaned[col].dt.strftime('%Y-%m-%d').replace('NaT', 'Unknown')

    return cleaned, caveats
