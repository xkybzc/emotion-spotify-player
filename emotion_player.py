import json
import os
import random
import threading
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
    cache = load_cache()
    tracks = sc.get_playlist_tracks(sp, playlist_id)
    buckets = {m: [] for m in MOODS}
    for track in tracks:
        buckets[classify_track(sp, track, cache)].append(track)
    save_cache(cache)
    return buckets, {track["id"] for track in tracks}


class PlaybackSession:
    def __init__(self, playlist_id, mood):
        self.playlist_id = playlist_id
        self.mood = mood
        self.sp = None
        self.device_id = None
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.current_track_id = None
        self.pending_mood = None
        self.cache = {}

    def run(self):
        self.sp = sc.get_spotify_client()
        print("Reading and classifying your playlist...")
        buckets, all_ids = classify_library(self.sp, self.playlist_id)
        self.cache = load_cache()
        local_tracks = buckets.get(self.mood, [])[:]
        random.shuffle(local_tracks)

        if not local_tracks:
            print(f"No '{self.mood}' track is ready yet; searching Spotify before starting...")
            external = sc.find_external_tracks_for_mood(
                self.sp, self.mood, all_ids, pages_per_query=1
            )
            local_tracks = self._matching_tracks(external, 1)
        if not local_tracks:
            print(f"Couldn't find any '{self.mood}' tracks.")
            return

        self.device_id = sc.get_active_device_id(self.sp)
        if not self.device_id:
            print("No active Spotify device found. Open Spotify and try again.")
            return

        first = local_tracks.pop(0)
        self.current_track_id = first["id"]
        sc.play_uris(self.sp, [first["uri"]], device_id=self.device_id)
        print(f"Now playing: {first['name']} by {first['artist']}")
        print("Commands: stop, forward, backward, exit, or type a mood to correct the current song.")

        threading.Thread(
            target=self._fill_queue,
            args=(local_tracks, all_ids | {first["id"]}),
            daemon=True,
        ).start()
        self._monitor()

    def _matching_tracks(self, candidates, target_count):
        matches = []
        for track in candidates:
            if len(matches) >= target_count:
                break
            if classify_track(self.sp, track, self.cache) == self.mood:
                matches.append(track)
        save_cache(self.cache)
        return matches

    def _fill_queue(self, local_tracks, exclude_ids):
        queued_ids = set(exclude_ids)
        playlist_count = 0
        for track in local_tracks:
            if self.stop_event.is_set():
                return
            if self._queue_track(track, queued_ids):
                playlist_count += 1

        print(
            f"Queued {playlist_count} more '{self.mood}' songs from your playlist first."
        )
        print("Searching for more matching songs while those playlist songs play...")
        external = sc.find_external_tracks_for_mood(
            self.sp, self.mood, queued_ids, pages_per_query=3
        )
        for track in external:
            if self.stop_event.is_set():
                return
            if classify_track(self.sp, track, self.cache) == self.mood:
                self._queue_track(track, queued_ids)
        save_cache(self.cache)

    def _queue_track(self, track, queued_ids):
        if track["id"] in queued_ids:
            return False
        try:
            sc.add_to_queue(self.sp, track["uri"], device_id=self.device_id)
            queued_ids.add(track["id"])
            print(f"Added to queue: {track['name']} by {track['artist']}")
            return True
        except Exception as error:
            print(f"Could not add '{track['name']}' to the queue: {error}")
            return False

    def _monitor(self):
        last_id = self.current_track_id
        while not self.stop_event.wait(3):
            current = sc.get_currently_playing(self.sp)
            if not current or current["id"] == last_id:
                continue
            self._apply_pending_mood()
            last_id = current["id"]
            self.current_track_id = last_id
            print(f"Now playing: {current['name']} by {current['artist']}")
        self._apply_pending_mood()

    def correct_current_mood(self, mood):
        if mood not in MOODS:
            return
        with self.lock:
            if not self.current_track_id:
                print("No current song is available for correction yet.")
                return
            self.pending_mood = mood
        print(f"Marked the current song as '{mood}'. It will be saved when the song changes.")

    def _apply_pending_mood(self):
        with self.lock:
            if not self.pending_mood or not self.current_track_id:
                return
            self.cache[self.current_track_id] = self.pending_mood
            save_cache(self.cache)
            print(f"Saved mood correction: {self.current_track_id} -> {self.pending_mood}")
            self.pending_mood = None

    def stop(self):
        if self.sp and self.device_id:
            sc.stop_playback(self.sp, device_id=self.device_id)
            print("Playback paused.")

    def forward(self):
        if self.sp and self.device_id:
            sc.skip_forward(self.sp, device_id=self.device_id)
            print("Moved forward.")

    def backward(self):
        if self.sp and self.device_id:
            sc.skip_backward(self.sp, device_id=self.device_id)
            print("Moved backward.")

    def exit(self):
        self._apply_pending_mood()
        self.stop_event.set()
        if self.sp and self.device_id:
            sc.stop_playback(self.sp, device_id=self.device_id)


def run(playlist_id, mood):
    """Compatibility wrapper for callers that used the original run function."""
    PlaybackSession(playlist_id, mood).run()
