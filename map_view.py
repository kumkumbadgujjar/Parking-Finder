"""
map_view.py
Plots exact coordinates returned by Google Places API (New) and opens
Google Maps directions in the user's default browser.
Never generates random coordinates.
"""

import html
import os
import webbrowser
from typing import List

import folium

from parking_service import ParkingLocation

MAP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "map.html")


def generate_and_open_map(
    center_lat: float,
    center_lon: float,
    location_label: str,
    parkings: List[ParkingLocation],
) -> str:
    """Plot user's current location and exact Google Places parking markers, then open map."""
    parking_map = folium.Map(location=[center_lat, center_lon], zoom_start=15)

    # User's current location marker (blue)
    folium.Marker(
        location=[center_lat, center_lon],
        popup=folium.Popup(
            f"<b>Your Location</b><br>{html.escape(location_label)}<br>"
            f"Lat: {center_lat:.5f}, Lon: {center_lon:.5f}",
            max_width=280,
        ),
        tooltip="Your Location",
        icon=folium.Icon(color="blue", icon="user", prefix="fa"),
    ).add_to(parking_map)

    # Exact Google Places API parking markers (green)
    for p in parkings:
        popup_html = (
            f"<div style='font-family: Arial, sans-serif; min-width: 220px;'>"
            f"<b>{html.escape(p.name)}</b><br>"
            f"<b>Address:</b> {html.escape(p.address)}<br>"
            f"<b>Distance:</b> {p.distance_km:.2f} km<br>"
            f"<b>Place ID:</b> {html.escape(p.place_id)}<br>"
            f"<b>Status:</b> {html.escape(p.availability_status)}<br>"
            f"<a href='{html.escape(p.directions_uri)}' target='_blank'>Open Google Maps Directions</a>"
            f"</div>"
        )
        folium.Marker(
            location=[p.latitude, p.longitude],
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=f"{p.name} ({p.distance_km:.2f} km)",
            icon=folium.Icon(color="green", icon="car", prefix="fa"),
        ).add_to(parking_map)

    parking_map.save(MAP_FILE)
    webbrowser.open(f"file://{MAP_FILE}")
    return MAP_FILE


def open_directions_in_google_maps(directions_uri: str) -> None:
    """Open the exact Google Maps directions URL in the default browser."""
    webbrowser.open(directions_uri)
