import json
import os
import random
import threading
import time

import config
import spotify_client as sc
import lyrics_emotion as le

MOODS = ["happy", "sad", "energetic", "calm"]
MINIMUM_PLAYLIST_TOTAL = 12


def load_cache():
    # Reuse previous classifications so tracks do not need to be analyzed again.
    if os.path.exists(config.CACHE_FILE):
        with open(config.CACHE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    # Persist classifications between runs of the player.
    with open(config.CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def classify_track(sp, track, cache):
    """Mood for one track, using (and filling) the local cache."""
    # Cached moods avoid repeated API calls and model inference.
    mood = cache.get(track["id"])
    if mood is None:
        genres = sc.get_artist_genres(sp, track.get("artist_id"))
        if not genres and track.get("genre_hint"):
            genres = [track["genre_hint"]]
        mood = le.classify_mood(track["artist"], track["name"], genres=genres)
        cache[track["id"]] = mood
    return mood


def classify_library(sp, playlist_id):
    # Build one list per mood so playback can select the requested category.
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
        self.last_next_track_id = None

    def run(self):
        # Classify the playlist before choosing the requested mood.
        self.sp = sc.get_spotify_client()
        buckets, all_ids = classify_library(self.sp, self.playlist_id)
        self.cache = load_cache()
        local_tracks = buckets.get(self.mood, [])[:]
        random.shuffle(local_tracks)

        if not local_tracks:
            print(f"No '{self.mood}' track was found in the playlist.")

        # Find outside songs before playback so they can be placed after the
        # playlist songs in one ordered start_playback request.
        tracks_to_play = local_tracks[:]
        external_needed = max(0, MINIMUM_PLAYLIST_TOTAL - len(tracks_to_play))
        if external_needed:
            external = sc.find_external_tracks_for_mood(
                self.sp,
                self.mood,
                all_ids,
                pages_per_query=1,
                max_candidates=max(external_needed * 3, 12),
            )
            tracks_to_play.extend(
                self._matching_tracks(external, external_needed)
            )
        if not tracks_to_play:
            print(f"Couldn't find any '{self.mood}' tracks.")
            return

        self.device_id = sc.get_active_device_id(self.sp)
        if not self.device_id:
            print("No active Spotify device found. Open Spotify and try again.")
            return

        first = tracks_to_play[0]
        self.current_track_id = first["id"]
        # Spotify's queue endpoint inserts items next, so send the complete
        # playlist-first order in a single playback request instead.
        playlist_batch = tracks_to_play[:100]
        sc.play_uris(
            self.sp,
            [track["uri"] for track in playlist_batch],
            device_id=self.device_id,
        )
        print(f"Now playing: {first['name']} by {first['artist']}")
        print("Commands: stop, forward, backward, exit, or type a mood to correct the current song.")
        self._print_next_track()
        self._monitor()

    def _matching_tracks(self, candidates, target_count):
        # Search results are only candidates; lyrics and genre data decide the final mood.
        matches = []
        for track in candidates:
            if len(matches) >= target_count:
                break
            if classify_track(self.sp, track, self.cache) == self.mood:
                matches.append(track)
        save_cache(self.cache)
        return matches

    def _print_next_track(self):
        next_track = sc.get_next_track(self.sp)
        next_id = next_track["id"] if next_track else None
        if next_id == self.last_next_track_id:
            return
        self.last_next_track_id = next_id
        if next_track:
            print(f"Next: {next_track['name']} by {next_track['artist']}")
        else:
            print("Next: none")

    def _monitor(self):
        last_id = self.current_track_id
        # Poll Spotify so the app can report song changes and save corrections.
        while not self.stop_event.wait(3):
            current = sc.get_currently_playing(self.sp)
            if current and current["id"] == last_id:
                continue
            if not current:
                continue
            self._apply_pending_mood()
            last_id = current["id"]
            self.current_track_id = last_id
            print(f"Now playing: {current['name']} by {current['artist']}")
            self._print_next_track()
        self._apply_pending_mood()

    def correct_current_mood(self, mood):
        # Delay the correction until the song changes so it applies to the song just heard.
        if mood not in MOODS:
            return
        with self.lock:
            if not self.current_track_id:
                print("No current song is available for correction yet.")
                return
            self.pending_mood = mood
        print(f"Marked the current song as '{mood}'. It will be saved when the song changes.")

    def _apply_pending_mood(self):
        # Save a pending correction against the last known track ID.
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
