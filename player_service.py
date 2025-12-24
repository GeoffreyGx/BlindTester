import math
from typing import cast, List, Tuple, Literal
from redis_client import redis_client
from redis_models import RedisPlayer

def players_key(code: str) -> str:
    return f"game:{code}:players"

def leaderboard_key(code: str) -> str:
    return f"game:{code}:leaderboard"

def add_player(code: str, player_id: str, role: Literal["host", "player"]):
    player = RedisPlayer(
        id=player_id, 
        username=None, 
        score=0, 
        role=role,
        phase="WAITING"
    )
    redis_client.hset(players_key(code), player_id, player.model_dump_json())
    if role == "player":
        redis_client.zadd(leaderboard_key(code), {player_id : 0})

def player_exists(code: str, player_id: str) -> bool:
    return redis_client.hexists(players_key(code), player_id) == 1

def get_player(code: str, player_id: str) -> RedisPlayer | None:
    raw = redis_client.hget(players_key(code), player_id)
    return RedisPlayer.model_validate_json(str(raw)) if raw else None

def save_player(code: str, player: RedisPlayer):
    redis_client.hset(players_key(code), player.id, player.model_dump_json())
    if player.role == 'player':
        redis_client.zrem(leaderboard_key(code), player.id)
        redis_client.zadd(leaderboard_key(code), {player.id : player.score})

def remove_player(code: str, player_id: str):
    redis_client.hdel(players_key(code), player_id)

def set_username(game_code: str, player: RedisPlayer, username: str):
    player.username = username
    save_player(game_code, player)

def set_phase(game_code: str, player: RedisPlayer, phase: Literal["ANSWERING", "LEADERBOARD", "LOCKED", "KICKED"]):
    player.phase = phase
    save_player(game_code, player)

def alter_score(player: RedisPlayer, score: int, elapsed: float, atl: int):
    bonus = (1 - math.e ** (elapsed / (0.3 * atl))) + 50
    player.score += bonus * score

def get_leaderboard(code: str) -> List[Tuple[str, float]]:
    return cast(List[Tuple[str, float]], redis_client.zrevrange(leaderboard_key(code), 0, -1, withscores=True))