from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.templating import Jinja2Templates
import asyncio
import time
from typing import Dict, Tuple
import secrets

from obj import AIResponse, Song

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from google import genai
from pydantic import BaseModel, TypeAdapter
from dotenv import load_dotenv

from ws_service import connect, disconnect, broadcast
from game_service import next_song, get_game, create_game, check_game_existence, close_game, can_receive_answer
from player_service import add_player, get_player, set_username, alter_score, remove_player, save_player, get_leaderboard
from song_service import load_songs

load_dotenv()
client = genai.Client().aio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # You can restrict this later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

templates = Jinja2Templates(directory="static")

songList: list[Song] = load_songs()

@app.get("/")
def server_index():
    return FileResponse(static_dir / "index.html")

@app.get("/editor")
def serve_editor(request: Request):
    return templates.TemplateResponse(
        "editor.html", {"request": request}
    )

@app.get("/party/{game_code}/{host_id}")
def serve_game(game_code: str, host_id: str):
    return FileResponse(static_dir / "party.html")

@app.get("/join")
def serve_join():
    return FileResponse(static_dir / "join.html")

@app.get("/join/{game_code}")
def serve_join_with_code(game_code: str):
    game_code = game_code.lower()

    if check_game_existence(game_code):
        serve_join()
    
    return FileResponse(static_dir / "join.html")

@app.get("/join/{game_code}/{player_id}")
def serve_join_with_id(game_code: str, player_id: str):
    return FileResponse(static_dir / "join.html")

active_timers: Dict[str, asyncio.Task] = {}  # Track active answer timers per game
last_msg: Dict[str, Dict] = {}
last_leaderboard: Dict = {}

async def timer_task(game_code: str):
    """Wait the ATL and broadcast time limit exceeded."""
    game = get_game(game_code)
    
    await asyncio.sleep(game.atl)

    song = songList[game.current_song_index]
    title = song.title if song else None
    artist = song.artist if song else None
    youtube_url = song.youtube_url if song else None

    last_msg[game_code] = {
            "action": "time_limit_exceeded",
            "title": title,
            "artist": artist,
            "youtube_url": youtube_url
        }
    await broadcast(game_code, last_msg[game_code])

    if game_code in active_timers:
        del active_timers[game_code]

def checkAnswer(song: Song, answer: str) -> int:
    answer = answer.lower()
    score = 0
    if song == None:
        return 0
    if any(s in answer for s in song.artist_variations):
        score = score + 1
    if any(s in answer for s in song.title_variations):
        score = score + 1
    return score


@app.post("/create_game")
def create_game_route():
    game_code = secrets.token_hex(3)
    host_id = secrets.token_hex(8)

    try:
        add_player(game_code, host_id, 'host')
        create_game(game_code, host_id)

        last_msg[game_code] = {"action": "no_message_sent_yet"}
        last_leaderboard[game_code] = {}

        return {
            "status": "Game successfully created",
            "game_code": game_code,
            "host_id": host_id
        }
    except Exception as e:
        print(e)


@app.post("/join_game")
def join_game(game_code: str):
    game_code = game_code.lower()

    if not check_game_existence(game_code):
        raise HTTPException(404, "Game not found")

    try:
        player_id = secrets.token_hex(8)
        add_player(game_code, player_id, 'player')

        return {
            "status": "Player successfully added",
            "player_id": player_id
        }
    except Exception as e: 
        print(e)
    

@app.post("/ping/{game_code}")
def ping_game(game_code: str):
    game_code = game_code.lower()

    if check_game_existence(game_code):
        return {
            "action": "party_found"
        }
    else:
        return {
            "action": "party_not_found"
        }

@app.post("/ping_player/{game_code}/{player_id}")
def ping_player(game_code: str, player_id: str):
    game_code = game_code.lower()
    game = get_game(game_code)

    if game:
        if get_player(game_code, player_id) == None:
            return {
                "action": "player_not_found"
            }
        else:
            return {
                "action": "player_found"
            }
        
@app.post("/ping_username/{game_code}/{player_id}")
def ping_username(game_code: str, player_id: str):
    game_code = game_code.lower()
    game = get_game(game_code)
    player = get_player(game_code, player_id)

    if game:
        if player == None:
            return {
                "action": "username_not_known"
            }
        elif player.username == None:
            return {
                "action": "username_not_known"
            }
        else:
            return {
                "action": "username_known",
                "username": player.username
            }

@app.websocket("/ws/{game_code}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, game_code: str, user_id: str):
    """Main WebSocket entrypoint for a game."""
    player = get_player(game_code, user_id)
    await connect(game_code, user_id, websocket)

    game = get_game(game_code)
    if not game:
        await websocket.close()
        return

    # Notify others
    await broadcast(game_code, {"event": "user_joined", "user_id": user_id})
    # Keep track of the last message sent
    global last_msg
    global last_leaderboard
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            # ---------------------------------------------------------
            # Host requests next song
            # ---------------------------------------------------------
            if msg_type == "next":
                if game.current_song_index == len(songList) - 1:
                    last_msg[game_code] = {"action": "no_songs_left"}
                    await broadcast(game_code, last_msg[game_code])
                    close_game(game_code)
                    continue

                if player == None or player.role != 'host' :
                    continue

                # Countdown
                game.countdown = True

                for i in range(3, 0, -1):
                    last_msg[game_code] = {"action": "countdown", "status": i}
                    await broadcast(game_code, last_msg[game_code])
                    await asyncio.sleep(1)

                # New song
                next_song(game_code)
                game = get_game(game_code)
                song = songList[game.current_song_index]

                if song:
                    payload = song.getDict()
                    payload["action"] = "next_song"
                    await websocket.send_json(payload)
                    last_msg[game_code] = {"action": "next_song_client"}
                    await broadcast(game_code, last_msg[game_code])
                    
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
                if player == None or player.role != 'host':
                    continue

                song = songList[game.current_song_index]
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
                last_msg[game_code] = {
                        "action": "time_limit_exceeded",
                        "title": song.title,
                        "artist": song.artist,
                        "youtube_url": song.youtube_url,
                    }
                await broadcast(game_code, last_msg[game_code])

            elif msg_type == "set_atl":
                if user_id != game.host_id:
                    continue  # only host can request next
                
                try:
                    atl = int(data.get('time'))
                    game.atl = atl
                    await websocket.send_json({"action": "time_changed"})
                except ValueError:
                    await websocket.send_json({"action": "time_not_number"})

            # ---------------------------------------------------------
            # Player joins and sets its username
            # ---------------------------------------------------------
            elif msg_type == "set_username":
                player = get_player(game_code, user_id)

                if player:
                    try:
                        username = data.get("username")
                        if username:
                            set_username(player, username)
                            save_player(game_code, player)
                            await websocket.send_json({"action": "username_ok"})
                            await broadcast(game_code, {
                                "action": "username_set",
                                "username": username,
                                "user_id": user_id
                            })
                        else:
                            await websocket.send_json({"action": "username_failed"})
                    except:
                        await websocket.send_json({"action": "username_empty_or_errored"})

            # ---------------------------------------------------------
            # Player answers
            # ---------------------------------------------------------
            elif msg_type == "answer":
                if not can_receive_answer(game_code):
                    elapsed = time.time() - game.time_start
                    if elapsed > game.atl:
                        await websocket.send_json({"action": "answering_not_available"})
                    else:
                        await websocket.send_json({"action": "answering_not_available"})
                    continue

                player = get_player(game_code, user_id)
                if not player:
                    continue

                game = get_game(game_code)
                song = songList[game.current_song_index]
                if not song:
                    continue

                # Duplicate answer
                if player in song.getScoreboard():
                    await websocket.send_json({"action": "answer_already_sent"})
                    continue

                score = checkAnswer(song, data.get("answer"))
                await websocket.send_json({"action": "general_score", "score": score})

                if score > 0:
                    song.addToScoreboard(player)
                    elapsed = time.time() - game.time_start
                    alter_score(player, score, elapsed, game.atl)
                    save_player(game_code, player)
                    game.correct_players.append(user_id)

                    # Send leaderboard with player IDs for correct highlighting
                    leaderboard_list = [
                        {"player_id": p[0], "score": p[1], "username": get_player(game_code, p[0]).username } # type: ignore
                        for p in get_leaderboard(game_code)
                    ]
                    # Sort by score descending
                    leaderboard_list.sort(key=lambda x: x["score"], reverse=True)
                    
                    last_msg[game_code] = {
                        "leaderboard": leaderboard_list,
                        "correct_players": game.correct_players
                    }
                    last_leaderboard[game_code] = last_msg[game_code]
                    await websocket.send_json({"action": "awaiting_next"})
                    await broadcast(game_code, last_msg[game_code])
                else:
                    await websocket.send_json({"action": "wrong_answer"})
                    
            elif msg_type == "remove_player":
                player_id = data.get("player_id")
                if player:
                    remove_player(game_code, player_id)
                    await broadcast(game_code, {"action": "player_removed", "player_id": player_id})
                else:
                    await websocket.send_json({"action": "player_not_found"})

            elif msg_type == "update":
                await websocket.send_json(last_leaderboard[game_code])
                await websocket.send_json(last_msg[game_code])


    except WebSocketDisconnect:
        # Cleanup and notify
        await disconnect(game_code, user_id)
        await broadcast(game_code, {"event": "user_left", "user_id": user_id})

@app.post("/get_variations")
async def get_variation(title: str, artist: str):
    response = await client.models.generate_content(
        model="gemini-2.5-flash-lite", 
        contents=f"Generate a list of orthographical variations for the artist ${artist} and the song ${title} for a French speaker. Include exact matches, common typos, phonetic misspellings, missing punctuation, and different separators (like hyphens or 'by'). CRITICAL: Convert every single output string to strictly lowercase. Don't include the artist name in the title variations and don't include the title in the artist name variations. Don't add any text that wasn't already present",
        config={"response_mime_type": "application/json", "response_schema": AIResponse}
    )
    
    return response.model_dump()['parsed']