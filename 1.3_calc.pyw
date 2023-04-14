import re
import tkinter as tk
from tkinter import ttk
from typing import IO, Optional, Tuple

import win32gui
import win32process

from utils import *

instance_dir: str = r"C:\Users\justi\Documents\Programs\MultiMC\instances"
instance_dir = instance_dir.replace("\\", "/")
current_dir: Optional[str] = None
new_dir: str
current_logs: Optional[IO] = None
invalid_biome_stronghold = re.compile(r"^Placed stronghold in INVALID biome at \(-?(\d+), (-?\d+)\)$")
proximity_stronghold = re.compile(r"^(-?\d+), (-?\d+)$")
strongholds: List[Optional[Tuple[int, int]]] = [None for _ in range(3)]


def add_stronghold(coords):
    for j, current_coord in enumerate(strongholds):
        if current_coord == coords:
            break
        elif current_coord is None:
            strongholds.__setitem__(j, coords)
            update_stronghold_strings()
            break


def update_stronghold_strings():
    for sh, sh_text in zip(strongholds, stronghold_text):
        sh_text.set("unknown" if not sh else f"{sh[0]*16+4}, {sh[1]*16+4}")


def clear_strongholds():
    for j, _ in enumerate(strongholds):
        strongholds.__setitem__(j, None)
    update_stronghold_strings()


def loop() -> None:
    global new_dir, current_dir, current_logs
    hwnd = win32gui.GetForegroundWindow()
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    new_dir = check_dir(pid, instance_dir)
    if new_dir is not None and new_dir != current_dir:
        if os.path.exists(new_dir + "/.minecraft/logs/latest.log"):
            current_dir = new_dir
            if current_logs:
                current_logs.close()
            current_logs = open(current_dir + "/.minecraft/logs/latest.log", "r")
        else:
            print("no logs, make sure you are using the wrapper script")
            root.after(5000, loop)
            return
    if current_logs is not None:
        while (line := current_logs.readline()) != "":
            if line == "Scanning folders...\n":
                print("resetting")
                clear_strongholds()
                continue
            else:
                result = match_line(line, [invalid_biome_stronghold, proximity_stronghold])
                print(result, line)

            if result is not None:
                add_stronghold(result)
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
    ttk.Label(root, text=f"sh {i+1}:").grid(row=1, column=i)
for num, stronghold in enumerate(stronghold_text):
    tk.Label(root, textvariable=stronghold).grid(row=2, column=num)
# make this threaded
root.after(0, loop)
root.mainloop()
