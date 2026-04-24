import folium
import webbrowser

def show_map(df, user_lat, user_lon):
    m = folium.Map(location=[user_lat, user_lon], zoom_start=14)

    # User marker
    folium.Marker(
        [user_lat, user_lon],
        popup="Your Location",
        icon=folium.Icon(color="blue")
    ).add_to(m)

    # Parking markers
    for _, row in df.iterrows():
        folium.Marker(
            [row['latitude'], row['longitude']],
            popup=f"{row['name']} ({row['available_slots']} slots)",
            icon=folium.Icon(color="green" if row['available_slots'] > 5 else "red")
        ).add_to(m)

    file_path = "map.html"
    m.save(file_path)
    webbrowser.open(file_path)