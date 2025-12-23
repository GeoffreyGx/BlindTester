import json
from obj import Song

SONGS_PATH = "./songs.json"

def load_songs() -> list[Song]:
    with open(SONGS_PATH, "r") as f:
        data = json.load(f)
    return [
        Song(
            s["title"],
            s["artist"],
            s["youtube_url"],
            s["timestamp"],
            s["title_writings"],
            s["artist_writings"]
        )
        for s in data["songs"]
    ]
