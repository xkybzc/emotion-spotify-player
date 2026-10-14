import spotipy
from spotipy.oauth2 import SpotifyOAuth

import config


def get_spotify_client():
    # Spotipy manages OAuth login and reuses the saved token cache.
    auth_manager = SpotifyOAuth(
        client_id=config.SPOTIFY_CLIENT_ID,
        client_secret=config.SPOTIFY_CLIENT_SECRET,
        redirect_uri=config.SPOTIFY_REDIRECT_URI,
        scope=config.SCOPES,
        cache_path=".spotify_token_cache",
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def _track_to_dict(t):
    # Keep only the track fields used by classification and playback.
    artist = t["artists"][0] if t["artists"] else {}
    return {
        "id": t["id"],
        "uri": t["uri"],
        "name": t["name"],
        "artist": artist.get("name", ""),
        "artist_id": artist.get("id"),
    }


_genre_cache = {}


def get_artist_genres(sp, artist_id):
    """Cached lookup so we don't re-fetch the same artist's genres repeatedly."""
    # Cache genre lookups because the same artist can appear on many tracks.
    if not artist_id:
        return []
    if artist_id not in _genre_cache:
        try:
            # Spotify currently returns null genres for most artists to
            # development-mode apps, so normalise None -> [].
            _genre_cache[artist_id] = sp.artist(artist_id).get("genres") or []
        except Exception:
            _genre_cache[artist_id] = []
    return _genre_cache[artist_id]


def get_playlist_tracks(sp, playlist_id):
    """All tracks in a playlist, as [{id, uri, name, artist}, ...]."""
    # Follow Spotify pagination until every playlist track has been collected.
    tracks = []
    results = sp.playlist_items(playlist_id)
    while results:
        for entry in results["items"]:
            t = entry.get("track") or entry.get("item")
            if t and t.get("id"):
                tracks.append(_track_to_dict(t))
        results = sp.next(results) if results.get("next") else None
    return tracks


# Search queries used to find candidate tracks for each mood. Since
# Feb 2025, apps in Spotify "development mode" get 403 Forbidden when
# reading almost any playlist they don't own, so we can't harvest
# tracks from public "sad songs" playlists any more. Track search
# (with the `genre:` filter) still works, so we use that instead.
# Candidates are still re-classified by lyrics before being played.
MOOD_SEARCH_QUERIES = {
    "energetic": [
        "genre:metal", "genre:rock", "genre:punk", "genre:hardcore",
        "genre:edm", "genre:techno", "genre:trap", "genre:drum-and-bass",
        "workout", "hype",
    ],
    "happy": [
        "genre:pop", "genre:dance", "genre:disco", "genre:funk",
        "feel good", "upbeat", "summer",
    ],
    "sad": [
        "genre:singer-songwriter", "genre:acoustic", "genre:indie",
        "genre:soul", "heartbreak", "breakup", "lonely", "goodbye",
    ],
    "calm": [
        "genre:acoustic", "genre:ambient", "genre:jazz", "genre:classical",
        "genre:folk", "genre:piano", "relax", "chill",
    ],
}


# Development-mode apps are currently capped at 10 results per search
# call (larger limits return 400 "Invalid limit"), so we page instead.
SEARCH_PAGE_SIZE = 10


def find_external_tracks_for_mood(sp, mood_keyword, exclude_ids, pages_per_query=3, max_candidates=300):
    """
    Recommendations-endpoint replacement: run several track searches
    tied to the mood (genre filters + mood words) and return the
    de-duplicated results. Caller is expected to re-check each
    candidate's mood, since a genre alone is a rough signal.
    """
    import random

    # Search several randomized queries, then remove duplicate or excluded tracks.
    candidates = []
    seen = set(exclude_ids)
    queries = MOOD_SEARCH_QUERIES.get(mood_keyword, [f"{mood_keyword} songs"])[:]
    random.shuffle(queries)

    for q in queries:
        if len(candidates) >= max_candidates:
            break
        # Random starting page so repeat runs don't always return the
        # same top hits for a query.
        start = random.choice([0, 10, 20, 30, 40, 50])
        for page in range(pages_per_query):
            offset = start + page * SEARCH_PAGE_SIZE
            try:
                search = sp.search(q=q, type="track", limit=SEARCH_PAGE_SIZE, offset=offset)
            except Exception:
                break
            items = search.get("tracks", {}).get("items", [])
            if not items:
                break
            for t in items:
                if not t or not t.get("id") or t["id"] in seen:
                    continue
                seen.add(t["id"])
                d = _track_to_dict(t)
                # Spotify no longer returns artist genres to dev-mode
                # apps, so remember which genre search found this track;
                # the classifier uses it as a fallback energy signal.
                if q.startswith("genre:"):
                    d["genre_hint"] = q[len("genre:"):]
                candidates.append(d)

    random.shuffle(candidates)
    return candidates


def get_active_device_id(sp):
    # Prefer the active device; otherwise use the first available device.
    devices = sp.devices().get("devices", [])
    for d in devices:
        if d.get("is_active"):
            return d["id"]
    return devices[0]["id"] if devices else None


def play_uris(sp, uris, device_id=None):
    if not uris:
        raise ValueError("No tracks to play.")
    # start_playback accepts an ad-hoc list of URIs as the queue.
    sp.start_playback(device_id=device_id, uris=uris[:100])


def add_to_queue(sp, uri, device_id=None):
    sp.add_to_queue(uri=uri, device_id=device_id)


def stop_playback(sp, device_id=None):
    sp.pause_playback(device_id=device_id)


def skip_forward(sp, device_id=None):
    sp.next_track(device_id=device_id)


def skip_backward(sp, device_id=None):
    sp.previous_track(device_id=device_id)


def get_currently_playing(sp):
    """Returns {'id', 'name', 'artist'} for the currently playing track, or None."""
    # Convert Spotify's nested playback response into the app's small track shape.
    current = sp.current_playback()
    if not current or not current.get("item"):
        return None
    item = current["item"]
    return {
        "id": item["id"],
        "name": item["name"],
        "artist": item["artists"][0]["name"] if item["artists"] else "",
    }