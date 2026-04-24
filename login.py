import tkinter as tk
from tkinter import messagebox, simpledialog
import json, random
from email.mime.text import MIMEText
import smtplib

# ================= EMAIL CONFIG =================
EMAIL = "your_email@gmail.com"
APP_PASSWORD = "your_app_password"

def send_otp(email, otp):
    try:
        msg = MIMEText(f"Your OTP is: {otp}")
        msg['Subject'] = "Login OTP"
        msg['From'] = EMAIL
        msg['To'] = email

        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(EMAIL, APP_PASSWORD)
        server.send_message(msg)
        server.quit()
    except:
        messagebox.showerror("Error", "OTP sending failed")

# ================= AUTH =================
def get_user(username, password):
    with open("users.json", "r") as f:
        data = json.load(f)
        for user in data["users"]:
            if user["username"] == username and user["password"] == password:
                return user
    return None

# ================= LOGIN SCREEN =================
def login_screen(root, on_success):
    frame = tk.Frame(root, bg="#1e1e2f")
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text="Login",
             font=("Arial", 18, "bold"),
             bg="#1e1e2f", fg="white").pack(pady=20)

    tk.Label(frame, text="Enter Username", bg="#1e1e2f", fg="white").pack()
    username_entry = tk.Entry(frame)
    username_entry.pack(pady=5)

    tk.Label(frame, text="Enter Password", bg="#1e1e2f", fg="white").pack()
    password_entry = tk.Entry(frame, show="*")
    password_entry.pack(pady=5)

    def login():
        user = username_entry.get()
        pwd = password_entry.get()

        user_data = get_user(user, pwd)

        if user_data:
            # 🔥 Generate OTP
            otp = str(random.randint(1000, 9999))

            # 🔥 Send OTP to user's email
            send_otp(user_data["email"], otp)

            # 🔥 Ask user to enter OTP
            entered = simpledialog.askstring("OTP", "Enter OTP sent to your email")

            if entered == otp:
                messagebox.showinfo("Success", "Login Successful")
                frame.destroy()
                on_success()
            else:
                messagebox.showerror("Error", "Wrong OTP")

        else:
            messagebox.showerror("Error", "Invalid Credentials")

    tk.Button(frame, text="Login", command=login,
              bg="#4CAF50", fg="white").pack(pady=20)