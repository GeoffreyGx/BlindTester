from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from pathlib import Path

from ws_service import connect, disconnect, broadcast
from game_service import next_song, get_game, create_game, check_game_existence, close_game, can_receive_answer, get_latest_log, set_latest_log
from player_service import add_player, get_player, set_username, alter_score, remove_player, save_player, get_leaderboard, player_exists, set_phase
from song_service import load_songs

from obj import AIResponse, Song
from dotenv import load_dotenv
from google import genai

from typing import Dict
import asyncio
import time
import secrets

load_dotenv()
songList: list[Song] = load_songs()

app = FastAPI()
ai = genai.Client().aio

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # You can restrict this later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="static")
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# USER-ACCESSIBLE ROUTES

@app.get("/")
def serve_index():
    return FileResponse(static_dir / "index.html")

@app.get("/beta/join")
def serve_beta_join(request: Request):
    return templates.TemplateResponse(
        "beta_join.html", {
            'request': request,
            'prefill_code': ''
        }
    )

@app.get("/beta/join/{game_code}")
def serve_beta_join_code(request: Request, game_code: str):
    game_code = game_code.lower()

    if not check_game_existence(game_code):
        return RedirectResponse("/beta/join?error=game", status_code=303)
    
    return templates.TemplateResponse(
        "beta_join.html", {
            'request': request,
            'prefill_code': game_code
        }
    )

@app.post("/beta/join")
def serve_post_beta_join(game_code: str = Form(...), username: str = Form(...)):
    game_code = game_code.lower().strip()
    username = username.strip()

    if not check_game_existence(game_code):
        return RedirectResponse("/beta/join?error=game", status_code=303)
    
    if not username:
        return RedirectResponse(f"/beta/join/{game_code}?error=username", status_code=303)
    
    player_id = secrets.token_hex(8)
    add_player(game_code, player_id, 'player')

    return RedirectResponse(f"/beta/play/{game_code}?uid={player_id}", status_code=303)

@app.get("/beta/play/{game_code}")
def serve_play(request: Request, game_code: str, uid: str):
    if not player_exists(game_code, uid):
        return RedirectResponse("/join", status_code=303)
    
    ws_proto = "wss" if request.url.scheme == "https" else "ws"
    ws_url = f"{ws_proto}://{request.url.netloc}/ws/{game_code}/{uid}"

    return templates.TemplateResponse(
        "beta_play.html", {
            'request': request,
            'game_code': game_code,
            'user_id': uid,
            'ws_url': ws_url
        }
    )


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

@app.get("/party/{game_code}/{host_id}")
def serve_game(game_code: str, host_id: str):
    return FileResponse(static_dir / "party.html")

@app.get("/editor")
def serve_editor(request: Request):
    return templates.TemplateResponse(
        "editor.html", {"request": request}
    )

# API ROUTES

@app.post("/create_game")
def create_game_route():
    game_code = secrets.token_hex(3)
    host_id = secrets.token_hex(8)

    try:
        add_player(game_code, host_id, 'host')
        create_game(game_code, host_id)

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
    if not player:
        await websocket.close()
        return
    
    await connect(game_code, user_id, websocket)

    game = get_game(game_code)
    if not game:
        await websocket.close()
        return

    await broadcast(game_code, {"event": "user_joined", "user_id": user_id})

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "hello":
                snapshot = {
                    "type": "snapshot",
                    "player": {
                        "id": player.id,
                        "username": player.username
                    },
                    "phase": player.phase,
                    "can_answer": can_receive_answer(game_code),
                    "leaderboard": get_leaderboard(game_code)
                }
                
                await websocket.send(snapshot)

            # ---------------------------------------------------------
            # Host requests next song
            # ---------------------------------------------------------
            if msg_type == "next":
                if game.current_song_index == len(songList) - 1:
                    set_latest_log(game_code, {"action": "no_songs_left"})
                    latest_log = get_latest_log(game_code)
                    await broadcast(game_code, latest_log)
                    close_game(game_code)
                    continue

                if player == None or player.role != 'host' :
                    continue

                # Countdown
                game.countdown = True

                for i in range(3, 0, -1):
                    set_latest_log(game_code, {"action": "countdown", "status": i})
                    latest_log = get_latest_log(game_code)
                    await broadcast(game_code, latest_log)
                    await asyncio.sleep(1)

                # New song
                next_song(game_code)
                game = get_game(game_code)
                song = songList[game.current_song_index]

                if song:
                    payload = song.getDict()
                    payload["action"] = "next_song"
                    await websocket.send_json(payload)
                    set_latest_log(game_code, {"action": "next_song_client"})
                    latest_log = get_latest_log(game_code)
                    await broadcast(game_code, latest_log)
                    
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
                set_latest_log(game_code, {
                        "action": "time_limit_exceeded",
                        "title": song.title,
                        "artist": song.artist,
                        "youtube_url": song.youtube_url,
                    })
                latest_log = get_latest_log(game_code)
                await broadcast(game_code, latest_log)

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
                if player:
                    try:
                        username = data.get("username")
                        if username:
                            set_username(game_code, player, username)
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
                    
                    set_latest_log(game_code, {
                        "leaderboard": leaderboard_list,
                        "correct_players": game.correct_players
                        })
                    await websocket.send_json({"action": "awaiting_next"})
                    latest_log = get_latest_log(game_code)
                    await broadcast(game_code, latest_log)
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
                # Send leaderboard with player IDs for correct highlighting
                leaderboard_list = [
                    {"player_id": p[0], "score": p[1], "username": get_player(game_code, p[0]).username } # type: ignore
                    for p in get_leaderboard(game_code)
                ]
                # Sort by score descending
                leaderboard_list.sort(key=lambda x: x["score"], reverse=True)
                
                latest_leaderboard = {
                    "leaderboard": leaderboard_list,
                    "correct_players": game.correct_players
                    }
                await websocket.send_json(latest_leaderboard)
                
                latest_log = get_latest_log(game_code)
                await websocket.send_json(latest_log)


    except WebSocketDisconnect:
        # Cleanup and notify
        await disconnect(game_code, user_id)
        await broadcast(game_code, {"event": "user_left", "user_id": user_id})

@app.post("/get_variations")
async def get_variation(title: str, artist: str):
    response = await ai.models.generate_content(
        model="gemini-2.5-flash-lite", 
        contents=f"Generate a list of orthographical variations for the artist ${artist} and the song ${title} for a French speaker. Include exact matches, common typos, phonetic misspellings, missing punctuation, and different separators (like hyphens or 'by'). CRITICAL: Convert every single output string to strictly lowercase. Don't include the artist name in the title variations and don't include the title in the artist name variations. Don't add any text that wasn't already present",
        config={"response_mime_type": "application/json", "response_schema": AIResponse}
    )
    return response.model_dump()['parsed']

active_timers: Dict[str, asyncio.Task] = {}
    
async def timer_task(game_code: str):
    game = get_game(game_code)
    
    await asyncio.sleep(game.atl)

    song = songList[game.current_song_index]
    title = song.title if song else None
    artist = song.artist if song else None
    youtube_url = song.youtube_url if song else None

    set_latest_log(game_code, {
            "action": "time_limit_exceeded",
            "title": title,
            "artist": artist,
            "youtube_url": youtube_url
        })
    
    latest_log = get_latest_log(game_code)
    await broadcast(game_code, latest_log)

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