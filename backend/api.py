import os
import requests
import pandas as pd

MONDAY_API_URL = "https://api.monday.com/v2"

def get_headers():
    return {
        "Authorization": os.getenv("MONDAY_API_TOKEN"),
        "API-Version": "2024-01",
        "Content-Type": "application/json"
    }

def fetch_board_data(board_id: int) -> pd.DataFrame:
    """
    Fetches ALL items from a Monday.com board using cursor-based pagination.
    Returns a flat Pandas DataFrame.
    """
    all_items = []
    cursor = None

    while True:
        if cursor:
            query = """
            query ($board_id: [ID!], $cursor: String!) {
              boards(ids: $board_id) {
                items_page(limit: 100, cursor: $cursor) {
                  cursor
                  items {
                    name
                    column_values {
                      column { title }
                      text
                    }
                  }
                }
              }
            }
            """
            variables = {"board_id": [board_id], "cursor": cursor}
        else:
            query = """
            query ($board_id: [ID!]) {
              boards(ids: $board_id) {
                items_page(limit: 100) {
                  cursor
                  items {
                    name
                    column_values {
                      column { title }
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
            headers=get_headers()
        )
        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            raise Exception(f"Monday API error: {data['errors']}")

        page = data["data"]["boards"][0]["items_page"]
        items = page["items"]
        cursor = page.get("cursor")

        for item in items:
            row = {"Item Name": item.get("name")}
            for col in item.get("column_values", []):
                row[col["column"]["title"]] = col.get("text", "")
            all_items.append(row)

        if not cursor:
            break

    return pd.DataFrame(all_items)


def test_connection() -> dict:
    """Test if the API token is valid."""
    query = "{ me { name email } }"
    try:
        r = requests.post(
            MONDAY_API_URL,
            json={"query": query},
            headers=get_headers()
        )
        r.raise_for_status()
        data = r.json()
        if "errors" in data:
            return {"ok": False, "error": str(data["errors"])}
        me = data["data"]["me"]
        return {"ok": True, "name": me["name"], "email": me["email"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}
