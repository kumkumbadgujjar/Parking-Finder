"""
main.py
Minimal Python Tkinter desktop application for Smart Parking Finder.
Flow:
  LOGIN SCREEN -> MAIN SCREEN (Find Parking | Change Password | Logout)
Uses Google Places API (New) Nearby Search with languageCode="en", regionCode="IN",
configurable radius (default 3000m), and exact returned coordinates.
"""

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Dict, List, Optional

from location_service import LocationResult, detect_device_location
from login import (
    BORDER_COLOR,
    GREEN_HOVER,
    GREEN_PRIMARY,
    GREEN_SUCCESS,
    NAVY_ACTIVE,
    NAVY_CARD,
    NAVY_DARK,
    RED_ERROR,
    SLATE_LIGHT,
    TEXT_MUTED,
    WHITE,
    AuthFrame,
    add_hover_effect,
    change_user_password,
)
from map_view import generate_and_open_map, open_directions_in_google_maps
from parking_service import ParkingLocation, fetch_google_nearby_parking


class SmartParkingApp:
    """Minimal main application controller: Find Parking + Change Password."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Smart Parking Finder")
        self.root.geometry("1020x680")
        self.root.minsize(840, 580)
        self.root.configure(bg=NAVY_DARK)

        self._configure_styles()

        self.current_user: Optional[Dict[str, str]] = None
        self.current_location: Optional[LocationResult] = None
        self.parkings: List[ParkingLocation] = []
        self.selected_parking: Optional[ParkingLocation] = None
        self.is_loading = False
        self.active_view = "find"

        self.location_error: Optional[str] = None
        self.radius_var = tk.StringVar(value="3000")
        self.status_var = tk.StringVar(
            value="Click 'Find Parking' to detect your current device location."
        )

        self.container = tk.Frame(self.root, bg=NAVY_DARK)
        self.container.pack(fill="both", expand=True)

        self.show_login_screen()

    def _configure_styles(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "Minimal.Treeview",
            background=WHITE,
            foreground=NAVY_DARK,
            fieldbackground=WHITE,
            rowheight=32,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Minimal.Treeview.Heading",
            background=NAVY_CARD,
            foreground=WHITE,
            font=("Segoe UI", 10, "bold"),
            padding=6,
        )
        style.map(
            "Minimal.Treeview",
            background=[("selected", "#d1fae5")],
            foreground=[("selected", NAVY_DARK)],
        )

    def _clear_container(self) -> None:
        for widget in self.container.winfo_children():
            widget.destroy()

    def show_login_screen(self) -> None:
        self._clear_container()
        auth = AuthFrame(self.container, on_login_success=self._on_login_success)
        auth.pack(fill="both", expand=True)

    def _on_login_success(self, user: Dict[str, str]) -> None:
        self.current_user = user
        self.current_location = None
        self.parkings = []
        self.selected_parking = None
        self.active_view = "find"
        self.location_error = None
        self.status_var.set("Click 'Find Parking' to detect your current device location.")
        self._build_main_screen()

    def _logout(self) -> None:
        self.current_user = None
        self.current_location = None
        self.parkings = []
        self.selected_parking = None
        self.show_login_screen()

    # ==================== MAIN SCREEN ====================
    def _build_main_screen(self) -> None:
        self._clear_container()
        self.container.columnconfigure(0, weight=1)
        self.container.rowconfigure(1, weight=1)

        header = tk.Frame(self.container, bg=NAVY_DARK, padx=24, pady=14)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        tk.Label(
            header,
            text="Smart Parking Finder",
            font=("Segoe UI", 18, "bold"),
            fg=WHITE,
            bg=NAVY_DARK,
        ).grid(row=0, column=0, sticky="w")

        actions = tk.Frame(header, bg=NAVY_DARK)
        actions.grid(row=0, column=2, sticky="e")

        username = (self.current_user or {}).get("username", "User")
        tk.Label(
            actions,
            text=f"User: {username}",
            font=("Segoe UI", 10, "bold"),
            fg="#cbd5e1",
            bg=NAVY_DARK,
            padx=12,
        ).pack(side="left")

        self.find_tab_btn = tk.Button(
            actions,
            text="Find Parking",
            font=("Segoe UI", 10, "bold"),
            fg=WHITE,
            bg=GREEN_PRIMARY if self.active_view == "find" else NAVY_CARD,
            relief="flat",
            padx=14,
            pady=6,
            cursor="hand2",
            command=lambda: self._switch_view("find"),
        )
        self.find_tab_btn.pack(side="left", padx=(0, 8))

        self.pwd_tab_btn = tk.Button(
            actions,
            text="Change Password",
            font=("Segoe UI", 10, "bold"),
            fg=WHITE,
            bg=GREEN_PRIMARY if self.active_view == "password" else NAVY_CARD,
            relief="flat",
            padx=14,
            pady=6,
            cursor="hand2",
            command=lambda: self._switch_view("password"),
        )
        self.pwd_tab_btn.pack(side="left", padx=(0, 8))

        logout_btn = tk.Button(
            actions,
            text="Logout",
            font=("Segoe UI", 10, "bold"),
            fg="#fecaca",
            bg="#7f1d1d",
            relief="flat",
            padx=14,
            pady=6,
            cursor="hand2",
            command=self._logout,
        )
        logout_btn.pack(side="left")
        add_hover_effect(logout_btn, "#7f1d1d", "#991b1b")

        self.body_frame = tk.Frame(self.container, bg=SLATE_LIGHT, padx=24, pady=20)
        self.body_frame.grid(row=1, column=0, sticky="nsew")

        self._switch_view(self.active_view)

    def _switch_view(self, view: str) -> None:
        self.active_view = view
        self.find_tab_btn.configure(bg=GREEN_PRIMARY if view == "find" else NAVY_CARD)
        self.pwd_tab_btn.configure(bg=GREEN_PRIMARY if view == "password" else NAVY_CARD)
        add_hover_effect(
            self.find_tab_btn,
            GREEN_PRIMARY if view == "find" else NAVY_CARD,
            GREEN_HOVER if view == "find" else NAVY_ACTIVE,
        )
        add_hover_effect(
            self.pwd_tab_btn,
            GREEN_PRIMARY if view == "password" else NAVY_CARD,
            GREEN_HOVER if view == "password" else NAVY_ACTIVE,
        )

        for widget in self.body_frame.winfo_children():
            widget.destroy()

        if view == "find":
            self._render_find_parking_view()
        else:
            self._render_change_password_view()

    def _get_radius_meters(self) -> float:
        try:
            val = float(self.radius_var.get().strip())
            return max(100.0, min(50000.0, val))
        except ValueError:
            return 3000.0

    # ==================== FIND PARKING ====================
    def _render_find_parking_view(self) -> None:
        frame = self.body_frame
        frame.columnconfigure(0, weight=3)
        frame.columnconfigure(1, weight=2)
        frame.rowconfigure(1, weight=1)

        # Row 0: Live Find Parking Action Card
        action_card = tk.Frame(
            frame,
            bg=WHITE,
            padx=20,
            pady=14,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
        )
        action_card.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        action_card.columnconfigure(1, weight=1)

        self.find_btn = tk.Button(
            action_card,
            text="Locating..." if self.is_loading else "Find Parking",
            font=("Segoe UI", 13, "bold"),
            bg=GREEN_PRIMARY,
            fg=WHITE,
            relief="flat",
            padx=24,
            pady=12,
            cursor="hand2",
            state="disabled" if self.is_loading else "normal",
            command=self.find_parking_live,
        )
        self.find_btn.grid(row=0, column=0, rowspan=2, padx=(0, 18), sticky="ns")
        add_hover_effect(self.find_btn, GREEN_PRIMARY, GREEN_HOVER)

        loc_heading = (
            f"Current Location: {self.current_location.display_name} "
            f"({self.current_location.latitude:.5f}, {self.current_location.longitude:.5f})"
            if self.current_location
            else "Current Location: Not detected yet"
        )
        tk.Label(
            action_card,
            text=loc_heading,
            font=("Segoe UI", 11, "bold"),
            fg=NAVY_DARK,
            bg=WHITE,
            anchor="w",
            wraplength=460,
            justify="left",
        ).grid(row=0, column=1, sticky="w")

        status_wrap = tk.Frame(action_card, bg=WHITE)
        status_wrap.grid(row=1, column=1, sticky="ew", pady=(3, 0))

        self.loading_bar = ttk.Progressbar(status_wrap, mode="indeterminate", length=90)
        if self.is_loading:
            self.loading_bar.pack(side="left", padx=(0, 8))
            self.loading_bar.start(12)

        tk.Label(
            status_wrap,
            textvariable=self.status_var,
            font=("Segoe UI", 9, "bold" if self.location_error else "normal"),
            fg=RED_ERROR if self.location_error else TEXT_MUTED,
            bg=WHITE,
            anchor="w",
            wraplength=420,
            justify="left",
        ).pack(side="left", fill="x", expand=True)

        right_controls = tk.Frame(action_card, bg=WHITE)
        right_controls.grid(row=0, column=2, rowspan=2, padx=(12, 0), sticky="e")

        if self.location_error and not self.is_loading:
            retry_btn = tk.Button(
                right_controls,
                text="Retry",
                font=("Segoe UI", 10, "bold"),
                bg=RED_ERROR,
                fg=WHITE,
                relief="flat",
                padx=12,
                pady=8,
                cursor="hand2",
                command=self.find_parking_live,
            )
            retry_btn.pack(side="left", padx=(0, 10))
            add_hover_effect(retry_btn, RED_ERROR, "#b91c1c")

        tk.Label(
            right_controls,
            text="Radius (m):",
            font=("Segoe UI", 9, "bold"),
            fg=NAVY_DARK,
            bg=WHITE,
        ).pack(side="left", padx=(0, 6))

        radius_entry = tk.Entry(
            right_controls,
            textvariable=self.radius_var,
            font=("Segoe UI", 10),
            bg=SLATE_LIGHT,
            fg=NAVY_DARK,
            relief="solid",
            bd=1,
            width=7,
        )
        radius_entry.pack(side="left", ipady=4, padx=(0, 10))

        map_open_btn = tk.Button(
            right_controls,
            text="Open Map",
            font=("Segoe UI", 10, "bold"),
            bg=NAVY_CARD,
            fg=WHITE,
            relief="flat",
            padx=14,
            pady=8,
            cursor="hand2",
            command=self._open_map,
        )
        map_open_btn.pack(side="left")
        add_hover_effect(map_open_btn, NAVY_CARD, NAVY_ACTIVE)

        # Row 1: Results List (Left) & Selected Parking Details (Right)
        list_card = tk.Frame(
            frame,
            bg=WHITE,
            padx=16,
            pady=14,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
        )
        list_card.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        list_card.rowconfigure(1, weight=1)
        list_card.columnconfigure(0, weight=1)

        tk.Label(
            list_card,
            text=f"Google Places Parking Results ({len(self.parkings)})",
            font=("Segoe UI", 11, "bold"),
            fg=NAVY_DARK,
            bg=WHITE,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        if not self.parkings:
            tk.Label(
                list_card,
                text=(
                    "No parking results loaded yet.\n"
                    "Click 'Find Parking' to automatically detect your current device location\n"
                    "and search genuine nearby parking facilities."
                ),
                font=("Segoe UI", 10),
                fg=TEXT_MUTED,
                bg=WHITE,
                justify="center",
                pady=40,
            ).grid(row=1, column=0, sticky="nsew")
        else:
            table_wrap = tk.Frame(list_card, bg=WHITE)
            table_wrap.grid(row=1, column=0, sticky="nsew")
            table_wrap.rowconfigure(0, weight=1)
            table_wrap.columnconfigure(0, weight=1)

            tree = ttk.Treeview(
                table_wrap,
                columns=("name", "address", "distance"),
                show="headings",
                style="Minimal.Treeview",
            )
            tree.heading("name", text="Parking Name")
            tree.heading("address", text="English Address")
            tree.heading("distance", text="Distance")
            tree.column("name", width=180, anchor="w")
            tree.column("address", width=220, anchor="w")
            tree.column("distance", width=85, anchor="center")

            scroll = ttk.Scrollbar(table_wrap, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scroll.set)
            tree.grid(row=0, column=0, sticky="nsew")
            scroll.grid(row=0, column=1, sticky="ns")

            for idx, p in enumerate(self.parkings):
                tree.insert(
                    "",
                    "end",
                    iid=str(idx),
                    values=(p.name, p.address, f"{p.distance_km:.2f} km"),
                )

            def on_select(_event: tk.Event) -> None:
                sel = tree.selection()
                if sel:
                    self.selected_parking = self.parkings[int(sel[0])]
                    self._render_selected_details()

            tree.bind("<<TreeviewSelect>>", on_select)

        self.details_card = tk.Frame(
            frame,
            bg=WHITE,
            padx=18,
            pady=16,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
        )
        self.details_card.grid(row=1, column=1, sticky="nsew")
        self._render_selected_details()

    def _render_selected_details(self) -> None:
        for w in self.details_card.winfo_children():
            w.destroy()

        tk.Label(
            self.details_card,
            text="Selected Parking",
            font=("Segoe UI", 12, "bold"),
            fg=NAVY_DARK,
            bg=WHITE,
            anchor="w",
        ).pack(fill="x", pady=(0, 10))

        p = self.selected_parking
        if p is None:
            tk.Label(
                self.details_card,
                text="Select a parking location from the list to view its English details and open Google Maps directions.",
                font=("Segoe UI", 10),
                fg=TEXT_MUTED,
                bg=WHITE,
                wraplength=260,
                justify="left",
            ).pack(fill="x", pady=16)
            return

        rows = [
            ("Parking Name", p.name),
            ("Formatted Address", p.address),
            ("Distance", f"{p.distance_km:.2f} km"),
            ("Exact Coordinates", f"{p.latitude:.5f}, {p.longitude:.5f}"),
            ("Place ID", p.place_id or "N/A"),
            ("Data Source", p.data_source),
            ("Availability", p.availability_status),
        ]
        for label, value in rows:
            box = tk.Frame(self.details_card, bg=SLATE_LIGHT, padx=10, pady=5)
            box.pack(fill="x", pady=2)
            tk.Label(
                box, text=label, font=("Segoe UI", 8, "bold"), fg=TEXT_MUTED, bg=SLATE_LIGHT, anchor="w"
            ).pack(fill="x")
            tk.Label(
                box,
                text=value,
                font=("Segoe UI", 9, "bold" if label == "Parking Name" else "normal"),
                fg=NAVY_DARK,
                bg=SLATE_LIGHT,
                anchor="w",
                wraplength=270,
                justify="left",
            ).pack(fill="x")

        dir_btn = tk.Button(
            self.details_card,
            text="Open Directions in Google Maps",
            font=("Segoe UI", 10, "bold"),
            bg=GREEN_PRIMARY,
            fg=WHITE,
            relief="flat",
            pady=9,
            cursor="hand2",
            command=lambda: open_directions_in_google_maps(p.directions_uri),
        )
        dir_btn.pack(fill="x", pady=(10, 0))
        add_hover_effect(dir_btn, GREEN_PRIMARY, GREEN_HOVER)

    def find_parking_live(self) -> None:
        if self.is_loading:
            return
        self.is_loading = True
        self.location_error = None
        radius = self._get_radius_meters()
        self.status_var.set("Fetching real-time device location via GPS / OS location services...")
        if self.active_view == "find":
            self._switch_view("find")

        def worker() -> None:
            loc, loc_err = detect_device_location()
            if loc_err or loc is None:
                self.root.after(0, lambda: self._on_find_error(loc_err or "Device location unavailable."))
                return

            self.root.after(
                0,
                lambda: self.status_var.set(
                    f"Location detected ({loc.display_name}). Searching nearby parking..."
                ),
            )
            parkings, park_err = fetch_google_nearby_parking(loc.latitude, loc.longitude, radius)
            self.root.after(0, lambda: self._on_find_complete(loc, parkings, park_err))

        threading.Thread(target=worker, daemon=True).start()

    def _on_find_error(self, msg: str) -> None:
        self.is_loading = False
        self.location_error = msg
        self.status_var.set(msg)
        if self.active_view == "find":
            self._switch_view("find")
        retry_now = messagebox.askretrycancel("Location Error", msg)
        if retry_now:
            self.find_parking_live()

    def _on_find_complete(
        self, loc: LocationResult, parkings: List[ParkingLocation], err: Optional[str]
    ) -> None:
        self.is_loading = False
        self.location_error = None
        self.current_location = loc

        if err:
            self.parkings = []
            self.selected_parking = None
            self.status_var.set(err)
            messagebox.showerror("Parking Search Error", err)
        else:
            self.parkings = parkings
            self.selected_parking = parkings[0] if parkings else None
            self.status_var.set(
                f"Found {len(parkings)} genuine English parking result(s) via Google Places API (New)."
            )
            generate_and_open_map(loc.latitude, loc.longitude, loc.display_name, parkings)

        if self.active_view == "find":
            self._switch_view("find")

    def _open_map(self) -> None:
        if self.current_location is None:
            messagebox.showinfo(
                "Location Required",
                "Click 'Find Parking' first to detect your device location.",
            )
            return
        generate_and_open_map(
            self.current_location.latitude,
            self.current_location.longitude,
            self.current_location.display_name,
            self.parkings,
        )

    # ==================== CHANGE PASSWORD ====================
    def _render_change_password_view(self) -> None:
        wrapper = self.body_frame
        wrapper.columnconfigure(0, weight=1)
        wrapper.rowconfigure(0, weight=1)

        card = tk.Frame(
            wrapper,
            bg=WHITE,
            padx=32,
            pady=28,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
        )
        card.grid(row=0, column=0)

        tk.Label(
            card,
            text="Change Password",
            font=("Segoe UI", 18, "bold"),
            fg=NAVY_DARK,
            bg=WHITE,
        ).pack(anchor="w")

        tk.Label(
            card,
            text="Update your account password stored in users.json",
            font=("Segoe UI", 9),
            fg=TEXT_MUTED,
            bg=WHITE,
        ).pack(anchor="w", pady=(2, 14))

        msg_label = tk.Label(
            card,
            text="",
            font=("Segoe UI", 9, "bold"),
            fg=RED_ERROR,
            bg=WHITE,
            wraplength=320,
            justify="left",
        )
        msg_label.pack(fill="x", pady=(0, 8))

        def make_field(label_text: str) -> tk.Entry:
            tk.Label(
                card,
                text=label_text,
                font=("Segoe UI", 10, "bold"),
                fg=NAVY_DARK,
                bg=WHITE,
                anchor="w",
            ).pack(fill="x")
            entry = tk.Entry(
                card,
                font=("Segoe UI", 11),
                bg=SLATE_LIGHT,
                fg=NAVY_DARK,
                relief="solid",
                bd=1,
                width=34,
                show="*",
            )
            entry.pack(fill="x", pady=(4, 12), ipady=5)
            return entry

        cur_entry = make_field("Current Password")
        new_entry = make_field("New Password")
        cfm_entry = make_field("Confirm New Password")

        def handle_update() -> None:
            username = (self.current_user or {}).get("username", "")
            ok, message = change_user_password(
                username,
                cur_entry.get(),
                new_entry.get(),
                cfm_entry.get(),
            )
            msg_label.configure(text=message, fg=GREEN_SUCCESS if ok else RED_ERROR)
            if ok:
                cur_entry.delete(0, tk.END)
                new_entry.delete(0, tk.END)
                cfm_entry.delete(0, tk.END)

        update_btn = tk.Button(
            card,
            text="Update Password",
            font=("Segoe UI", 11, "bold"),
            bg=GREEN_PRIMARY,
            fg=WHITE,
            relief="flat",
            pady=9,
            cursor="hand2",
            command=handle_update,
        )
        update_btn.pack(fill="x", pady=(6, 0))
        add_hover_effect(update_btn, GREEN_PRIMARY, GREEN_HOVER)


def main() -> None:
    root = tk.Tk()
    SmartParkingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
