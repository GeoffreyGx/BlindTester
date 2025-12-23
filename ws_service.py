from fastapi import WebSocket

connections: dict[tuple[str, str], WebSocket] = {}

async def connect(game_code: str, user_id: str, ws: WebSocket):
    await ws.accept()
    connections[(game_code, user_id)] = ws

async def disconnect(game_code: str, user_id: str):
    connections.pop((game_code, user_id), None)

async def broadcast(game_code: str, message):
    for (g, _), ws in connections.items():
        if g == game_code:
            try:
                await ws.send_json(message)
            except:
                pass
