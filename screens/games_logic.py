"""
screens/games_logic.py
DAN Automation Agent — Game Logic (UI-agnostic)

This file contains pure game logic with NO UI code — no Kivy, no
Termux:GUI, nothing visual. Each game is a class you drive by calling
methods and reading properties. This means the exact same logic can be
tested right now via a Termux:GUI harness or plain text in the terminal,
and later reused unchanged inside screens/games_screen.py once the app
is Kivy-based (after the Colab build). We only write the UI wiring once,
against logic that's already tested.

Games:
- TriviaBattle: 10 questions, tracks score, one question at a time.
  Reuses modules/entertainment.py's trivia fetching pattern (Open Trivia DB).
- MysteryBox: reveals a random challenge/dare from a local bank.
- WordChain: player types words starting with the last letter of the
  previous word; tracks used words and score.
"""

import random
import requests

REQUEST_TIMEOUT = 8


# =============================================================================
# TRIVIA BATTLE
# =============================================================================
class TriviaBattle:
    """
    Usage:
        game = TriviaBattle()
        game.start()                     # fetches 10 questions
        game.current_question()          # -> question text + options
        game.answer("A")                 # -> True/False, advances question
        game.is_finished()               # -> bool
        game.final_score()               # -> "7/10"
    """

    def __init__(self, total_questions=10):
        self.total_questions = total_questions
        self.questions = []
        self.index = 0
        self.score = 0
        self.started = False

    def start(self):
        self.questions = self._fetch_questions(self.total_questions)
        self.index = 0
        self.score = 0
        self.started = True
        return len(self.questions) > 0

    def _fetch_questions(self, amount):
        try:
            url = "https://opentdb.com/api.php"
            params = {"amount": amount, "type": "multiple"}
            r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            data = r.json()

            questions = []
            for q in data.get("results", []):
                question_text = self._unescape(q.get("question", ""))
                correct = self._unescape(q.get("correct_answer", ""))
                incorrect = [self._unescape(a) for a in q.get("incorrect_answers", [])]

                options = incorrect + [correct]
                random.shuffle(options)

                questions.append({
                    "question": question_text,
                    "options": options,
                    "correct": correct,
                })
            return questions
        except requests.exceptions.RequestException:
            return []

    @staticmethod
    def _unescape(text):
        replacements = {
            "&quot;": '"', "&#039;": "'", "&amp;": "&",
            "&lt;": "<", "&gt;": ">", "&eacute;": "e",
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        return text

    def current_question(self):
        if self.is_finished():
            return None
        q = self.questions[self.index]
        return {
            "number": self.index + 1,
            "total": len(self.questions),
            "question": q["question"],
            "options": q["options"],
        }

    def answer(self, chosen_option):
        if self.is_finished():
            return False

        q = self.questions[self.index]
        correct = chosen_option.strip() == q["correct"].strip()
        if correct:
            self.score += 1
        self.index += 1
        return correct

    def is_finished(self):
        return self.started and self.index >= len(self.questions)

    def final_score(self):
        return f"{self.score}/{len(self.questions)}"


# =============================================================================
# MYSTERY BOX
# =============================================================================
class MysteryBox:
    """
    Usage:
        game = MysteryBox()
        game.reveal()   # -> a random challenge string, different each call
                          until the bank is exhausted, then reshuffles
    """

    CHALLENGES = [
        "Do 10 push-ups right now.",
        "Say the alphabet backwards.",
        "Text a friend a random emoji with no explanation.",
        "Hold a plank for 30 seconds.",
        "Name 5 countries in 10 seconds.",
        "Do your best impression of a Nigerian market seller.",
        "Sing the chorus of your favorite song out loud.",
        "Balance a spoon on your nose for 5 seconds.",
        "List 3 things you're grateful for right now.",
        "Do 20 jumping jacks.",
        "Speak in a random accent for the next 2 minutes.",
        "Try to touch your toes without bending your knees.",
        "Recite a tongue twister 3 times fast.",
        "Draw a self-portrait using only your non-dominant hand (describe it).",
        "Come up with a nickname for yourself and use it for the rest of the day.",
    ]

    def __init__(self):
        self._remaining = list(self.CHALLENGES)
        random.shuffle(self._remaining)

    def reveal(self):
        if not self._remaining:
            self._remaining = list(self.CHALLENGES)
            random.shuffle(self._remaining)
        return self._remaining.pop()


# =============================================================================
# WORD CHAIN
# =============================================================================
class WordChain:
    """
    Usage:
        game = WordChain()
        game.start("apple")              # seeds the chain
        game.submit("elephant")          # -> (True, "") or (False, "reason")
        game.used_words                  # -> list of words played so far
        game.score                       # -> int, one point per valid word
    """

    MIN_WORD_LENGTH = 3

    def __init__(self):
        self.used_words = []
        self.score = 0
        self.last_letter = None

    def start(self, seed_word=None):
        self.used_words = []
        self.score = 0
        if seed_word:
            seed_word = seed_word.strip().lower()
            self.used_words.append(seed_word)
            self.last_letter = seed_word[-1]
        else:
            self.last_letter = None
        return self.last_letter

    def submit(self, word):
        word = word.strip().lower()

        if not word.isalpha():
            return False, "Words must be letters only."

        if len(word) < self.MIN_WORD_LENGTH:
            return False, f"Word must be at least {self.MIN_WORD_LENGTH} letters."

        if word in self.used_words:
            return False, "That word's already been used."

        if self.last_letter and not word.startswith(self.last_letter):
            return False, f"Word must start with '{self.last_letter}'."

        self.used_words.append(word)
        self.last_letter = word[-1]
        self.score += 1
        return True, ""

    def current_prompt(self):
        if self.last_letter is None:
            return "Type any word to start the chain."
        return f"Type a word starting with '{self.last_letter}'."
