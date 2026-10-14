import argparse
import queue
import re
import sys
import threading
import tkinter as tk
from tkinter import scrolledtext

from emotion_player import MOODS, PlaybackSession


def playlist_id_from_input(value):
    """Accept a Spotify playlist ID, URL, or URI and return its ID."""
    # Normalize all supported input formats to the ID expected by Spotify.
    value = value.strip()
    match = re.search(r"(?:playlist/|playlist:)([A-Za-z0-9]+)", value)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9]+", value):
        return value
    raise ValueError("Enter a Spotify playlist ID, URL, or URI.")


class TerminalWindow:
    def __init__(self, root):
        # Configure the terminal-style interface and its shared output queue.
        self.root = root
        self.root.title("Mood Spotify Player")
        self.root.geometry("800x560")
        self.root.configure(bg="#050505")
        self.output_queue = queue.Queue()
        self.session = None
        self.state = "playlist"

        self.output = scrolledtext.ScrolledText(
            root,
            bg="#050505",
            fg="#d7d7d7",
            insertbackground="#ffffff",
            relief="flat",
            font=("VT323", 12),
            state="disabled",
            wrap="word",
        )
        self.output.pack(fill="both", expand=True, padx=12, pady=(12, 4))
        self.entry = tk.Entry(
            root,
            bg="#111111",
            fg="#ffffff",
            insertbackground="#ffffff",
            relief="flat",
            font=("VT323", 18),
        )
        self.entry.pack(fill="x", padx=12, pady=(4, 12), ipady=8)
        self.entry.bind("<Return>", self.handle_input)
        self.root.protocol("WM_DELETE_WINDOW", self.exit_program)
        self.write("Mood Spotify Player\n")
        self.write("Playlist ID (You can paste the link): ")
        self.entry.focus_set()
        self.root.after(100, self.flush_output)

    def write(self, text):
        self.output.configure(state="normal")
        self.output.insert("end", text)
        self.output.see("end")
        self.output.configure(state="disabled")

    def flush_output(self):
        # Move worker-thread messages onto Tkinter's UI thread safely.
        while True:
            try:
                self.write(self.output_queue.get_nowait())
            except queue.Empty:
                break
        self.root.after(100, self.flush_output)

    def handle_input(self, _event=None):
        # Advance through playlist selection, mood selection, and playback commands.
        value = self.entry.get().strip()
        self.entry.delete(0, "end")
        if not value:
            return "break"
        self.write(f"{value}\n")

        if self.state == "playlist":
            try:
                self.playlist_id = playlist_id_from_input(value)
            except ValueError as error:
                self.write(f"{error}\nPlaylist ID (You can paste the link): ")
                return "break"
            self.state = "mood"
            self.write(f"Playlist: {self.playlist_id}\n")
            self.write("What mood do you want? (happy, sad, energetic, calm): ")
        elif self.state == "mood":
            mood = value.lower()
            if mood not in MOODS:
                self.write("Please type happy, sad, energetic, or calm: ")
            else:
                self.state = "playing"
                self.write(f"Starting {mood} playback...\n")
                threading.Thread(
                    target=self.start_session,
                    args=(self.playlist_id, mood),
                    daemon=True,
                ).start()
        else:
            self.handle_command(value.lower())
        return "break"

    def start_session(self, playlist_id, mood):
        class QueueWriter:
            def __init__(self, output_queue):
                self.output_queue = output_queue

            def write(self, text):
                if text:
                    self.output_queue.put(text)

            def flush(self):
                pass

        old_stdout = sys.stdout
        # Redirect session output so background work appears in the GUI.
        sys.stdout = QueueWriter(self.output_queue)
        try:
            self.session = PlaybackSession(playlist_id, mood)
            self.session.run()
        except Exception as error:
            self.output_queue.put(f"\nError: {error}\n")
        finally:
            sys.stdout = old_stdout

    def handle_command(self, command):
        # Translate text commands into operations on the active playback session.
        if command in MOODS:
            if self.session:
                self.session.correct_current_mood(command)
            else:
                self.write("Playback is still starting. Try again in a moment.\n")
        elif command == "stop":
            self.run_session_command("stop")
        elif command in ("forward", "next"):
            self.run_session_command("forward")
        elif command in ("backward", "back", "previous"):
            self.run_session_command("backward")
        elif command in ("exit", "quit"):
            self.exit_program()
        else:
            self.write(
                "Commands: stop, forward, backward, exit, or type a mood "
                "to correct the current song.\n"
            )

    def run_session_command(self, command):
        # Keep Spotify operations off the UI thread so the window stays responsive.
        if self.session:
            threading.Thread(
                target=getattr(self.session, command),
                daemon=True,
            ).start()
        else:
            self.write("Playback is still starting. Try again in a moment.\n")

    def exit_program(self):
        if self.session:
            self.session.exit()
        self.root.destroy()


def run_gui():
    # Start the Tkinter event loop for interactive use without CLI arguments.
    root = tk.Tk()
    TerminalWindow(root)
    root.mainloop()


def main():
    # CLI mode accepts direct arguments; without a playlist it opens the GUI.
    parser = argparse.ArgumentParser(description="Play Spotify tracks that match your mood.")
    parser.add_argument("--playlist", help="Your Spotify playlist ID, URL, or URI")
    parser.add_argument("--mood", choices=MOODS, help="Mood to play (omit to be asked)")
    args = parser.parse_args()

    if not args.playlist:
        run_gui()
        return

    playlist_id = playlist_id_from_input(args.playlist)
    mood = args.mood
    if not mood:
        mood = input(f"How are you feeling? ({'/'.join(MOODS)}): ").strip().lower()
        if mood not in MOODS:
            print(f"Unknown mood '{mood}', defaulting to 'calm'.")
            mood = "calm"

    PlaybackSession(playlist_id, mood).run()


if __name__ == "__main__":
    main()
