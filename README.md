# Emotion-Based Spotify Player

Plays songs from one of your playlists that match how you're feeling, and
automatically pulls in more songs from public Spotify playlists once it
runs out of matches in your own library.


1. **Mood detection from lyrics**, not audio features. Lyrics are fetched
   (free, no auth) and run through a text emotion-classification model
   (`j-hartmann/emotion-english-distilroberta-base`), which sorts each
   song into `happy`, `sad`, `energetic`, or `calm`.
2. **"More songs like this" via Search, not Recommendations.** When your
   playlist runs out of songs for a mood, the app runs a set of track
   searches tied to that mood (e.g. `genre:metal`, `genre:techno`,
   "workout" for `energetic`; see `MOOD_SEARCH_QUERIES` in
   `spotify_client.py`) and re-classifies the results the same way,
   rather than calling the dead `recommendations` endpoint.

   Note: an earlier version harvested tracks from public playlists
   titled "sad songs" etc. Since Feb 2025, apps in Spotify's
   development mode get `403 Forbidden` when reading almost any
   playlist they don't own, and search is capped at 10 results per
   call, so the app now pages through track searches instead.
   Spotify also no longer returns artist genres to dev-mode apps, so
   the genre from the search query is used as the energy hint for
   tracks found this way.

Trade-offs to know about: instrumental tracks or songs lyrics.ovh can't
find get lumped into `calm` by default (see `lyrics_emotion.py`), and the
4-mood split is a simplification — good enough for "play sad songs" but
not a fine-grained mood engine. If you want better lyrics coverage, swap
`fetch_lyrics` for the `lyricsgenius` package with a Genius API key.

## Setup

1. Create a Spotify app at https://developer.potify.com/dashboard
   (free). Add `http://127.0.0.1:8888/callback` as a Redirect URI in the
   app settings.
2. Copy `.env.example` to `.env` and fill in your Client ID/Secret.
3. `pip install -r requirements.txt`
4. Requires **Spotify Premium** (playback control needs it) and an
   active device — open Spotify on your phone, desktop, or web player
   before running.
5. Find your playlist's ID: right-click it in Spotify → Share → Copy
   link. The ID is the string after `/playlist/` in the URL.

## Run

### Window mode

Run the project without arguments:

```bash
python main.py
```

This opens a terminal-style window. It asks for a playlist ID or link, then
asks you to type `happy`, `sad`, `energetic`, or `calm`. Playback starts after
you enter the mood. While playing, type `stop`, `forward`, `backward`, or
`exit`. You can also type a mood while a song is playing to correct that
song's mood; the correction is saved when the song changes and is remembered
on future runs.

All matching songs already in the playlist are queued before any songs found
by Spotify search. The application searches for and appends outside songs while
the playlist songs are playing. It prints the name and artist whenever the
current song changes.

Spotify must be open on an active device, and playback control requires Spotify
Premium. Public playlist links can be entered, but Spotify development-mode
access may reject playlists that the application cannot read.

### Command-line mode

```bash
python main.py --playlist YOUR_PLAYLIST_ID --mood sad
```
