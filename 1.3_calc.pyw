import json
import math
import os
import re
import subprocess
import threading
import tkinter as tk
from tkinter import ttk
from typing import IO, Optional, Tuple, Any, List, Union

import win32gui
import win32process

current_dir: Optional[str] = None
config_file = os.path.join(os.curdir, "1.3_calc.json")
new_dir: str
current_logs: Optional[IO] = None
invalid_biome_stronghold = re.compile(r"^Placed stronghold in INVALID biome at \((-?\d+), (-?\d+)\)$")
proximity_stronghold = re.compile(r"^(-?\d+), (-?\d+)$")
strongholds: List[Optional[Tuple[int, int]]] = [None for _ in range(3)]
worker_thread = None
strongholds_with_guesses: List[Optional[Tuple[int, int]]] = [None for _ in range(3)]


# noinspection SpellCheckingInspection
def add_stronghold(coords):
    coords = (coords[0] * 16 + 4, coords[1] * 16 + 4)
    for j, current_coord in enumerate(strongholds):
        if current_coord == coords:
            break
        elif current_coord is None:
            strongholds.__setitem__(j, coords)
            break


def update_stronghold_strings():
    guess_sh_location()
    print(strongholds)
    print(strongholds_with_guesses)
    for sh, sh_guess, sh_text in zip(strongholds, strongholds_with_guesses, stronghold_text):
        if sh is not None:
            sh_text.set(f"{sh[0]}, {sh[1]}")
        elif sh_guess is not None:
            sh_text.set(f"guess: {sh_guess[0]}, {sh_guess[1]}")
        else:
            sh_text.set("unknown")


def clear_strongholds():
    # TODO: merge these
    for j, _ in enumerate(strongholds):
        strongholds.__setitem__(j, None)
    for j, _ in enumerate(strongholds_with_guesses):
        strongholds_with_guesses.__setitem__(j, None)


# TODO: make only what needs to be threaded, threaded
def loop() -> None:
    global new_dir, current_dir, current_logs
    hwnd = win32gui.GetForegroundWindow()
    pid = win32process.GetWindowThreadProcessId(hwnd)[1]
    new_dir = check_dir(pid, config.get("instance"))
    should_update = False
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
                should_update = True
                continue
            else:
                result = match_line(line, [invalid_biome_stronghold, proximity_stronghold])
            if result is not None:
                add_stronghold(result)
                should_update = True
    if should_update:
        update_stronghold_strings()


def loop_thread():
    global worker_thread
    # if worker_thread:
    #     worker_thread.join()
    worker_thread = threading.Thread(target=loop)
    worker_thread.start()
    root.after(config.get("delay"), loop_thread)


def match_line(line: str, patterns: List[re.Pattern]):
    for pattern in patterns:
        if (result := pattern.match(line)) is not None:
            return tuple(map(int, result.groups()))


# noinspection SpellCheckingInspection
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


cx = 7
cy = 84
r = 896  # (1152-640)/2+640


def get_pos_from_angle(angle: float) -> tuple[int, int]:
    x = cx + r * math.sin(angle)
    y = cy + r * math.cos(angle)
    return int(x), int(y)


def guess_sh_location():
    global strongholds_with_guesses
    known = list(filter(lambda x: x is not None, strongholds))
    if len(known) == 3:
        strongholds_with_guesses = strongholds
    if len(known) == 2:
        # run on both, avg answer
        angle1 = math.atan2(known[0][0] - cx, known[0][1] - cy) % (2 * math.pi)
        angle2 = math.atan2(known[1][0] - cx, known[1][1] - cy) % (2 * math.pi)
        known_angles = [angle1, angle2]
        angle3 = (max(known_angles) - min(known_angles)) / 2 + min(known_angles)
        known_diff = abs(angle1 - angle2)
        print(known_diff)
        print(angle3)
        if known_diff < math.pi:
            angle3 = angle3 + math.pi % (2 * math.pi)
        print(known_angles)
        print(angle3)
        pos3 = get_pos_from_angle(angle3)
        strongholds_with_guesses = known
        strongholds_with_guesses.append(pos3)
        pass
    if len(known) == 1:
        angle1 = math.atan2(known[0][0] - cx, known[0][1] - cy)
        angle2 = (angle1 + (2 * math.pi / 3)) % (2 * math.pi)
        angle3 = (angle1 + (4 * math.pi / 3)) % (2 * math.pi)
        print(angle1, angle2, angle3)
        pos2 = get_pos_from_angle(angle2)
        pos3 = get_pos_from_angle(angle3)
        print(known[0], get_pos_from_angle(angle1))
        strongholds_with_guesses = known
        strongholds_with_guesses.extend([pos2, pos3])


def get_config() -> dict[str, Union[str, int]]:
    if not os.path.exists(config_file):
        with open(config_file, "w") as file:
            # noinspection SpellCheckingInspection
            json.dump(
                {
                    "instance": r"C:\Users\justi\Documents\Programs\MultiMC\instances",
                    "delay": 2000
                },
                file,
                indent=2
            )
    with open(config_file, "r") as file:
        config_local: dict = json.load(file)
        config_local.__setitem__("instance", config_local.get("instance").replace("\\", "/"))
        if os.path.exists(config_local.get("instance")):
            print(f"instance dir is {config_local.get('instance')}, delay is {config_local.get('delay')}")
            return config_local
        error.set(f"{config_local.get('instance')} not found, please change it in {config_file}")


if __name__ == "__main__":
    root: tk.Tk = tk.Tk()
    root.wm_attributes("-topmost", 1)
    root.title("1.3 calc")
    # root.tk.call("tk", "scaling", 2)
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
    ttk.Label(root, textvariable=window_name, font=("Ariel", 10)).grid(row=0, column=0, columnspan=3)
    for i, _ in enumerate(stronghold_text):
        ttk.Label(root, text=f"sh {i + 1}:", font=("Ariel", 10)).grid(row=1, column=i)
    for num, stronghold in enumerate(stronghold_text):
        ttk.Label(root, textvariable=stronghold, font=("Ariel", 10)).grid(row=2, column=num)
    ttk.Label(root, textvariable=error, font=("Ariel", 10)).grid(row=3, column=0, columnspan=3)
    root.after(1, loop_thread)
    if not error.get():
        root.mainloop()
