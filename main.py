import argparse

from emotion_player import run, MOODS


def main():
    parser = argparse.ArgumentParser(description="Play Spotify tracks that match your mood.")
    parser.add_argument("--playlist", required=True, help="Your Spotify playlist ID or URI")
    parser.add_argument("--mood", choices=MOODS, help="Mood to play (omit to be asked)")
    args = parser.parse_args()

    mood = args.mood
    if not mood:
        mood = input(f"How are you feeling? ({'/'.join(MOODS)}): ").strip().lower()
        if mood not in MOODS:
            print(f"Unknown mood '{mood}', defaulting to 'calm'.")
            mood = "calm"

    run(args.playlist, mood)


if __name__ == "__main__":
    main()
