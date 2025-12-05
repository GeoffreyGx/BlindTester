import secrets
import time
import json
import math
from typing import List, Optional


class User:
    def __init__(self) -> None:
        self.id = secrets.token_hex(8)

    def getID(self) -> str:
        return self.id


class Player(User):
    def __init__(self) -> None:
        super().__init__()
        self.username = "Connecting..."
        self.score = 0.0

    def setUsername(self, username: str) -> None:
        self.username = username

    def getUsername(self) -> str | None:
        return self.username if self.username != "Connecting..." else None

    def alterScore(self, elapsed: float, score: int) -> None:
        """Update score with exponential decay."""
        bonus = ((1 - math.e ** (elapsed / 7)) / 0.5) + 50
        self.score += bonus * score

    def __str__(self) -> str:
        return f"{self.username} | {self.score}"


class Song:
    def __init__(self, title: str, artist: str, youtube_url: str) -> None:
        self.title = title
        self.artist = artist
        self.youtube_url = youtube_url
        self.scores: List[Player] = []

    def getDict(self) -> dict:
        return {
            "title": self.title,
            "artist": self.artist,
            "youtube_url": self.youtube_url
        }

    def addToScoreboard(self, player: Player) -> None:
        self.scores.append(player)

    def getScoreboard(self) -> List[Player]:
        return self.scores


class Game:
    ANSWER_TIME_LIMIT = 15  # seconds

    def __init__(self, host: User, songs_path="./songs.json") -> None:
        self.host = host
        self.players: List[Player] = []
        self.songs: List[Song] = self._loadSongs(songs_path)
        self.leaderboard: List[Player] = []
        self.correct_players_this_round: List[str] = []  # Track player IDs who answered correctly

        self.party_code = secrets.token_hex(3)

        self.current_song_index: Optional[int] = -1
        self.time_start = 0.0
        self.countdown = False

    def _loadSongs(self, songs_path) -> List[Song]:
        with open(songs_path, "r") as f:
            data = json.load(f)
        return [Song(s["title"], s["artist"], s["youtube_url"]) for s in data["songs"]]

    def addPlayer(self, player: Player) -> None:
        self.players.append(player)
        self.leaderboard.append(player)

    def getCode(self) -> str:
        return self.party_code

    def getHostID(self) -> str:
        return self.host.getID()

    def nextSong(self) -> None:
        if self.current_song_index is None:
            return

        if self.current_song_index >= len(self.songs) - 1:
            self.current_song_index = None
            return

        self.current_song_index += 1
        self.time_start = time.time()
        self.countdown = False
        self.correct_players_this_round = []  # Reset for new round

    def getCurrentSong(self) -> Optional[Song]:
        if self.current_song_index is None or self.current_song_index == -1:
            return None
        return self.songs[self.current_song_index]

    def canReceiveAnswer(self) -> bool:
        if self.current_song_index in (None, -1) or self.countdown is True:
            return False
        
        elapsed = time.time() - self.time_start
        return elapsed <= self.ANSWER_TIME_LIMIT

    def isGameFinished(self) -> bool:
        return (
            self.current_song_index is None
            or self.current_song_index == len(self.songs) - 1
        )

    def checkAnswer(self, answer: str) -> int:
        answer = answer.lower()
        score = 0
        current_song = self.getCurrentSong()
        if current_song == None:
            return 0
        if current_song.artist.lower() in answer:
            score = score + 1
        if current_song.title.lower() in answer:
            score = score + 1
        return score

    def getPlayerFromID(self, player_id: str) -> Optional[Player]:
        return next((p for p in self.players if p.getID() == player_id), None)

    def getCurrentRoundTime(self) -> float:
        return self.time_start

    def setCountdownStatus(self, status: bool) -> None:
        self.countdown = status

    def addToLeaderboard(self, player: Player) -> None:
        self.leaderboard.append(player)

    def getLeaderboard(self) -> List[Player]:
        return self.leaderboard

    def addCorrectPlayerThisRound(self, player_id: str) -> None:
        """Track a player who answered correctly this round."""
        if player_id not in self.correct_players_this_round:
            self.correct_players_this_round.append(player_id)

    def getCorrectPlayersThisRound(self) -> List[str]:
        """Get list of player IDs who answered correctly this round."""
        return self.correct_players_this_round
