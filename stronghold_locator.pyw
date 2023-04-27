import dataclasses
import enum
import re
import subprocess
import threading
import time
import typing
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from typing import Optional

import win32gui
import win32process


class Config:
    instance_dir: Path
    font_size: int
    interval: int

    def __init__(self, instance_dir: str, font_size=10, interval=1000):
        self.instance_dir = Path(instance_dir)
        self.font_size = font_size
        self.interval = interval


# TODO: reimplement this
# noinspection SpellCheckingInspection
def get_config() -> Config:
    return Config(r"C:\Users\justi\Documents\Programs\MultiMC\instances", font_size=12, interval=2500)


class Window(tk.Tk):
    config: Config
    window_name: tk.StringVar
    logs: dict[str]
    locator: typing.Any

    def __init__(self):
        super().__init__()

        self.config = get_config()
        self.create_widgets()
        if self.config.instance_dir.exists():
            self.after(1, self.loop)
            self.mainloop()
        # else: alert

    def create_widgets(self):
        self.wm_attributes("-topmost", 1)
        self.title("1.3 stronghold locator")
        # uncomment this for double size widgets
        # root.tk.call("tk", "scaling", 2)
        try:
            # noinspection PyUnresolvedReferences
            from ctypes import windll
        except ImportError:
            pass
        else:
            # scaling fix for my laptop
            windll.shcore.SetProcessDpiAwareness(1)
        self.window_name = tk.StringVar()
        #  = [tk.StringVar(value="unknown") for _ in range(3)]
        ttk.Label(self, textvariable=self.window_name, font=("", self.config.font_size)).grid(row=0, column=0,
                                                                                              columnspan=3, padx=5,
                                                                                              pady=5)

        stronghold_text = [ttk.Label(self, text="unknown", font=("", self.config.font_size)) for _ in range(3)]
        for i, sh_text in enumerate(stronghold_text):
            sh_text.grid(row=2, column=i, padx=5, pady=5)
        self.locator = Locator(stronghold_text, str(self.config.instance_dir), self.window_name)

    def loop(self):
        threading.Thread(target=self.locator.check_window).start()
        self.after(self.config.interval, self.loop)


class StrongholdSource(enum.StrEnum):
    invalid = "blue"
    proximity = "green"
    guess = "red"


@dataclasses.dataclass
class Stronghold:
    x: int
    y: int
    source: str

    def get_coords(self) -> tuple[int, int]:
        return self.x * 16 + 4, self.y * 16 + 4

    def __str__(self):
        return ", ".join(map(str, self.get_coords()))


@dataclasses.dataclass
class StrongholdRing:
    center_x = 7
    center_y = 84
    radius = 896  # (1152-640)/2+640, probably mostly correct
    known_strongholds: list[Stronghold] = dataclasses.field(default_factory=list)

    def guess_strongholds(self) -> list[Stronghold]:
        if len(self.known_strongholds) == 3:
            return []
        if len(self.known_strongholds) == 2:
            return []
        if len(self.known_strongholds) == 1:
            return []
        if len(self.known_strongholds) == 0:
            return []

    def add_stronghold(self, coords: tuple[int, int], source: StrongholdSource):
        stronghold = Stronghold(coords[0], coords[1], source)
        if not self.has_stronghold(stronghold):
            self.known_strongholds.append(stronghold)

    def has_stronghold(self, stronghold: Stronghold) -> bool:
        return len(list(filter(lambda sh: sh.x == stronghold.x and sh.y == stronghold.y, self.known_strongholds))) == 1


def get_focus_handles() -> tuple[int, int]:
    hwnd = win32gui.GetForegroundWindow()
    pid = win32process.GetWindowThreadProcessId(hwnd)[1]
    return hwnd, pid


class Locator:
    ring: StrongholdRing
    logs: dict[Path, typing.IO] = dict()
    current_logs: Path = None
    instance_dir: str
    stronghold_text: list[ttk.Label]
    window_name = tk.StringVar
    invalid_biome_stronghold: re.Pattern = re.compile(r"^Placed stronghold in INVALID biome at \((-?\d+), (-?\d+)\)$")
    proximity_stronghold: re.Pattern = re.compile(r"^(-?\d+), (-?\d+)$")

    def __init__(self, stronghold_text: list[ttk.Label], instance_dir: str, window_name: tk.StringVar):
        self.stronghold_text = stronghold_text
        self.instance_dir = instance_dir.replace("\\", "/")
        self.window_name = window_name
        self.set_window_name("unknown", None)

    def set_window_name(self, name: str, pid: Optional[int]) -> None:
        self.window_name.set(f"window: {name} ({'unknown' if pid is None else pid})")

    def check_window(self):
        hwnd, pid = get_focus_handles()
        new_logs = self.get_logs(self.get_directory(pid))
        if new_logs:
            if str(new_logs) not in self.logs:
                self.logs.__setitem__(new_logs, new_logs.open())
            if new_logs != self.current_logs:
                print("new logs")
                self.current_logs = new_logs
                self.set_window_name(win32gui.GetWindowText(hwnd), pid)
                threading.Thread(target=lambda: self.thread(self.logs.get(self.current_logs))).start()

    def get_directory(self, pid: int) -> Optional[Path]:
        # ~~stolen~~ adapted from easy-multi
        cmd = f'powershell.exe "$proc = Get-WmiObject Win32_Process -Filter \\"ProcessId = {str(pid)}\\";$proc.CommandLine"'
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        response = p.communicate()[0].decode()
        # print(pid, self.instance_dir, response)
        if self.instance_dir in response:
            start = response.index(self.instance_dir)
            end = response.index(r"/", start + len(self.instance_dir) + 1)
            return Path(response[start:end])
        return None

    def get_logs(self, instance_dir: Optional[Path]) -> Optional[Path]:
        if instance_dir is None:
            return None
        logs = instance_dir.joinpath(".minecraft/logs/latest.log")
        if not logs.exists():
            return None
        return logs

    # noinspection PyTypeChecker
    def thread(self, log_file: typing.IO):
        while True:
            line = log_file.readline()
            if not line.__contains__("\n"):
                time.sleep(1)
                continue
            if line == "Scanning folders...\n":
                self.ring = StrongholdRing()
                self.update_text()
            # there has got to be a cleaner way to do this
            source = None
            match = self.invalid_biome_stronghold.match(line)
            if match:
                source = StrongholdSource.invalid
            else:
                match = self.proximity_stronghold.match(line)
                if match:
                    source = StrongholdSource.proximity
            if match:
                assert source is not None
                self.ring.add_stronghold(tuple(map(int, match.groups())), source)
                self.update_text()

    def update_text(self):
        strongholds = self.ring.known_strongholds + self.ring.guess_strongholds()
        # assert len(strongholds) == 3 or len(strongholds) == 0
        if len(strongholds) == 0:
            for stronghold_text in self.stronghold_text:
                stronghold_text.configure(foreground="black", text="unknown")
            return
        for stronghold, stronghold_text in zip(strongholds, self.stronghold_text):
            stronghold_text.configure(foreground=stronghold.source, text=str(stronghold))


if __name__ == '__main__':
    Window()
