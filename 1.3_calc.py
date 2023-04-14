import fileinput
import tkinter as tk
from tkinter import ttk
from typing import IO

import win32gui
import win32process

from utils import *

instance_dir: str = r"C:\Users\justi\Documents\Programs\MultiMC\instances"
instance_dir = instance_dir.replace("\\", "/")
current_dir: str
new_dir: str
current_logs: IO


def loop() -> None:
    global new_dir, current_dir, current_logs
    hwnd = win32gui.GetForegroundWindow()
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    if new_dir := check_dir(pid, instance_dir) is not None and new_dir != current_dir:
        current_dir = new_dir
        current_logs = open(current_dir + "/logs/latest.txt", "r")
        while current_logs.
    if current_logs is not None:

    root.after(1000, loop)


root: tk.Tk = tk.Tk()
root.wm_attributes("-topmost", 1)
root.title("1.3 calc")
root.geometry("210x180")

window_name = tk.StringVar()
window_name.set("window:")
stronghold_text = [tk.StringVar() for _ in range(3)]
ttk.Label(root, textvariable=window_name).grid(row=0, column=0, columnspan=3)
for i, _ in enumerate(stronghold_text):
    ttk.Label(root, text=f"sh {i}:").grid(row=1, column=i)
for num, stronghold in enumerate(stronghold_text):
    tk.Label(root, textvariable=stronghold).grid(row=num, column=2)
root.after(0, loop)
root.mainloop()

