"""
Quick sanity check for the classifier, with no Spotify auth required.
Run: python test_classify.py
"""
import lyrics_emotion as le
 
# These examples exercise lyric lookup and the genre-based energy fallback.
TEST_SONGS = [
    ("Adele", "Someone Like You", []),                    # expect: sad
    ("Pharrell Williams", "Happy", ["pop"]),               # expect: happy
    ("Metallica", "Enter Sandman", ["thrash metal", "hard rock"]),  # expect: energetic
]
 
for artist, title, genres in TEST_SONGS:
    # Print both the predicted mood and whether lyrics were available.
    lyrics = le.fetch_lyrics(artist, title)
    found = "lyrics found" if lyrics.strip() else "NO LYRICS FOUND (will default via genre)"
    mood = le.classify_mood(artist, title, genres=genres)
    print(f"{artist} - {title}: {mood}  [{found}]")
 