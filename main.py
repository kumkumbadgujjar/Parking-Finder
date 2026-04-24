import tkinter as tk
from tkinter import messagebox, simpledialog
import json, os, random, hashlib, math
import smtplib
from email.mime.text import MIMEText
from geopy.geocoders import Nominatim
import requests
import http.server, socketserver, urllib.parse, threading
import webbrowser

# ================= EMAIL CONFIG =================
EMAIL = "your_email@gmail.com"
APP_PASSWORD = "your_app_password"

# ================= OTP =================
def send_otp(email, otp):
    try:
        msg = MIMEText(f"Your OTP is: {otp}")
        msg['Subject'] = "Parking Finder OTP"
        msg['From'] = EMAIL
        msg['To'] = email

        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(EMAIL, APP_PASSWORD)
        server.send_message(msg)
        server.quit()
    except:
        messagebox.showinfo("OTP (Demo Mode)", f"Your OTP is: {otp}")

# ================= AUTH =================
if not os.path.exists("users.json"):
    json.dump({"users": []}, open("users.json", "w"))

def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

def load_users():
    return json.load(open("users.json"))

def save_users(data):
    json.dump(data, open("users.json", "w"), indent=4)

def user_exists(u):
    return any(x["username"] == u for x in load_users()["users"])

def register(u, p, e):
    data = load_users()
    data["users"].append({
        "username": u,
        "password": hash_password(p),
        "email": e
    })
    save_users(data)

def login_check(u, p):
    for user in load_users()["users"]:
        if user["username"] == u and user["password"] in [p, hash_password(p)]:
            return user
    return None

# ================= HAVERSINE DISTANCE (KM) =================
def distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2)

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# ================= BASIC LOCATION =================
def get_current_location():
    return "Faridabad, Haryana, India"

# ================= GPS SERVER =================
PORT = 8000

def start_location_server(callback):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            params = urllib.parse.parse_qs(
                urllib.parse.urlparse(self.path).query
            )

            if "lat" in params and "lon" in params:
                lat = float(params["lat"][0])
                lon = float(params["lon"][0])

                geo = Nominatim(user_agent="parking_app")
                location = geo.reverse((lat, lon), language='en')

                if location:
                    callback(location.address)

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Location received")

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()

# ================= SMART PARKING =================
def get_parking_list(location):
    geo = Nominatim(user_agent="parking_app")
    loc = geo.geocode(location)

    if not loc:
        return []

    lat, lon = loc.latitude, loc.longitude
    parkings = []

    # ===== TRY REAL API =====
    try:
        url = "https://overpass-api.de/api/interpreter"
        query = f"""
        [out:json];
        node["amenity"="parking"](around:1500,{lat},{lon});
        out;
        """

        res = requests.get(url, params={'data': query}, timeout=10)
        data = res.json()

        for el in data.get('elements', []):
            name = el.get('tags', {}).get('name', 'Parking')
            dist = distance(lat, lon, el['lat'], el['lon'])

            parkings.append({
                "name": name,
                "distance": dist,
                "slots": random.randint(5, 50)
            })

    except:
        pass

    # ===== DYNAMIC AI-LIKE FALLBACK =====
    if len(parkings) < 3:
        names = ["Smart Parking", "City Parking", "Mall Parking",
                 "Metro Parking", "Public Parking"]

        for i in range(5):
            new_lat = lat + random.uniform(-0.01, 0.01)
            new_lon = lon + random.uniform(-0.01, 0.01)

            parkings.append({
                "name": random.choice(names) + f" {i+1}",
                "distance": distance(lat, lon, new_lat, new_lon),
                "slots": random.randint(10, 60)
            })

    # ===== SMART RANKING =====
    parkings.sort(key=lambda x: (x["distance"], -x["slots"]))

    return parkings[:5]

# ================= UI =================
def clear():
    for w in root.winfo_children():
        w.destroy()

# ================= MAIN =================
def main_app():
    clear()

    tk.Label(root, text="🚗 Smart Parking Finder",
             font=("Arial", 22, "bold")).pack(pady=20)

    tk.Label(root, text="Enter Location").pack()
    loc_entry = tk.Entry(root, width=40)
    loc_entry.pack(pady=10)

    result_box = tk.Text(root, height=14, width=60)
    result_box.pack(pady=10)

    def search():
        location = loc_entry.get()
        if not location:
            messagebox.showerror("Error", "Enter location")
            return

        result_box.delete("1.0", tk.END)
        parkings = get_parking_list(location)

        for i, p in enumerate(parkings, start=1):
            result_box.insert(tk.END,
                f"{i}. {p['name']}\n"
                f"   📏 Distance: {p['distance']:.2f} km\n"
                f"   🅿 Slots: {p['slots']}\n\n"
            )

    def auto_loc_basic():
        loc_entry.delete(0, tk.END)
        loc_entry.insert(0, get_current_location())

    def auto_loc_advanced():
        def update_location(address):
            loc_entry.delete(0, tk.END)
            loc_entry.insert(0, address)

        threading.Thread(
            target=start_location_server,
            args=(update_location,),
            daemon=True
        ).start()

        webbrowser.open("location.html")

    tk.Button(root, text="Search Parking", command=search,
              bg="green", fg="white").pack(pady=5)

    tk.Button(root, text="Use Basic Location",
              command=auto_loc_basic,
              bg="orange", fg="white").pack(pady=5)

    tk.Button(root, text="Use Exact Current Location 📍",
              command=auto_loc_advanced,
              bg="blue", fg="white").pack(pady=5)

# ================= LOGIN =================
def login_screen():
    clear()

    tk.Label(root, text="Login", font=("Arial", 20, "bold")).pack(pady=20)

    tk.Label(root, text="Enter Username").pack()
    user = tk.Entry(root)
    user.pack()

    tk.Label(root, text="Enter Password").pack()
    pwd = tk.Entry(root, show="*")
    pwd.pack()

    def login():
        user_data = login_check(user.get(), pwd.get())

        if user_data:
            otp = str(random.randint(1000, 9999))
            send_otp(user_data["email"], otp)

            entered = simpledialog.askstring("OTP", "Enter OTP")

            if entered == otp:
                main_app()
            else:
                messagebox.showerror("Error", "Wrong OTP")
        else:
            messagebox.showerror("Error", "Invalid Credentials")

    tk.Button(root, text="Login", command=login).pack(pady=10)
    tk.Button(root, text="Signup", command=signup_screen).pack()

# ================= SIGNUP =================
def signup_screen():
    clear()

    tk.Label(root, text="Signup", font=("Arial", 20, "bold")).pack(pady=20)

    tk.Label(root, text="Enter Username").pack()
    user = tk.Entry(root)
    user.pack()

    tk.Label(root, text="Enter Email").pack()
    email = tk.Entry(root)
    email.pack()

    tk.Label(root, text="Enter Password").pack()
    pwd = tk.Entry(root, show="*")
    pwd.pack()

    def signup():
        if user_exists(user.get()):
            messagebox.showerror("Error", "User exists")
        else:
            otp = str(random.randint(1000, 9999))
            send_otp(email.get(), otp)

            entered = simpledialog.askstring("OTP", "Enter OTP")

            if entered == otp:
                register(user.get(), pwd.get(), email.get())
                login_screen()
            else:
                messagebox.showerror("Error", "Wrong OTP")

    tk.Button(root, text="Create Account", command=signup).pack(pady=10)

# ================= START =================
root = tk.Tk()
root.geometry("600x600")
login_screen()
root.mainloop()