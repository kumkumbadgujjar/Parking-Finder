"""
login.py
Preserves existing users.json authentication (SHA-256 and legacy plaintext compatibility),
provides Login / Registration UI with show/hide password, and supports Change Password.
"""

import hashlib
import json
import os
import tkinter as tk
from typing import Callable, Dict, Optional

USERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.json")

# Minimal Dark Navy, White, and Green theme
NAVY_DARK = "#0f172a"
NAVY_CARD = "#1e293b"
NAVY_ACTIVE = "#334155"
WHITE = "#ffffff"
SLATE_LIGHT = "#f8fafc"
TEXT_MUTED = "#64748b"
BORDER_COLOR = "#cbd5e1"
GREEN_PRIMARY = "#10b981"
GREEN_HOVER = "#059669"
RED_ERROR = "#dc2626"
GREEN_SUCCESS = "#15803d"


def hash_password(password: str) -> str:
    """Return SHA-256 hex digest for a password."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def ensure_users_file() -> None:
    """Create users.json if it does not exist."""
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump({"users": []}, f, indent=2)


def load_users() -> Dict[str, list]:
    """Load user records from users.json safely."""
    ensure_users_file()
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("users"), list):
                return data
    except (json.JSONDecodeError, OSError):
        pass
    return {"users": []}


def save_users(data: Dict[str, list]) -> None:
    """Save user records to users.json."""
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def user_exists(username: str) -> bool:
    """Check if a username already exists."""
    data = load_users()
    return any(u.get("username") == username for u in data["users"])


def authenticate_user(username: str, password: str) -> Optional[Dict[str, str]]:
    """Verify username and password against users.json (SHA-256 or legacy plaintext)."""
    data = load_users()
    hashed = hash_password(password)
    for user in data["users"]:
        if user.get("username") == username and user.get("password") in (password, hashed):
            return user
    return None


def register_user(username: str, password: str, email: str = "") -> tuple[bool, str]:
    """Register a new user in users.json with SHA-256 password hashing."""
    username = username.strip()
    email = email.strip()

    if not username:
        return False, "Please enter a username."
    if len(username) < 3:
        return False, "Username must be at least 3 characters long."
    if not password:
        return False, "Please enter a password."
    if len(password) < 4:
        return False, "Password must be at least 4 characters long."
    if user_exists(username):
        return False, f"Username '{username}' is already taken."

    data = load_users()
    data["users"].append(
        {
            "username": username,
            "password": hash_password(password),
            "email": email,
        }
    )
    save_users(data)
    return True, "Account created successfully! You can now log in."


def change_user_password(
    username: str,
    current_password: str,
    new_password: str,
    confirm_password: str,
) -> tuple[bool, str]:
    """Validate current password and update password in users.json."""
    if not current_password or not new_password or not confirm_password:
        return False, "All password fields are required."
    if new_password != confirm_password:
        return False, "New password and confirmation do not match."
    if len(new_password) < 4:
        return False, "New password must be at least 4 characters long."

    data = load_users()
    current_hash = hash_password(current_password)
    for user in data["users"]:
        if user.get("username") == username:
            stored = user.get("password", "")
            if stored not in (current_password, current_hash):
                return False, "Current password is incorrect."
            user["password"] = hash_password(new_password)
            save_users(data)
            return True, "Password updated successfully!"

    return False, "User account not found."


def add_hover_effect(widget: tk.Button, normal_bg: str, hover_bg: str) -> None:
    """Apply background hover effect to a Tkinter Button."""
    widget.bind("<Enter>", lambda _e: widget.configure(bg=hover_bg))
    widget.bind("<Leave>", lambda _e: widget.configure(bg=normal_bg))


class AuthFrame(tk.Frame):
    """Minimal modern Login & Registration screen."""

    def __init__(self, parent: tk.Widget, on_login_success: Callable[[Dict[str, str]], None]):
        super().__init__(parent, bg=NAVY_DARK)
        self.on_login_success = on_login_success
        self.mode = "login"
        self.show_password_var = tk.BooleanVar(value=False)
        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        card = tk.Frame(
            self,
            bg=WHITE,
            highlightthickness=1,
            highlightbackground="#334155",
            padx=36,
            pady=32,
        )
        card.grid(row=0, column=0, padx=24, pady=24)

        tk.Label(
            card,
            text="SMART PARKING FINDER",
            font=("Segoe UI", 10, "bold"),
            fg=GREEN_HOVER,
            bg="#ecfdf5",
            padx=10,
            pady=4,
        ).pack(pady=(0, 10))

        self.title_label = tk.Label(
            card,
            text="Login",
            font=("Segoe UI", 22, "bold"),
            fg=NAVY_DARK,
            bg=WHITE,
        )
        self.title_label.pack()

        self.subtitle_label = tk.Label(
            card,
            text="Sign in with your username and password",
            font=("Segoe UI", 10),
            fg=TEXT_MUTED,
            bg=WHITE,
        )
        self.subtitle_label.pack(pady=(4, 16))

        self.message_label = tk.Label(
            card,
            text="",
            font=("Segoe UI", 9, "bold"),
            fg=RED_ERROR,
            bg=WHITE,
            wraplength=310,
            justify="left",
        )
        self.message_label.pack(fill="x", pady=(0, 8))

        tk.Label(
            card,
            text="Username",
            font=("Segoe UI", 10, "bold"),
            fg=NAVY_DARK,
            bg=WHITE,
            anchor="w",
        ).pack(fill="x")
        self.username_entry = tk.Entry(
            card,
            font=("Segoe UI", 11),
            bg=SLATE_LIGHT,
            fg=NAVY_DARK,
            relief="solid",
            bd=1,
            width=32,
        )
        self.username_entry.pack(fill="x", pady=(4, 12), ipady=6)

        self.email_container = tk.Frame(card, bg=WHITE)
        tk.Label(
            self.email_container,
            text="Email (optional)",
            font=("Segoe UI", 10, "bold"),
            fg=NAVY_DARK,
            bg=WHITE,
            anchor="w",
        ).pack(fill="x")
        self.email_entry = tk.Entry(
            self.email_container,
            font=("Segoe UI", 11),
            bg=SLATE_LIGHT,
            fg=NAVY_DARK,
            relief="solid",
            bd=1,
            width=32,
        )
        self.email_entry.pack(fill="x", pady=(4, 12), ipady=6)

        self.password_label = tk.Label(
            card,
            text="Password",
            font=("Segoe UI", 10, "bold"),
            fg=NAVY_DARK,
            bg=WHITE,
            anchor="w",
        )
        self.password_label.pack(fill="x")

        pwd_row = tk.Frame(card, bg=WHITE)
        pwd_row.pack(fill="x", pady=(4, 6))

        self.password_entry = tk.Entry(
            pwd_row,
            font=("Segoe UI", 11),
            bg=SLATE_LIGHT,
            fg=NAVY_DARK,
            relief="solid",
            bd=1,
            show="*",
        )
        self.password_entry.pack(side="left", fill="x", expand=True, ipady=6)

        self.toggle_pwd_btn = tk.Button(
            pwd_row,
            text="Show",
            font=("Segoe UI", 9, "bold"),
            bg="#e2e8f0",
            fg=NAVY_DARK,
            relief="flat",
            padx=10,
            cursor="hand2",
            command=self._toggle_password,
        )
        self.toggle_pwd_btn.pack(side="left", padx=(6, 0), ipady=5)
        add_hover_effect(self.toggle_pwd_btn, "#e2e8f0", "#cbd5e1")

        self.submit_btn = tk.Button(
            card,
            text="Login",
            font=("Segoe UI", 11, "bold"),
            bg=GREEN_PRIMARY,
            fg=WHITE,
            activebackground=GREEN_HOVER,
            activeforeground=WHITE,
            relief="flat",
            cursor="hand2",
            pady=9,
            command=self._handle_submit,
        )
        self.submit_btn.pack(fill="x", pady=(14, 10))
        add_hover_effect(self.submit_btn, GREEN_PRIMARY, GREEN_HOVER)

        self.switch_btn = tk.Button(
            card,
            text="Don't have an account? Register",
            font=("Segoe UI", 9, "bold"),
            bg=WHITE,
            fg=NAVY_CARD,
            relief="flat",
            cursor="hand2",
            command=self._toggle_mode,
        )
        self.switch_btn.pack(pady=(2, 0))

        self.username_entry.bind("<Return>", lambda _e: self._handle_submit())
        self.password_entry.bind("<Return>", lambda _e: self._handle_submit())
        self.username_entry.focus_set()

    def _toggle_password(self) -> None:
        showing = not self.show_password_var.get()
        self.show_password_var.set(showing)
        self.password_entry.configure(show="" if showing else "*")
        self.toggle_pwd_btn.configure(text="Hide" if showing else "Show")

    def _toggle_mode(self) -> None:
        self.message_label.configure(text="")
        if self.mode == "login":
            self.mode = "register"
            self.title_label.configure(text="Create Account")
            self.subtitle_label.configure(text="Register a new Smart Parking Finder account")
            self.email_container.pack(fill="x", before=self.password_label)
            self.submit_btn.configure(text="Create Account")
            self.switch_btn.configure(text="Already have an account? Login")
        else:
            self.mode = "login"
            self.title_label.configure(text="Login")
            self.subtitle_label.configure(text="Sign in with your username and password")
            self.email_container.pack_forget()
            self.submit_btn.configure(text="Login")
            self.switch_btn.configure(text="Don't have an account? Register")

    def _show_message(self, text: str, is_error: bool = True) -> None:
        self.message_label.configure(
            text=text,
            fg=RED_ERROR if is_error else GREEN_SUCCESS,
        )

    def _handle_submit(self) -> None:
        username = self.username_entry.get().strip()
        password = self.password_entry.get()

        if self.mode == "login":
            if not username or not password:
                self._show_message("Please enter both username and password.")
                return

            user = authenticate_user(username, password)
            if user is None:
                self._show_message("Invalid username or password. Please try again.")
                return

            self.on_login_success(user)
        else:
            email = self.email_entry.get().strip()
            ok, msg = register_user(username, password, email)
            if not ok:
                self._show_message(msg, is_error=True)
                return

            self._toggle_mode()
            self.username_entry.delete(0, tk.END)
            self.username_entry.insert(0, username)
            self.password_entry.delete(0, tk.END)
            self._show_message(msg, is_error=False)
