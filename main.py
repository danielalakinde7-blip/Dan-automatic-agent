"""
main.py
DAN Automation Agent — App Shell

This is the entry point. It sets up:
- APP_DATA: the single dict holding all persistent state, loaded from and
  saved to dan_data.json in the app root.
- Light/dark theme system.
- Chat-bubble UI (user messages right-aligned, DAN's replies left-aligned).
- Scrollable chat area.
- Quick action grid (common one-tap actions).
- Settings screen (theme toggle, username, premium status placeholder).
- Command input bar with send button.
- Live date/time ticker in the header.

Every module's handle(keyword, rest, APP_DATA) function gets called from
modules/parser.py, which this file calls into for every command the user
sends. main.py itself doesn't know about individual features — it only
knows about the chat UI and persistence.
"""

import json
import os
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import StringProperty, BooleanProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.switch import Switch
from kivy.uix.popup import Popup
from kivy.graphics import Color, RoundedRectangle

from modules import parser


# ---------------------------------------------------------------------------
# PATHS / PERSISTENCE
# ---------------------------------------------------------------------------
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(APP_ROOT, "dan_data.json")

DEFAULT_DATA = {
    "theme": "dark",
    "is_premium": False,
    "username": None,
    "tasks": [],
    "notes": [],
    "shopping": [],
    "diary": [],
    "habits": [],
    "budget": {"income": 0, "expenses": 0, "log": []},
    "spots": [],
    "location_history": [],
    "spot_reminders": [],
    "emergency_contact": "",
    "passwords": {},
    "memory": {},
    "workouts": [],
    "sleep_log": [],
    "medicine_log": [],
    "recordings": [],
    "conversations": [],
    "monitored_sites": [],
    "briefing_time": None,
    "routines": {},
    "nlu_api_key": None,
}


def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # backfill any keys added in later versions of the app
            for key, default_value in DEFAULT_DATA.items():
                data.setdefault(key, default_value)
            return data
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_DATA)


def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except OSError:
        return False


APP_DATA = load_data()


# ---------------------------------------------------------------------------
# THEME SYSTEM
# ---------------------------------------------------------------------------
THEMES = {
    "dark": {
        "bg": "1a1a2eff",
        "surface": "22223bff",
        "primary": "4ecdc4ff",
        "accent": "ff6b6bff",
        "text": "f5f5f5ff",
        "text_dim": "9a9a9aff",
        "bubble_user": "4ecdc4ff",
        "bubble_dan": "2d2d44ff",
    },
    "light": {
        "bg": "f5f5f5ff",
        "surface": "ffffffff",
        "primary": "3aa9a0ff",
        "accent": "e85555ff",
        "text": "1a1a1aff",
        "text_dim": "6a6a6aff",
        "bubble_user": "3aa9a0ff",
        "bubble_dan": "e0e0e0ff",
    },
}


def hex_to_rgba(hex_str):
    hex_str = hex_str.lstrip("#")
    r = int(hex_str[0:2], 16) / 255
    g = int(hex_str[2:4], 16) / 255
    b = int(hex_str[4:6], 16) / 255
    a = int(hex_str[6:8], 16) / 255 if len(hex_str) >= 8 else 1
    return (r, g, b, a)


def theme():
    return THEMES.get(APP_DATA.get("theme", "dark"), THEMES["dark"])


def c(key):
    return hex_to_rgba(theme().get(key, "000000ff"))


# ---------------------------------------------------------------------------
# CHAT BUBBLE WIDGET
# ---------------------------------------------------------------------------
class ChatBubble(BoxLayout):
    def __init__(self, text, is_user, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.padding = (dp(10), dp(4))

        label = Label(
            text=text,
            color=c("text") if not is_user else (1, 1, 1, 1),
            size_hint_x=0.78,
            halign="left" if not is_user else "right",
            valign="middle",
            text_size=(Window.width * 0.6, None),
        )
        label.bind(texture_size=self._update_label_height)
        self._label = label

        bubble_color = c("bubble_user") if is_user else c("bubble_dan")
        with label.canvas.before:
            Color(*bubble_color)
            self._rect = RoundedRectangle(radius=[dp(14)])
        label.bind(pos=self._update_rect, size=self._update_rect)

        if is_user:
            spacer = BoxLayout(size_hint_x=0.22)
            self.add_widget(spacer)
            self.add_widget(label)
        else:
            self.add_widget(label)
            spacer = BoxLayout(size_hint_x=0.22)
            self.add_widget(spacer)

    def _update_rect(self, instance, value):
        self._rect.pos = instance.pos
        self._rect.size = instance.size

    def _update_label_height(self, instance, value):
        instance.height = value[1] + dp(20)
        self.height = instance.height


# ---------------------------------------------------------------------------
# MAIN CHAT SCREEN
# ---------------------------------------------------------------------------
class ChatScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical")

        # --- Header ---
        header = BoxLayout(size_hint_y=None, height=dp(56), padding=(dp(12), 0))
        with header.canvas.before:
            Color(*c("surface"))
            self._header_rect = RoundedRectangle(radius=[0])
        header.bind(pos=self._update_header_rect, size=self._update_header_rect)

        self.time_label = Label(text="", color=c("text_dim"), font_size=dp(13), halign="left")
        title_label = Label(text="DAN", bold=True, color=c("primary"), font_size=dp(20))
        settings_btn = Button(
            text="\u2699", size_hint_x=None, width=dp(44),
            background_color=(0, 0, 0, 0), color=c("text"),
        )
        settings_btn.bind(on_release=self.open_settings)

        header.add_widget(self.time_label)
        header.add_widget(title_label)
        header.add_widget(settings_btn)
        root.add_widget(header)

        # --- Chat scroll area ---
        self.scroll = ScrollView(size_hint=(1, 1))
        self.chat_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4), padding=(0, dp(8)))
        self.chat_box.bind(minimum_height=self.chat_box.setter("height"))
        self.scroll.add_widget(self.chat_box)
        root.add_widget(self.scroll)

        # --- Quick action grid ---
        self.quick_grid = self._build_quick_actions()
        root.add_widget(self.quick_grid)

        # --- Input bar ---
        input_bar = BoxLayout(size_hint_y=None, height=dp(56), padding=(dp(8), dp(6)), spacing=dp(6))
        self.text_input = TextInput(
            hint_text="Type a command...",
            multiline=False,
            size_hint_x=0.85,
            background_color=c("surface"),
            foreground_color=c("text"),
        )
        self.text_input.bind(on_text_validate=self.on_send)
        send_btn = Button(text="Send", size_hint_x=0.15, background_color=c("primary"))
        send_btn.bind(on_release=self.on_send)
        input_bar.add_widget(self.text_input)
        input_bar.add_widget(send_btn)
        root.add_widget(input_bar)

        self.add_widget(root)

        Clock.schedule_interval(self._tick, 1)
        self._greet()

    def _update_header_rect(self, instance, value):
        self._header_rect.pos = instance.pos
        self._header_rect.size = instance.size

    def _tick(self, dt):
        self.time_label.text = datetime.now().strftime("%a %d %b · %H:%M")

    def _greet(self):
        name = APP_DATA.get("username")
        if not name:
            self.add_bubble("Hey! I don't think we've met — what should I call you?", is_user=False)
        else:
            self.add_bubble(f"Hey {name}! Type 'help' to see what I can do.", is_user=False)

    def _build_quick_actions(self):
        grid = GridLayout(cols=4, size_hint_y=None, height=dp(120), padding=dp(6), spacing=dp(6))
        actions = [
            ("Torch", "torch"), ("Silent", "silent"), ("Battery", "battery"),
            ("Alarm", "alarm"), ("Weather", "weather Lagos"), ("Rate", "crypto btc"),
            ("Tasks", "tasks"), ("Note", "note "), ("Timer", "timer 5"),
            ("Focus", "focus 30"), ("Meds", "meds"), ("Games", "games"),
        ]
        for label, command in actions:
            btn = Button(text=label, background_color=c("surface"), color=c("text"), font_size=dp(12))
            btn.bind(on_release=lambda inst, cmd=command: self._quick_action(cmd))
            grid.add_widget(btn)
        return grid

    def _quick_action(self, command):
        self.text_input.text = command
        self.on_send(None)

    def add_bubble(self, text, is_user):
        bubble = ChatBubble(text=text, is_user=is_user, size_hint_y=None)
        self.chat_box.add_widget(bubble)
        Clock.schedule_once(self._scroll_to_bottom, 0.05)

    def _scroll_to_bottom(self, dt):
        self.scroll.scroll_y = 0

    def on_send(self, instance):
        text = self.text_input.text.strip()
        if not text:
            return

        self.add_bubble(text, is_user=True)
        self.text_input.text = ""

        reply = parser.handle_command(text, APP_DATA)
        save_data(APP_DATA)

        self.add_bubble(reply, is_user=False)

    def open_settings(self, instance):
        App.get_running_app().root.current = "settings"


# ---------------------------------------------------------------------------
# SETTINGS SCREEN
# ---------------------------------------------------------------------------
class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(16))

        back_btn = Button(text="< Back", size_hint_y=None, height=dp(44), background_color=c("surface"), color=c("text"))
        back_btn.bind(on_release=self.go_back)
        root.add_widget(back_btn)

        root.add_widget(Label(text="Settings", font_size=dp(22), bold=True, color=c("primary"), size_hint_y=None, height=dp(40)))

        # Theme toggle
        theme_row = BoxLayout(size_hint_y=None, height=dp(48))
        theme_row.add_widget(Label(text="Dark theme", color=c("text")))
        theme_switch = Switch(active=(APP_DATA.get("theme") == "dark"))
        theme_switch.bind(active=self.toggle_theme)
        theme_row.add_widget(theme_switch)
        root.add_widget(theme_row)

        # Username
        root.add_widget(Label(text="Username", color=c("text_dim"), size_hint_y=None, height=dp(24), halign="left"))
        self.username_input = TextInput(
            text=APP_DATA.get("username", ""), multiline=False, size_hint_y=None, height=dp(44),
            background_color=c("surface"), foreground_color=c("text"),
        )
        self.username_input.bind(text=self.update_username)
        root.add_widget(self.username_input)

        # Premium status
        premium_text = "Premium: Active" if APP_DATA.get("is_premium") else "Premium: Free tier"
        root.add_widget(Label(text=premium_text, color=c("text"), size_hint_y=None, height=dp(30)))

        upgrade_btn = Button(
            text="Upgrade to Premium", size_hint_y=None, height=dp(48),
            background_color=c("accent"),
        )
        upgrade_btn.bind(on_release=self.show_upgrade_placeholder)
        root.add_widget(upgrade_btn)

        root.add_widget(BoxLayout())  # spacer
        self.add_widget(root)

    def go_back(self, instance):
        App.get_running_app().root.current = "chat"

    def toggle_theme(self, instance, value):
        APP_DATA["theme"] = "dark" if value else "light"
        save_data(APP_DATA)
        self._show_restart_notice()

    def update_username(self, instance, value):
        APP_DATA["username"] = value
        save_data(APP_DATA)

    def show_upgrade_placeholder(self, instance):
        popup = Popup(
            title="Upgrade to Premium",
            content=Label(text="Paystack checkout not wired up yet.\nComing soon: ₦500/month."),
            size_hint=(0.8, 0.4),
        )
        popup.open()

    def _show_restart_notice(self):
        popup = Popup(
            title="Theme changed",
            content=Label(text="Restart the app to see the new theme fully applied."),
            size_hint=(0.8, 0.3),
        )
        popup.open()


# ---------------------------------------------------------------------------
# APP
# ---------------------------------------------------------------------------
class DANApp(App):
    def build(self):
        Window.clearcolor = c("bg")
        sm = ScreenManager(transition=SlideTransition())
        sm.add_widget(ChatScreen(name="chat"))
        sm.add_widget(SettingsScreen(name="settings"))
        return sm

    def on_stop(self):
        save_data(APP_DATA)


if __name__ == "__main__":
    DANApp().run()
