import requests

_classifier = None


def _get_classifier():
    """Lazy-load the model so `import lyrics_emotion` stays fast."""
    global _classifier
    if _classifier is None:
        # Load the transformer only when classification is first requested.
        from transformers import pipeline
        _classifier = pipeline(
            "text-classification",
            model="j-hartmann/emotion-english-distilroberta-base",
            top_k=1,
            truncation=True,
            max_length=512,
        )
    return _classifier


# Lyrics tell us tone (valence), not loudness (energy). We approximate
# energy from the artist's genre tags instead, then combine the two into
# the same happy/sad/energetic/calm quadrants the old valence-energy
# audio features used to give us directly.
VALENCE_MAP = {
    "joy": "positive",
    "surprise": "positive",
    "sadness": "negative",
    "fear": "negative",
    "anger": "negative",
    "disgust": "negative",
    "neutral": "neutral",
}

# Fallback energy guess from the lyric emotion alone, used only when we
# have no genre info at all (e.g. artist lookup failed).
FALLBACK_ENERGY_FROM_LABEL = {
    "anger": "high",
    "disgust": "high",
    "joy": "high",
    "surprise": "high",
    "sadness": "low",
    "fear": "low",
    "neutral": "low",
}

HIGH_ENERGY_GENRE_KEYWORDS = [
    "metal", "punk", "hardcore", "rock", "edm", "techno", "house",
    "dubstep", "drum and bass", "drum-and-bass", "dnb", "trap", "dance", "industrial",
    "grunge", "hard rock", "rave",
]

LOW_ENERGY_GENRE_KEYWORDS = [
    "acoustic", "ambient", "classical", "chill", "lo-fi", "lofi",
    "singer-songwriter", "soul", "jazz", "folk", "ballad", "piano",
]


def estimate_energy_from_genres(genres):
    # Genre keywords provide an approximate energy level when audio features are unavailable.
    if not genres:
        return None
    text = " ".join(genres).lower()
    if any(k in text for k in HIGH_ENERGY_GENRE_KEYWORDS):
        return "high"
    if any(k in text for k in LOW_ENERGY_GENRE_KEYWORDS):
        return "low"
    return None


def fetch_lyrics(artist, title):
    """Free, no-auth lyrics lookup. Returns "" if not found."""
    try:
        resp = requests.get(f"https://api.lyrics.ovh/v1/{artist}/{title}", timeout=5) #get lyrics from lyrics.ovh API
        if resp.status_code == 200:
            return resp.json().get("lyrics", "")
    except requests.RequestException:
        pass
    return ""


def classify_mood(artist, title, genres=None):
    """Returns one of: happy, sad, energetic, calm."""
    # Combine lyric sentiment (valence) with genre-based intensity (energy).
    lyrics = fetch_lyrics(artist, title)
    energy = estimate_energy_from_genres(genres)

    if not lyrics.strip():
        # No lyrics to read tone from -> fall back to genre-only guess.
        return "energetic" if energy == "high" else "calm"

    # Limit the model input to keep each classification reasonably fast.
    snippet = lyrics[:2000]  # keep inference fast
    result = _get_classifier()(snippet)[0][0]
    label = result["label"].lower()
    valence = VALENCE_MAP.get(label, "neutral")

    if energy is None:
        energy = FALLBACK_ENERGY_FROM_LABEL.get(label, "low")

    if valence == "positive":
        return "happy" if energy == "high" else "calm"
    if valence == "negative":
        return "energetic" if energy == "high" else "sad"
    # neutral valence
    return "energetic" if energy == "high" else "calm"