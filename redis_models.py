from pydantic import BaseModel
from typing import List, Literal

class RedisPlayer(BaseModel):
    id: str
    username: str | None
    score: float
    role: Literal["host", "player"]

class RedisGame(BaseModel):
    host_id: str
    current_song_index: int
    time_start: float
    countdown: bool
    atl: int
    correct_players: List[str]