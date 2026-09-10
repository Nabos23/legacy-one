import json
import httpx

from ai.connectors.base import BaseConnector

_BASE = "https://api.monday.com/v2"


def _handle_error(tool_name: str, e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code in (401, 403):
            return (
                f"Authorization error in {tool_name}: the connected Monday.com account lacks permission "
                f"(HTTP {e.response.status_code}). Ask the user to reconnect their Monday.com connector."
            )
        return f"API error in {tool_name} (HTTP {e.response.status_code}): {e.response.text[:300]}"
    return f"Unexpected error in {tool_name}: {e}"


def _gql(token: str, query: str, variables: dict | None = None) -> dict:
    headers = {"Authorization": token, "Content-Type": "application/json", "API-Version": "2024-01"}
    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables
    resp = httpx.post(_BASE, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise ValueError(str(data["errors"]))
    return data.get("data", {})


class MondayConnector(BaseConnector):

    PROVIDER_ID = "monday"

    def list_boards(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "monday_list_boards", inp)
        if permission_error: return permission_error
        try:
            query = """
            query($limit: Int) {
                boards(limit: $limit, order_by: created_at) {
                    id name description state board_kind
                }
            }"""
            data = _gql(self._token, query, {"limit": inp.get("limit", 20)})
            return json.dumps({"boards": data.get("boards", [])})
        except Exception as e:
            return _handle_error("monday_list_boards", e)

    def list_items(self, inp: dict) -> str:
        permission_error, board_id = self._check(self.agent_id, self.PROVIDER_ID, "monday_list_items", inp, "board_id")
        if permission_error: return permission_error
        try:
            query = """
            query($board_id: ID!, $limit: Int) {
                boards(ids: [$board_id]) {
                    items_page(limit: $limit) {
                        items {
                            id name state
                            column_values { id text }
                            group { id title }
                        }
                    }
                }
            }"""
            data = _gql(self._token, query, {"board_id": board_id, "limit": inp.get("limit", 25)})
            boards = data.get("boards", [])
            if not boards:
                return json.dumps({"items": []})
            items_page = boards[0].get("items_page", {})
            items = [
                {
                    "id": i["id"],
                    "name": i["name"],
                    "state": i["state"],
                    "group": i.get("group", {}).get("title"),
                    "columns": {c["id"]: c["text"] for c in i.get("column_values", []) if c.get("text")},
                }
                for i in items_page.get("items", [])
            ]
            return json.dumps({"items": items, "count": len(items)})
        except Exception as e:
            return _handle_error("monday_list_items", e)

    def get_item(self, inp: dict) -> str:
        permission_error, item_id = self._check(self.agent_id, self.PROVIDER_ID, "monday_get_item", inp, "item_id")
        if permission_error: return permission_error
        try:
            query = """
            query($item_id: ID!) {
                items(ids: [$item_id]) {
                    id name state
                    column_values { id title text }
                    group { title }
                    board { id name }
                    updates(limit: 3) { id text_body created_at }
                }
            }"""
            data = _gql(self._token, query, {"item_id": item_id})
            items = data.get("items", [])
            if not items:
                return json.dumps({"error": "Item not found."})
            i = items[0]
            return json.dumps({
                "id": i["id"],
                "name": i["name"],
                "state": i["state"],
                "group": i.get("group", {}).get("title"),
                "board": i.get("board", {}).get("name"),
                "columns": {c["title"]: c["text"] for c in i.get("column_values", []) if c.get("text")},
                "recent_updates": [{"text": u["text_body"], "created_at": u["created_at"]} for u in i.get("updates", [])],
            })
        except Exception as e:
            return _handle_error("monday_get_item", e)

    def create_item(self, inp: dict) -> str:
        permission_error, board_id, item_name = self._check(self.agent_id, self.PROVIDER_ID, "monday_create_item", inp, "board_id", "item_name")
        if permission_error: return permission_error
        try:
            query = """
            mutation($board_id: ID!, $item_name: String!, $group_id: String, $column_values: JSON) {
                create_item(board_id: $board_id, item_name: $item_name, group_id: $group_id, column_values: $column_values) {
                    id name
                }
            }"""
            variables: dict = {"board_id": board_id, "item_name": item_name}
            if inp.get("group_id"):
                variables["group_id"] = inp["group_id"]
            if inp.get("column_values"):
                variables["column_values"] = json.dumps(inp["column_values"])
            data = _gql(self._token, query, variables)
            item = data.get("create_item", {})
            return json.dumps({"id": item.get("id"), "name": item.get("name"), "status": "created"})
        except Exception as e:
            return _handle_error("monday_create_item", e)

    def update_item_column(self, inp: dict) -> str:
        permission_error, board_id, item_id, column_id, value = self._check(self.agent_id, self.PROVIDER_ID, "monday_update_item_column", inp, "board_id", "item_id", "column_id", "value")
        if permission_error: return permission_error
        try:
            query = """
            mutation($board_id: ID!, $item_id: ID!, $column_id: String!, $value: JSON!) {
                change_column_value(board_id: $board_id, item_id: $item_id, column_id: $column_id, value: $value) {
                    id
                }
            }"""
            column_value = json.dumps(value) if not isinstance(value, str) else json.dumps({"label": value})
            data = _gql(self._token, query, {"board_id": board_id, "item_id": item_id, "column_id": column_id, "value": column_value})
            return json.dumps({"item_id": item_id, "column_id": column_id, "status": "updated"})
        except Exception as e:
            return _handle_error("monday_update_item_column", e)

    def add_update(self, inp: dict) -> str:
        permission_error, item_id, body = self._check(self.agent_id, self.PROVIDER_ID, "monday_add_update", inp, "item_id", "body")
        if permission_error: return permission_error
        try:
            query = """
            mutation($item_id: ID!, $body: String!) {
                create_update(item_id: $item_id, body: $body) { id text_body }
            }"""
            data = _gql(self._token, query, {"item_id": item_id, "body": body})
            update = data.get("create_update", {})
            return json.dumps({"id": update.get("id"), "text": update.get("text_body"), "status": "update_added"})
        except Exception as e:
            return _handle_error("monday_add_update", e)

    def search_items(self, inp: dict) -> str:
        permission_error, board_id, query_term = self._check(self.agent_id, self.PROVIDER_ID, "monday_search_items", inp, "board_id", "query")
        if permission_error: return permission_error
        try:
            query = """
            query($board_id: ID!, $query: String!) {
                boards(ids: [$board_id]) {
                    items_page(query_params: {rules: [{column_id: "name", compare_value: [$query]}]}) {
                        items { id name state }
                    }
                }
            }"""
            data = _gql(self._token, query, {"board_id": board_id, "query": query_term})
            boards = data.get("boards", [])
            if not boards:
                return json.dumps({"items": []})
            items = boards[0].get("items_page", {}).get("items", [])
            return json.dumps({"items": items, "count": len(items)})
        except Exception as e:
            return _handle_error("monday_search_items", e)

    def delete_item(self, inp: dict) -> str:
        permission_error, item_id = self._check(self.agent_id, self.PROVIDER_ID, "monday_delete_item", inp, "item_id")
        if permission_error: return permission_error
        try:
            query = """
            mutation($item_id: ID!) {
                delete_item(item_id: $item_id) { id }
            }"""
            data = _gql(self._token, query, {"item_id": item_id})
            deleted = data.get("delete_item", {})
            return json.dumps({"deleted": True, "id": deleted.get("id")})
        except Exception as e:
            return _handle_error("monday_delete_item", e)

    def list_groups(self, inp: dict) -> str:
        permission_error, board_id = self._check(self.agent_id, self.PROVIDER_ID, "monday_list_groups", inp, "board_id")
        if permission_error: return permission_error
        try:
            query = """
            query($board_id: ID!) {
                boards(ids: [$board_id]) {
                    groups { id title }
                }
            }"""
            data = _gql(self._token, query, {"board_id": board_id})
            boards = data.get("boards", [])
            if not boards:
                return json.dumps({"groups": []})
            groups = boards[0].get("groups", [])
            return json.dumps({"groups": groups, "count": len(groups)})
        except Exception as e:
            return _handle_error("monday_list_groups", e)

    def list_columns(self, inp: dict) -> str:
        permission_error, board_id = self._check(self.agent_id, self.PROVIDER_ID, "monday_list_columns", inp, "board_id")
        if permission_error: return permission_error
        try:
            query = """
            query($board_id: ID!) {
                boards(ids: [$board_id]) {
                    columns { id title type }
                }
            }"""
            data = _gql(self._token, query, {"board_id": board_id})
            boards = data.get("boards", [])
            if not boards:
                return json.dumps({"columns": []})
            columns = boards[0].get("columns", [])
            return json.dumps({"columns": columns, "count": len(columns)})
        except Exception as e:
            return _handle_error("monday_list_columns", e)

    def create_group(self, inp: dict) -> str:
        permission_error, board_id, group_name = self._check(self.agent_id, self.PROVIDER_ID, "monday_create_group", inp, "board_id", "group_name")
        if permission_error: return permission_error
        try:
            query = """
            mutation($board_id: ID!, $group_name: String!) {
                create_group(board_id: $board_id, group_name: $group_name) { id }
            }"""
            data = _gql(self._token, query, {"board_id": board_id, "group_name": group_name})
            group = data.get("create_group", {})
            return json.dumps({"id": group.get("id"), "group_name": group_name, "status": "created"})
        except Exception as e:
            return _handle_error("monday_create_group", e)

    def create_board(self, inp: dict) -> str:
        permission_error, board_name = self._check(self.agent_id, self.PROVIDER_ID, "monday_create_board", inp, "board_name")
        if permission_error: return permission_error
        board_kind = inp.get("board_kind", "public")
        try:
            query = """
            mutation($board_name: String!, $board_kind: BoardKind!) {
                create_board(board_name: $board_name, board_kind: $board_kind) { id name }
            }"""
            data = _gql(self._token, query, {"board_name": board_name, "board_kind": board_kind})
            board = data.get("create_board", {})
            return json.dumps({"id": board.get("id"), "name": board.get("name"), "status": "created"})
        except Exception as e:
            return _handle_error("monday_create_board", e)

    def list_users(self, inp: dict) -> str:
        permission_error, = self._check(self.agent_id, self.PROVIDER_ID, "monday_list_users", inp)
        if permission_error: return permission_error
        try:
            query = """
            query($limit: Int) {
                users(limit: $limit) { id name email enabled is_admin }
            }"""
            data = _gql(self._token, query, {"limit": inp.get("limit", 50)})
            users = data.get("users", [])
            return json.dumps({"users": users, "count": len(users)})
        except Exception as e:
            return _handle_error("monday_list_users", e)

    def move_item_to_group(self, inp: dict) -> str:
        permission_error, item_id, group_id = self._check(self.agent_id, self.PROVIDER_ID, "monday_move_item_to_group", inp, "item_id", "group_id")
        if permission_error: return permission_error
        try:
            query = """
            mutation($item_id: ID!, $group_id: String!) {
                move_item_to_group(item_id: $item_id, group_id: $group_id) { id }
            }"""
            data = _gql(self._token, query, {"item_id": item_id, "group_id": group_id})
            item = data.get("move_item_to_group", {})
            return json.dumps({"id": item.get("id"), "group_id": group_id, "status": "moved"})
        except Exception as e:
            return _handle_error("monday_move_item_to_group", e)

    def as_tools(self) -> tuple[list[dict], dict[str, callable]]:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "monday_list_boards",
                    "description": "List all Monday.com boards in the workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {"limit": {"type": "integer", "description": "Max boards to return (default 20)."}},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "monday_list_items",
                    "description": "List items (rows) in a Monday.com board.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "board_id": {"type": "string", "description": "Monday.com board ID."},
                            "limit": {"type": "integer", "description": "Max items to return (default 25)."},
                        },
                        "required": ["board_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "monday_get_item",
                    "description": "Get full details of a specific Monday.com item including column values and recent updates.",
                    "parameters": {
                        "type": "object",
                        "properties": {"item_id": {"type": "string", "description": "Monday.com item ID."}},
                        "required": ["item_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "monday_create_item",
                    "description": "Create a new item in a Monday.com board.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "board_id": {"type": "string", "description": "Board ID to add the item to."},
                            "item_name": {"type": "string", "description": "Name of the new item."},
                            "group_id": {"type": "string", "description": "Optional group/section ID to place the item in."},
                            "column_values": {"type": "object", "description": "Optional column values as a dict of column_id to value."},
                        },
                        "required": ["board_id", "item_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "monday_update_item_column",
                    "description": "Update a specific column value of a Monday.com item (e.g. change status, due date, assignee). Use monday_list_columns first to get column IDs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "board_id": {"type": "string", "description": "Board ID."},
                            "item_id": {"type": "string", "description": "Item ID."},
                            "column_id": {"type": "string", "description": "Column ID to update (e.g. 'status', 'date4'). Use monday_list_columns to discover IDs."},
                            "value": {"type": "string", "description": "New value for the column."},
                        },
                        "required": ["board_id", "item_id", "column_id", "value"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "monday_add_update",
                    "description": "Add a comment/update to a Monday.com item.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "Item ID to add the update to."},
                            "body": {"type": "string", "description": "Update/comment text."},
                        },
                        "required": ["item_id", "body"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "monday_search_items",
                    "description": "Search for items by name within a Monday.com board.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "board_id": {"type": "string", "description": "Board ID to search within."},
                            "query": {"type": "string", "description": "Search term to match against item names."},
                        },
                        "required": ["board_id", "query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "monday_delete_item",
                    "description": "Permanently delete an item from a Monday.com board.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "ID of the item to delete."},
                        },
                        "required": ["item_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "monday_list_groups",
                    "description": "List groups (sections) within a Monday.com board.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "board_id": {"type": "string", "description": "Board ID to list groups for."},
                        },
                        "required": ["board_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "monday_list_columns",
                    "description": "List all columns in a Monday.com board. Use this to discover column IDs before calling monday_update_item_column.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "board_id": {"type": "string", "description": "Board ID to list columns for."},
                        },
                        "required": ["board_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "monday_create_group",
                    "description": "Create a new group (section) in a Monday.com board.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "board_id": {"type": "string", "description": "Board ID to create the group in."},
                            "group_name": {"type": "string", "description": "Name of the new group."},
                        },
                        "required": ["board_id", "group_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "monday_create_board",
                    "description": "Create a new Monday.com board.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "board_name": {"type": "string", "description": "Name of the new board."},
                            "board_kind": {"type": "string", "description": "Board kind: 'public', 'private', or 'share'. Defaults to 'public'."},
                        },
                        "required": ["board_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "monday_list_users",
                    "description": "List users in the Monday.com account.",
                    "parameters": {
                        "type": "object",
                        "properties": {"limit": {"type": "integer", "description": "Max users to return (default 50)."}},
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "monday_move_item_to_group",
                    "description": "Move an item to a different group (section) within the same board.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_id": {"type": "string", "description": "Item ID to move."},
                            "group_id": {"type": "string", "description": "Target group ID."},
                        },
                        "required": ["item_id", "group_id"],
                    },
                },
            },
        ]
        callables = {
            "monday_list_boards": self.list_boards,
            "monday_list_items": self.list_items,
            "monday_get_item": self.get_item,
            "monday_create_item": self.create_item,
            "monday_update_item_column": self.update_item_column,
            "monday_add_update": self.add_update,
            "monday_search_items": self.search_items,
            "monday_delete_item": self.delete_item,
            "monday_list_groups": self.list_groups,
            "monday_list_columns": self.list_columns,
            "monday_create_group": self.create_group,
            "monday_create_board": self.create_board,
            "monday_list_users": self.list_users,
            "monday_move_item_to_group": self.move_item_to_group,
        }
        return tools, callables
