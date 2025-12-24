import time
import json
from typing import Literal
from redis_client import redis_client
from redis_models import RedisGame

GAME_TTL = 3600

def game_key(code: str) -> str:
    return f"game:{code}"

def logs_key(code: str) -> str:
    return f"game:{code}:logs"

def check_game_existence(code: str) -> bool:
    return redis_client.exists(game_key(code)) == 1

def get_game(code: str) -> RedisGame:
    raw = redis_client.get(game_key(code))
    if not raw:
        raise KeyError('Game not found')
    return RedisGame.model_validate_json(str(raw))

def save_game(code: str, game: RedisGame):
    redis_client.set(
        game_key(code), 
        game.model_dump_json(),
        ex=GAME_TTL
    )

def create_game(code: str, host_id: str):
    game = RedisGame(
        host_id=host_id,
        current_song_index=-1,
        time_start=0,
        countdown=False,
        atl=30,
        correct_players=[]
    )
    save_game(code, game)

def close_game(code: str):
    redis_client.delete(game_key(code))

def next_song(code: str):
    game = get_game(code)
    game.current_song_index += 1
    game.time_start = time.time()
    game.countdown = False
    game.correct_players = []
    save_game(code, game)

def can_receive_answer(code: str) -> bool:
    game = get_game(code)
    if game.current_song_index in (None, -1) or game.countdown is True:
            return False        
    elapsed = time.time() - game.time_start
    return elapsed <= game.atl

def get_latest_log(code: str):
    entries = redis_client.xrevrange(logs_key(code), count=1)
    if not entries:
        return {'action': 'no_message_sent_yet'}
    
    _id, data = entries[0] # type: ignore 
    return json.loads(data["payload"])
    

def set_latest_log(code: str, msg: dict):
    redis_client.xadd(logs_key(code), {'payload': json.dumps(msg)})