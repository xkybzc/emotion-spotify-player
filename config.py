import os
from dotenv import load_dotenv

load_dotenv()

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

# Playback control + reading your playlists is all we need.
# (We deliberately don't request anything tied to the deprecated
# audio-features / recommendations endpoints.)
SCOPES = (
    "playlist-read-private "
    "playlist-read-collaborative "
    "user-read-playback-state "
    "user-modify-playback-state "
    "user-read-currently-playing"
)

CACHE_FILE = "emotion_cache.json"
