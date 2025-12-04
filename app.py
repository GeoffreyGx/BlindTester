from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import uvicorn
import asyncio
import time
from typing import Dict, Tuple

from obj import Game, Player, User

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # You can restrict this later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir), html=True), name="static")

@app.get("/")
def server_index():
    return FileResponse(static_dir / "index.html")

@app.get("/join")
def serve_join():
    return FileResponse(static_dir / "join.html")

@app.get("/game")
def serve_game():
    return FileResponse(static_dir / "game.html")

@app.get("/join/{game_code}")
def serve_join_with_code(game_code: str):
    return FileResponse(static_dir / "join.html")

games_list: Dict[str, Game] = {}
connections_list: Dict[Tuple[str, str], WebSocket] = {}
active_timers: Dict[str, asyncio.Task] = {}  # Track active answer timers per game


async def broadcast(game_code: str, message: dict):
    """Send a message to all web sockets in the same game."""
    targets = [
        ws for (gcode, _), ws in connections_list.items()
        if gcode == game_code
    ]

    for ws in targets:
        try:
            await ws.send_json(message)
        except Exception:
            # Ignore broken connections and let cleanup handle them
            pass


async def timer_task(game_code: str):
    """Wait 15 seconds and broadcast time limit exceeded."""
    await asyncio.sleep(15)

    game = games_list.get(game_code)
    if not game:
        return

    song = game.getCurrentSong()
    title = song.title if song else None
    artist = song.artist if song else None
    youtube_url = song.youtube_url if song else None

    await broadcast(
        game_code,
        {
            "action": "time_limit_exceeded",
            "title": title,
            "artist": artist,
            "youtube_url": youtube_url
        }
    )

    if game_code in active_timers:
        del active_timers[game_code]



@app.post("/create_game")
def create_game():
    host = User()
    game = Game(host)

    games_list[game.getCode()] = game

    return {
        "status": "Game successfully created",
        "game_code": game.getCode(),
        "host_id": game.getHostID()
    }


@app.post("/join_game")
def join_game(game_code: str, username: str):
    game_code = game_code.lower()

    if game_code not in games_list:
        raise HTTPException(404, "Game not found")

    player = Player(username)
    game = games_list[game_code]
    game.addPlayer(player)

    return {
        "status": "Player successfully added",
        "player_id": player.getID()
    }


@app.websocket("/ws/{game_code}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, game_code: str, user_id: str):
    """Main WebSocket entrypoint for a game."""
    await websocket.accept()

    game = games_list.get(game_code)
    if not game:
        await websocket.close()
        return

    # Register WS
    connections_list[(game_code, user_id)] = websocket

    # Notify others
    await broadcast(game_code, {"event": "user_joined", "user_id": user_id})

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            # ---------------------------------------------------------
            # Host requests next song
            # ---------------------------------------------------------
            if msg_type == "next":
                if game.isGameFinished():
                    await websocket.send_json({"action": "no_songs_left"})
                    continue

                if user_id != game.getHostID():
                    continue  # only host can request next

                # Countdown
                game.setCountdownStatus(True)

                for i in range(3, 0, -1):
                    await broadcast(game_code, {"action": "countdown", "status": i})
                    await asyncio.sleep(1)

                # New song
                game.nextSong()
                song = game.getCurrentSong()

                if song:
                    payload = song.getDict()
                    payload["action"] = "next_song"
                    await broadcast(game_code, payload)
                    
                    # Cancel any existing timer for this game
                    if game_code in active_timers:
                        active_timers[game_code].cancel()
                    
                    # Start a new answer timer for this round
                    task = asyncio.create_task(timer_task(game_code))
                    active_timers[game_code] = task

            # ---------------------------------------------------------
            # Host reveal song immediately
            # ---------------------------------------------------------
            elif msg_type == "reveal":
                # Only host can reveal
                if user_id != game.getHostID():
                    continue

                song = game.getCurrentSong()
                if not song:
                    continue

                # Cancel active timer for this round if present
                if game_code in active_timers:
                    try:
                        active_timers[game_code].cancel()
                    except Exception:
                        pass
                    del active_timers[game_code]

                # Broadcast the reveal (reuse time_limit_exceeded payload fields)
                await broadcast(
                    game_code,
                    {
                        "action": "time_limit_exceeded",
                        "title": song.title,
                        "artist": song.artist,
                        "youtube_url": song.youtube_url,
                    },
                )

            # ---------------------------------------------------------
            # Player answers
            # ---------------------------------------------------------
            elif msg_type == "answer":
                if not game.canReceiveAnswer():
                    elapsed = time.time() - game.getCurrentRoundTime()
                    if elapsed > game.ANSWER_TIME_LIMIT:
                        await websocket.send_json({"action": "answering_not_available"})
                    else:
                        await websocket.send_json({"action": "answering_not_available"})
                    continue

                player = game.getPlayerFromID(user_id)
                if not player:
                    continue

                song = game.getCurrentSong()
                if not song:
                    continue

                # Duplicate answer
                if player in song.getScoreboard():
                    await websocket.send_json({"action": "answer_already_sent"})
                    continue

                score = game.checkAnswer(data.get("answer"))
                await websocket.send_json({"action": "general_score", "score": score})

                if score > 0:
                    song.addToScoreboard(player)
                    elapsed = time.time() - game.getCurrentRoundTime()
                    player.alterScore(elapsed, score)
                    game.addCorrectPlayerThisRound(user_id)

                    # Send leaderboard with player IDs for correct highlighting
                    leaderboard_list = [
                        {"username": p.getUsername(), "score": p.score, "player_id": p.getID()}
                        for p in game.getLeaderboard()
                    ]
                    # Sort by score descending
                    leaderboard_list.sort(key=lambda x: x["score"], reverse=True)
                    
                    await broadcast(game_code, {
                        "leaderboard": leaderboard_list,
                        "correct_players": game.getCorrectPlayersThisRound()
                    })
                else:
                    await websocket.send_json({"action": "wrong_answer"})

            # ---------------------------------------------------------
            # Elapsed broadcasting (moved to periodic loop recommended)
            # ---------------------------------------------------------

    except WebSocketDisconnect:
        # Cleanup and notify
        if (game_code, user_id) in connections_list:
            del connections_list[(game_code, user_id)]
        await broadcast(game_code, {"event": "user_left", "user_id": user_id})
