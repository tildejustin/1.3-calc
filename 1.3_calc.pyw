import json
import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk
from typing import IO, Optional, Tuple, Any, List, Dict, Union

import win32gui
import win32process
current_dir: Optional[str] = None
config_file = os.path.join(os.curdir, "1.3_calc.json")
new_dir: str
current_logs: Optional[IO] = None
invalid_biome_stronghold = re.compile(r"^Placed stronghold in INVALID biome at \(-?(\d+), (-?\d+)\)$")
proximity_stronghold = re.compile(r"^(-?\d+), (-?\d+)$")
strongholds: List[Optional[Tuple[int, int]]] = [None for _ in range(3)]
worker_thread = None


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
        sh_text.set("unknown" if not sh else f"{sh[0] * 16 + 4}, {sh[1] * 16 + 4}")


def clear_strongholds():
    for j, _ in enumerate(strongholds):
        strongholds.__setitem__(j, None)
    update_stronghold_strings()


def loop() -> None:
    global new_dir, current_dir, current_logs
    hwnd = win32gui.GetForegroundWindow()
    pid = win32process.GetWindowThreadProcessId(hwnd)[1]
    new_dir = check_dir(pid, config.get("instance"))
    print(new_dir)
    if new_dir is not None and new_dir != current_dir:
        set_window_name(win32gui.GetWindowText(hwnd), pid)
        current_dir = new_dir
        error.set("")
        clear_strongholds()
        if os.path.exists(new_dir + "/.minecraft/logs/latest.log"):
            if current_logs:
                current_logs.close()
            current_logs = open(current_dir + "/.minecraft/logs/latest.log", "r")
        else:
            error.set("no logs, make sure you are using the wrapper script")
            current_logs = None
    if current_logs is not None:
        while (line := current_logs.readline()) != "":
            if line == "Scanning folders...\n":
                clear_strongholds()
                continue
            else:
                result = match_line(line, [invalid_biome_stronghold, proximity_stronghold])
            if result is not None:
                add_stronghold(result)


def loop_thread():
    global worker_thread
    if worker_thread:
        worker_thread.join()
    worker_thread = threading.Thread(target=loop)
    worker_thread.start()
    root.after(config.get("delay"), loop_thread)


def match_line(line: str, patterns: List[re.Pattern]):
    for pattern in patterns:
        if (result := pattern.match(line)) is not None:
            return tuple(map(int, result.groups()))


def check_dir(pid: int, inst_dir: str) -> Optional[str]:
    # Thanks to the creator of MoveWorlds-v0.3.ahk (probably specnr)
    cmd = f'powershell.exe "$proc = Get-WmiObject Win32_Process -Filter \\"ProcessId = {str(pid)}\\";$proc.CommandLine"'
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
    response = p.communicate()[0].decode()
    # print(pid, inst_dir, response)
    if inst_dir in response:
        start = response.index(inst_dir)
        end = response.index(r"/", start + len(inst_dir) + 1)
        return response[start:end]
    return None


def set_window_name(name: str, pid: Any) -> None:
    window_name.set(f"window: {name} ({pid})")


def get_config() -> dict[str, Union[str, int]]:
    if not os.path.exists(config_file):
        with open(config_file, "w") as file:
            json.dump({"instance": r"C:\Users\justi\Documents\Programs\MultiMC\instances", "delay": 2000}, file, indent=2)
    with open(config_file, "r") as file:
        config: dict = json.load(file)
        config.__setitem__("instance", config.get("instance").replace("\\", "/"))
        if os.path.exists(config.get("instance")):
            print(f"instance dir is {config.get('instance')}, delay is {config.get('delay')}")
            return config
        error.set(f"{config.get('instance')} not found, please change it in {config_file}")


if __name__ == "__main__":
    root: tk.Tk = tk.Tk()
    root.wm_attributes("-topmost", 1)
    root.title("1.3 calc")
    root.tk.call("tk", "scaling", 2)
    try:
        # noinspection PyUnresolvedReferences
        from ctypes import windll
    except ImportError:
        pass
    else:
        windll.shcore.SetProcessDpiAwareness(1)
    error = tk.StringVar()
    config = get_config()
    window_name = tk.StringVar()
    stronghold_text = [tk.StringVar() for _ in range(3)]
    update_stronghold_strings()
    set_window_name("unknown", "none")
    ttk.Label(root, textvariable=window_name).grid(row=0, column=0, columnspan=3)
    for i, _ in enumerate(stronghold_text):
        ttk.Label(root, text=f"sh {i + 1}:").grid(row=1, column=i)
    for num, stronghold in enumerate(stronghold_text):
        ttk.Label(root, textvariable=stronghold).grid(row=2, column=num)
    ttk.Label(root, textvariable=error).grid(row=3, column=0, columnspan=3)
    # make this threaded
    if not error.get():
        root.after(1, loop_thread)
    root.mainloop()
