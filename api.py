import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

MONDAY_API_URL = "https://api.monday.com/v2"
HEADERS = {
    "Authorization": os.getenv("MONDAY_API_TOKEN"),
    "API-Version": "2024-01"
}

def fetch_board_data(board_id: int) -> pd.DataFrame:
    """
    Fetches live data from a Monday.com board and returns it as a Pandas DataFrame.
    """
    # GraphQL query to get items and their column values
    query = """
    query ($board_id: [ID!]) {
      boards (ids: $board_id) {
        items_page (limit: 100) {
          items {
            name
            column_values {
              column {
                title
              }
              text
            }
          }
        }
      }
    }
    """
    
    variables = {"board_id": [board_id]}
    
    response = requests.post(
        MONDAY_API_URL, 
        json={"query": query, "variables": variables}, 
        headers=HEADERS
    )
    
    response.raise_for_status()
    data = response.json()
    
    # Extracting items
    try:
        items = data['data']['boards'][0]['items_page']['items']
    except (KeyError, IndexError):
        return pd.DataFrame()
    
    # Flattening the JSON into a structured dictionary for Pandas
    parsed_items = []
    for item in items:
        row = {"Item Name": item.get("name")}
        for col in item.get("column_values", []):
            col_title = col['column']['title']
            col_text = col['text']
            row[col_title] = col_text
        parsed_items.append(row)
        
    return pd.DataFrame(parsed_items)


# --- Quick Test ---
# if __name__ == "__main__":
    # WORK_ORDERS_BOARD_ID = 5026937422
    
    # print("Fetching live Work Orders data...")
    # df_work_orders = fetch_board_data(WORK_ORDERS_BOARD_ID)
    # print(df_work_orders.head())
