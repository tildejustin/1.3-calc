import json
import math
import multiprocessing
import os
import re
import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk
from typing import IO, Optional, Tuple, Any, List, Union

import win32gui
import win32process

invalid_biome_stronghold = re.compile(r"^Placed stronghold in INVALID biome at \((-?\d+), (-?\d+)\)$")
proximity_stronghold = re.compile(r"^(-?\d+), (-?\d+)$")


def update_strings(string_arr: list[tk.StringVar], values: list[str]):
    assert len(string_arr) == len(values)
    for string, value in zip(string_arr, values):
        string.set(value)


strongholds: List[Tuple[int, int]] = []


def file_thread() -> None:
    strongholds.clear()
    lines: list[str] = ["", "", ""]
    if current_logs is not None:
        while True:
            updated = False
            lines.pop(0)
            lines.append(current_logs.readline())
            if lines[-1] == "Scanning folders...\n":
                strongholds.clear()
                updated = True
            else:
                result = match_line(lines[-1], [invalid_biome_stronghold, proximity_stronghold])
                if result is not None:
                    # add_stronghold(result)
                    coords = (result[0] * 16 + 4, result[1] * 16 + 4)
                    if coords not in strongholds:
                        strongholds.append(coords)
                        updated = True
            if updated:
                set_text(stronghold_text, guess_strongholds(strongholds), len(strongholds))
                print(strongholds)
                print(guess_strongholds(strongholds))
            time.sleep(0.01)


def set_text(text: list[tk.StringVar], values: list[tuple[int, int]], guesses: int):
    pass


def match_line(line: str, patterns: List[re.Pattern]):
    for pattern in patterns:
        if (result := pattern.match(line)) is not None:
            return tuple(map(int, result.groups()))


# noinspection SpellCheckingInspection
def get_directory(pid: int, inst_dir: str) -> Optional[str]:
    # adapted from easy-multi
    cmd = f'powershell.exe "$proc = Get-WmiObject Win32_Process -Filter \\"ProcessId = {str(pid)}\\";$proc.CommandLine"'
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
    response = p.communicate()[0].decode()
    # print(pid, inst_dir, response)
    if inst_dir in response:
        start = response.index(inst_dir)
        end = response.index(r"/", start + len(inst_dir) + 1)
        return response[start:end]
    return None


cx = 7
cy = 84
r = 896  # (1152-640)/2+640


def get_pos_from_angle(angle: float) -> tuple[int, int]:
    # parametric equation of a circle
    x = cx + r * math.cos(math.degrees(angle))
    y = cy + r * math.sin(math.degrees(angle))
    return round(x), round(y)


def guess_strongholds(known_strongholds: list[tuple[int, int]]) -> list[tuple[int, int]]:
    assert len(known_strongholds) <= 3
    if len(known_strongholds) == 3:
        return known_strongholds
    if len(known_strongholds) == 2:
        angle1 = math.atan2(known_strongholds[0][0] - cx, known_strongholds[0][1] - cy) % (2 * math.pi)
        angle2 = math.atan2(known_strongholds[1][0] - cx, known_strongholds[1][1] - cy) % (2 * math.pi)
        known_angles = [angle1, angle2]
        angle3 = (max(known_angles) - min(known_angles)) / 2 + min(known_angles)
        difference = abs(angle1 - angle2)
        if difference < math.pi:
            angle3 = angle3 + math.pi % (2 * math.pi)
        pos3 = get_pos_from_angle(angle3)
        return known_strongholds + [pos3]
        pass
    if len(known_strongholds) == 1:
        angle1 = math.atan2(known_strongholds[0][0] - cx, known_strongholds[0][1] - cy)
        angle2 = (angle1 + (2 * math.pi / 3)) % (2 * math.pi)
        angle3 = (angle1 + (4 * math.pi / 3)) % (2 * math.pi)
        pos2 = get_pos_from_angle(angle2)
        pos3 = get_pos_from_angle(angle3)
        return known_strongholds + [pos2, pos3]


current_dir: str = ""
current_logs: IO = None
worker_thread: threading.Thread = None


def loop():
    global current_dir, current_logs, worker_thread
    hwnd = win32gui.GetForegroundWindow()
    pid = win32process.GetWindowThreadProcessId(hwnd)[1]
    new_directory = get_directory(pid, instance_directory)
    if new_directory is not None and new_directory != current_dir:
        set_window_name(window_name, win32gui.GetWindowText(hwnd), pid)
        current_dir = new_directory
        error.set("")
        if os.path.exists(new_directory + "/.minecraft/logs/latest.log"):
            if current_logs:
                current_logs.close()
            current_logs = open(current_dir + "/.minecraft/logs/latest.log", "r")
            # only deploy a new thread when the instance is switched
            # if worker_thread:
            #     process.kill()
            # worker_thread = threading.Thread(target=file_thread, daemon=True)
            # worker_thread.start()
            file_thread()
        else:
            error.set("no logs, make sure you are using the wrapper script")
            current_logs = None
    root.after(interval, loop)


root: tk.Tk
error: tk.StringVar
interval: int
instance_directory: str
window_name: tk.StringVar
stronghold_text: list[tk.StringVar]


def main():
    global root, error, interval, instance_directory, window_name, stronghold_text


def get_config(error_string) -> dict[str, Union[str, int]]:
    config_file = os.path.join(os.curdir, "1.3_calc.json")
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
        error_string.set(f"{config_local.get('instance')} not found, please change it in {config_file}")


def set_window_name(string_var: tk.StringVar, name: str, pid: Any) -> None:
    string_var.set(f"window: {name} ({pid})")


if __name__ == "__main__":
    main()
