# Emotion-Based Spotify Player (NEED SPOTIFY PREMIUM)

Plays songs a playlist of your choice that match how you're feeling.


1. **Mood detection from lyrics**. Lyrics are fetched
   and run through a model
   [(`j-hartmann/emotion-english-distilroberta-base`)](https://huggingface.co/j-hartmann/emotion-english-distilroberta-base), which sorts each
   song into `happy`, `sad`, `energetic`, or `calm`.
2. **Auto Recommendation** When your
   playlist runs out of songs for a mood, the app runs a set of track
   searches tied to that mood (e.g. `genre:metal`, `genre:techno`,
   "workout" for `energetic`; see `MOOD_SEARCH_QUERIES` in
   `spotify_client.py`).

**Trade-offs**: instrumental tracks can't
find get lumped into `calm` by default (see `lyrics_emotion.py`).
If you want better lyrics coverage, swap
`fetch_lyrics` for the `lyricsgenius` package with a Genius API key.

## Setup

1. Create a Spotify app at https://developer.potify.com/dashboard.
   Add `http://127.0.0.1:8888/callback` as a Redirect URI in the
   app settings.
2. Copy `.env.example` to `.env` and fill in your Client ID/Secret.
3. `pip install -r requirements.txt`
4. Before running, open Spotify on your phone, desktop, or web player
5. Find your playlist's ID, the ID is the string after `/playlist/` in the URL, or
   you can paste the link of your playlist.

## Run

### Window mode
```bash
python main.py
```

Enter the playlist ID or link, then enter your mood: `happy`, `sad`, `energetic`, or `calm`.
Type `stop` to stop the song, `forward` to play the next song, `backward` to play the previous song, and `exit` to end the program.

You can type a mood while a song is playing to correct that
song's mood; the correction will be saved when the song finishs and will belong to that mood.

### Command-line mode

```bash
python main.py --playlist YOUR_PLAYLIST_ID --mood sad
```
