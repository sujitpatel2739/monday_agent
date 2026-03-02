import pandas as pd
import re
from api import fetch_board_data


# Remove $, commas, and handle 'k' for thousands
def clean_currency(val):
    empty_tags = ['None', 'none', 'Nan', 'nan', '', 'N/A', 'n/a', 'NA', 'na', 'INF', 'inf']
    if pd.isna(val) or str(val).strip() in empty_tags:
        return pd.NA
    val_str = str(val).lower().replace('$', '').replace(',', '').strip()
    if 'k' in val_str:
        try:
            return float(val_str.replace('k', '')) * 1000
        except ValueError:
            return pd.NA
    return val_str

def clean_and_prep_data(df: pd.DataFrame, board_name: str) -> tuple[pd.DataFrame, list[str]]:
    """
    Cleans messy board data and returns the cleaned DataFrame along with a list of caveat warnings.
    """
    if df.empty:
        return df, [f"Warning: The {board_name} board returned no data."]
        
    cleaned_df = df.copy()
    caveats = []
    
    empty_tags = ['None', 'none', 'Nan', 'nan', '', 'N/A', 'n/a', 'NA', 'na', 'INF', 'inf']
    
    # 1. Normalize Categorical Strings (e.g., Sector, Status)
    # Target columns that likely contain text categories
    text_cols = [c for c in cleaned_df.columns if any(x in c.lower() for x in ['sector', 'status', 'industry', 'priority'])]
    for col in text_cols:
        # Strip whitespace and title-case for consistency (e.g., ' energy ' -> 'Energy')
        cleaned_df[col] = cleaned_df[col].astype(str).str.strip().str.title()
        
        # Handle explicitly missing text
        missing_count = cleaned_df[col].isin(empty_tags).sum()
        if missing_count > 0:
            cleaned_df[col] = cleaned_df[col].replace(empty_tags, 'Unknown')
            caveats.append(f"Normalized {missing_count} missing/invalid entries in '{col}' to 'Unknown'.")

    # 2. Normalize Financial/Numeric Data (e.g., Revenue, Value, Amount)
    numeric_cols = [c for c in cleaned_df.columns if any(x in c.lower() for x in ['revenue', 'amount', 'value', 'price'])]
    for col in numeric_cols:
        cleaned_df[col] = cleaned_df[col].apply(clean_currency)
        
        # Coerceing to numeric, turning unparseable garbage into NaN
        cleaned_df[col] = pd.to_numeric(cleaned_df[col], errors='coerce')
        
        nan_count = cleaned_df[col].isna().sum()
        if nan_count > 0:
            cleaned_df[col] = cleaned_df[col].fillna(0)
            caveats.append(f"Found {nan_count} missing or unreadable values in '{col}'. Assumed $0 for calculations.")

    # 3. Normalize Dates
    date_cols = [c for c in cleaned_df.columns if 'date' in c.lower()]
    for col in date_cols:
        # pd.to_datetime handles a massive variety of messy string formats automatically
        original_nans = cleaned_df[col].isna().sum()
        cleaned_df[col] = pd.to_datetime(cleaned_df[col], errors='coerce')
        
        new_nans_count = cleaned_df[col].isna().sum()
        invalid_dates_count = new_nans_count - original_nans
        if invalid_dates_count > 0:
            caveats.append(f"Could not parse {invalid_dates_count} dates in '{col}'. Left as missing (NaT).")

    return cleaned_df, caveats


# --- Quick Test ---
if __name__ =='__main__':
    
    DEALS_BOARD_ID = 5026937396
    raw_deals_df = fetch_board_data(DEALS_BOARD_ID)
    clean_deals_df, deals_caveats = clean_and_prep_data(raw_deals_df, "Deals")
    print("Caveats to pass to LLM:", deals_caveats)
