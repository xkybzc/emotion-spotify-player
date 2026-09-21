import json
import os
import random
import time

import config
import spotify_client as sc
import lyrics_emotion as le

MOODS = ["happy", "sad", "energetic", "calm"]


def load_cache():
    if os.path.exists(config.CACHE_FILE):
        with open(config.CACHE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(config.CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def classify_track(sp, track, cache):
    """Mood for one track, using (and filling) the local cache."""
    mood = cache.get(track["id"])
    if mood is None:
        genres = sc.get_artist_genres(sp, track.get("artist_id"))
        if not genres and track.get("genre_hint"):
            genres = [track["genre_hint"]]
        mood = le.classify_mood(track["artist"], track["name"], genres=genres)
        cache[track["id"]] = mood
    return mood


def classify_library(sp, playlist_id):
    """
    Classify every track in the playlist into a mood bucket.
    Results are cached locally by track id so re-runs don't
    re-hit the lyrics API / re-run the model on the same song.
    """
    cache = load_cache()
    tracks = sc.get_playlist_tracks(sp, playlist_id)
    buckets = {m: [] for m in MOODS}

    for t in tracks:
        buckets[classify_track(sp, t, cache)].append(t)

    save_cache(cache)
    return buckets, {t["id"] for t in tracks}


def build_queue_for_mood(sp, mood, buckets, all_ids, target_count=40):
    queue = buckets.get(mood, [])[:]
    random.shuffle(queue)

    if len(queue) < target_count:
        print(f"Only {len(queue)} '{mood}' tracks in your playlist; searching Spotify for more...")
        cache = load_cache()
        exclude = all_ids | {t["id"] for t in queue}
        external = sc.find_external_tracks_for_mood(sp, mood, exclude)
        print(f"Found {len(external)} candidates, checking their mood (cached ones are instant)...")

        checked = 0
        for t in external:
            if len(queue) >= target_count:
                break
            # Re-check mood ourselves; a genre search is only a rough
            # signal and can return mislabeled tracks.
            if classify_track(sp, t, cache) == mood:
                queue.append(t)
            checked += 1
            if checked % 25 == 0:
                print(f"  checked {checked}/{len(external)}, queue now {len(queue)}")
                save_cache(cache)

        save_cache(cache)
        added = len(queue) - (len(buckets.get(mood, [])))
        print(f"Added {added} '{mood}' tracks from Spotify search.")

    return queue


def monitor_now_playing(sp, first_track_id, poll_seconds=3):
    """Prints the track name/artist every time the playing song changes.
    Runs until you press Ctrl+C; playback itself keeps going either way."""
    last_id = first_track_id
    print("Watching for song changes (Ctrl+C to stop watching -- playback keeps going).")
    try:
        while True:
            time.sleep(poll_seconds)
            current = sc.get_currently_playing(sp)
            if current and current["id"] != last_id:
                print(f"Now playing: {current['name']} by {current['artist']}")
                last_id = current["id"]
    except KeyboardInterrupt:
        print("\nStopped watching (music keeps playing on your device).")


def run(playlist_id, mood):
    sp = sc.get_spotify_client()

    print("Reading and classifying your playlist (first run can take a while)...")
    buckets, all_ids = classify_library(sp, playlist_id)
    queue = build_queue_for_mood(sp, mood, buckets, all_ids)

    if not queue:
        print(f"Couldn't find any '{mood}' tracks in the playlist or nearby playlists.")
        return

    device_id = sc.get_active_device_id(sp)
    if not device_id:
        print("No active Spotify device found. Open Spotify on a device (phone, desktop, web) and try again.")
        return

    uris = [t["uri"] for t in queue]
    sc.play_uris(sp, uris, device_id=device_id)
    print(f"Playing {len(uris)} '{mood}' tracks, starting with '{queue[0]['name']}' by {queue[0]['artist']}.")
    monitor_now_playing(sp, first_track_id=queue[0]["id"])