import os
from dotenv import load_dotenv # read key values from .env file

# Load local environment variables before reading Spotify credentials.
load_dotenv()

# These values authenticate the app and configure Spotify's callback URL.
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

# Playback control + reading your playlists is all we need.
# (We deliberately don't request anything tied to the deprecated
# audio-features / recommendations endpoints.)
SCOPES = (
    "playlist-read-private " # read private playlists
    "playlist-read-collaborative " # read playlists shared with you
    "user-read-playback-state " # see what device is playing
    "user-modify-playback-state " # control playback (start/stop/skip)
    "user-read-currently-playing" # see what track is playing
)

CACHE_FILE = "emotion_cache.json" # save track id and mood
