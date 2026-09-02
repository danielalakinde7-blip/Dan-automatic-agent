"""
screens/termuxgui_demo.py
DAN Automation Agent — Termux:GUI test harness

Lets you play Trivia Battle, Mystery Box, and Word Chain visually on your
phone RIGHT NOW, using the Termux:GUI addon app instead of waiting for a
full Colab/Buildozer APK build. This is a TEST HARNESS ONLY — it's not
part of the final app. The final app will use screens/games_screen.py
with Kivy widgets, reusing the exact same games_logic.py classes.

REQUIREMENTS:
1. Install the "Termux:GUI" app from F-Droid (separate from Termux itself).
2. Open Termux:GUI at least once so it registers.
3. In Termux: pip install termuxgui

RUN:
    cd ~/dan_automation
    python3 screens/termuxgui_demo.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import termuxgui as tg
from screens.games_logic import TriviaBattle, MysteryBox, WordChain


def main():
    connection = tg.Connection()
    activity = tg.Activity(connection)

    root_layout = tg.LinearLayout(activity)

    title = tg.TextView(activity, "DAN Games (Termux:GUI Demo)", root_layout)
    title.settextsize(22)

    menu_layout = tg.LinearLayout(activity, root_layout)

    trivia_btn = tg.Button(activity, "Trivia Battle", menu_layout)
    mystery_btn = tg.Button(activity, "Mystery Box", menu_layout)
    wordchain_btn = tg.Button(activity, "Word Chain", menu_layout)

    status = tg.TextView(activity, "Pick a game above.", root_layout)
    status.settextsize(16)

    action_layout = tg.LinearLayout(activity, root_layout)
    input_field = tg.EditText(activity, "", action_layout)
    submit_btn = tg.Button(activity, "Submit", action_layout)

    state = {"game": None, "mode": None}

    def show_trivia_question():
        game = state["game"]
        q = game.current_question()
        if q is None:
            status.settext(f"Trivia over! Score: {game.final_score()}")
            state["mode"] = None
            return
        options_text = "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(q["options"]))
        status.settext(
            f"Q{q['number']}/{q['total']}: {q['question']}\n\n{options_text}\n\n"
            f"Type the option NUMBER and submit."
        )

    def start_trivia():
        status.settext("Loading trivia questions...")
        game = TriviaBattle()
        if not game.start():
            status.settext("Couldn't load trivia — check your internet connection.")
            return
        state["game"] = game
        state["mode"] = "trivia"
        show_trivia_question()

    def start_mystery():
        state["game"] = MysteryBox()
        state["mode"] = "mystery"
        challenge = state["game"].reveal()
        status.settext(f"Mystery Box:\n\n{challenge}\n\nType 'next' and submit for another.")

    def start_wordchain():
        game = WordChain()
        game.start()
        state["game"] = game
        state["mode"] = "wordchain"
        status.settext(f"Word Chain — Score: 0\n{game.current_prompt()}")

    def handle_submit(event):
        mode = state["mode"]
        text = input_field.gettext().strip()
        input_field.settext("")

        if mode == "trivia":
            game = state["game"]
            q = game.current_question()
            if q is None:
                return
            try:
                choice_idx = int(text) - 1
                if 0 <= choice_idx < len(q["options"]):
                    chosen = q["options"][choice_idx]
                    correct = game.answer(chosen)
                    prefix = "Correct! " if correct else "Wrong. "
                    status.settext(prefix + "Loading next question...")
                    show_trivia_question()
                else:
                    status.settext("Enter a valid option number.")
            except ValueError:
                status.settext("Enter the option NUMBER (e.g. 1, 2, 3, 4).")

        elif mode == "mystery":
            if text.lower() == "next":
                challenge = state["game"].reveal()
                status.settext(f"Mystery Box:\n\n{challenge}\n\nType 'next' and submit for another.")

        elif mode == "wordchain":
            game = state["game"]
            ok, reason = game.submit(text)
            if ok:
                status.settext(f"Word Chain — Score: {game.score}\n{game.current_prompt()}")
            else:
                status.settext(f"'{text}' rejected: {reason}\n{game.current_prompt()}")

    def on_trivia_click(event):
        start_trivia()

    def on_mystery_click(event):
        start_mystery()

    def on_wordchain_click(event):
        start_wordchain()

    connection.set_events_target(activity)

    for event in connection.events():
        if isinstance(event, tg.events.ClickEvent):
            if event.view == trivia_btn:
                on_trivia_click(event)
            elif event.view == mystery_btn:
                on_mystery_click(event)
            elif event.view == wordchain_btn:
                on_wordchain_click(event)
            elif event.view == submit_btn:
                handle_submit(event)
        elif isinstance(event, tg.events.DestroyEvent):
            break

    connection.close()


if __name__ == "__main__":
    main()
