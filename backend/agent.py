import os
import json
from groq import Groq
from tools import (
    get_board_schema, filter_board,
    aggregate_board, get_board_chunk, clear_cache
)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """You are an expert Business Intelligence Agent for company founders.

You have two Monday.com boards:
- deals: sales pipeline (stages A-O, sectors, deal values, status, owners)
- work_orders: project delivery (execution status, billing, collections, sectors)

All financial values are in Indian Rupees (INR).

You have ONE tool: monday_query
Call it with an "action" field to choose what to do:

ACTIONS:
1. action="schema"      → learn columns and unique values of a board
2. action="aggregate"   → get grouped totals (e.g. deal value by sector)
3. action="filter"      → get specific rows matching conditions
4. action="chunk"       → paginate through raw rows

WORKFLOW:
- Start with action="schema" on the relevant board
- Then use action="aggregate" for summary/totals questions
- Use action="filter" for specific row-level questions
- Only use action="chunk" if no filter applies
- NEVER answer without calling the tool first

RULES:
- Never invent numbers
- Always report data quality caveats from tool results
- Format INR with Indian commas e.g. ₹1,23,45,678
- For cross-board questions, query both boards
"""

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "monday_query",
            "description": "Query live Monday.com board data. Use action field to choose: schema, aggregate, filter, or chunk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["schema", "aggregate", "filter", "chunk"],
                        "description": "schema=get columns/values, aggregate=group-by totals, filter=get matching rows, chunk=paginate raw rows"
                    },
                    "board": {
                        "type": "string",
                        "enum": ["deals", "work_orders"],
                        "description": "Which board to query"
                    },
                    "group_by": {
                        "type": "string",
                        "description": "For aggregate: column to group by. e.g. 'Sector', 'Deal Stage'"
                    },
                    "metrics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "For aggregate: list of 'function:column'. e.g. ['sum:Deal Value', 'count:Deal Name']"
                    },
                    "filters": {
                        "type": "object",
                        "description": "For filter/aggregate: column-value pairs. e.g. {\"Sector\": \"Mining\"} or {\"Deal Status\": [\"Open\", \"Won\"]}"
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "For filter/chunk: which columns to return. Always specify to keep response small."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max rows to return. Default 50."
                    },
                    "offset": {
                        "type": "integer",
                        "description": "For chunk: row offset for pagination. Default 0."
                    }
                },
                "required": ["action", "board"]
            }
        }
    }
]


def execute_query(args: dict) -> tuple[str, list[dict]]:
    """Route the unified tool call to the correct underlying function."""
    action = args.get("action")
    board  = args.get("board")

    if action == "schema":
        return get_board_schema(board)

    elif action == "aggregate":
        group_by = args.get("group_by", "")
        metrics  = args.get("metrics", ["count:Deal Name"])
        filters  = args.get("filters", None)
        if not group_by:
            return json.dumps({"error": "group_by is required for aggregate action"}), []
        return aggregate_board(board, group_by, metrics, filters)

    elif action == "filter":
        filters = args.get("filters", {})
        columns = args.get("columns", None)
        limit   = args.get("limit", 50)
        return filter_board(board, filters, columns, limit)

    elif action == "chunk":
        offset  = args.get("offset", 0)
        limit   = args.get("limit", 50)
        columns = args.get("columns", None)
        return get_board_chunk(board, offset, limit, columns)
 
    else:
        return json.dumps({"error": f"Unknown action: {action}"}), []


def run_agent(user_query: str, conversation_history: list) -> tuple[str, list, list[dict]]:
    """
    Runs the Groq agent with single unified tool.
    Returns (final_answer, updated_history, all_trace_events)
    """
    clear_cache()
    conversation_history.append({"role": "user", "content": user_query})
    all_traces = []

    MAX_TURNS = 8  # prevent infinite loops
    turns = 0

    while turns < MAX_TURNS:
        turns += 1

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=conversation_history,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=0.0,
            max_tokens=2048
        )

        response_message = response.choices[0].message

        # No tool calls, then return final answer
        if not response_message.tool_calls:
            answer = response_message.content or "Could not generate a response."
            conversation_history.append({
                "role": "assistant",
                "content": answer
            })
            return answer, conversation_history, all_traces

        # Save assistant turn
        conversation_history.append({
            "role": "assistant",
            "content": response_message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in response_message.tool_calls
            ]
        })

        # Execute each tool call
        for tool_call in response_message.tool_calls:
            try:
                args = json.loads(tool_call.function.arguments)
            except (json.JSONDecodeError, TypeError):
                args = {}

            action = args.get("action", "?")
            board  = args.get("board", "?")

            all_traces.append({
                "type": "tool_call",
                "message": f"monday_query → action={action}, board={board}",
                "detail": json.dumps(
                    {k: v for k, v in args.items() if k not in ("action", "board")},
                    default=str
                )
            })

            result_str, trace_events = execute_query(args)
            all_traces.extend(trace_events)

            conversation_history.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result_str
            })

    # Hit max turns
    return (
        "Unable to complete the analysis within the allowed steps.",
        conversation_history,
        all_traces
    )