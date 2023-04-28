import dataclasses
import enum
import json
import math
import os
import pathlib
import re
import subprocess
import threading
import time
import tkinter as tk
import typing
from tkinter import ttk

import win32gui
import win32process


class Config:
    instance_dir: pathlib.Path
    font_size: int
    interval: int

    def __init__(self, instance_dir: str, font_size=10, interval=1000):
        self.instance_dir = pathlib.Path(instance_dir)
        self.font_size = font_size
        self.interval = interval


class Window(tk.Tk):
    config: Config
    window_name: tk.StringVar
    logs: dict[str]
    locator: typing.Any
    config_file: pathlib.Path

    def __init__(self):
        super().__init__()
        self.config_file = pathlib.Path(os.path.join(os.curdir, "stronghold_locator.json"))
        self.config = self.get_config()
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
        # needs to be threaded so the powershell call doesn't make the window stutter while moving around
        threading.Thread(target=self.locator.check_window).start()
        self.after(self.config.interval, self.loop)

    # noinspection SpellCheckingInspection
    def get_config(self) -> Config:
        if not self.config_file.exists():
            with self.config_file.open("w") as file:
                json.dump(
                    {
                        "instance": r"C:\Users\justi\Documents\Programs\MultiMC\instances",
                        "font_size": 12,
                        "interval": 2000
                    },
                    file,
                    indent=2
                )
        with self.config_file.open("r") as file:
            config: dict = json.load(file)
            return Config(config.get("instance"), config.get("font_size"), config.get("interval"))


class StrongholdSource(enum.StrEnum):
    invalid = "blue"
    proximity = "green"
    guess = "red"
    other = "yellow"


class Stronghold:
    x: int
    y: int
    source: str

    def __init__(self, coords: typing.Union[tuple[int, int], tuple[int, ...]], source: StrongholdSource):
        assert len(coords) == 2
        self.x = coords[0]
        self.y = coords[1]
        self.source = source

    def get_coords(self) -> tuple[int, int]:
        return self.x, self.y

    def __str__(self):
        return ", ".join(map(str, self.get_coords()))


@dataclasses.dataclass
class StrongholdRing:
    center_x: int = 7
    center_y: int = 84
    radius: int = 896  # (1152 - 640) / 2 + 640, probably mostly correct
    known_strongholds: list[Stronghold] = dataclasses.field(default_factory=list)

    def get_angle(self, stronghold: Stronghold) -> float:
        return math.atan2(stronghold.y - self.center_y, stronghold.x - self.center_x) % math.tau

    def guess_strongholds(self) -> list[Stronghold]:
        guesses: list[Stronghold] = []
        if len(self.known_strongholds) == 3:
            return guesses
        if len(self.known_strongholds) == 0:
            return guesses
        angle = self.get_angle(self.known_strongholds[0])
        assert angle >= 0
        if len(self.known_strongholds) == 2:
            angle2 = self.get_angle(self.known_strongholds[1])
            angle3 = (angle + angle2) / 2
            if abs(angle - angle2) < math.pi:
                angle3 += math.pi
            guesses.append(Stronghold(self.get_coords(angle3), StrongholdSource.guess))
            return guesses
        if len(self.known_strongholds) == 1:
            guesses.append(Stronghold(self.get_coords((angle + math.tau / 3) % math.tau), StrongholdSource.guess))
            guesses.append(Stronghold(self.get_coords((angle + math.tau * 2 / 3) % math.tau), StrongholdSource.guess))
            return guesses

    def add_stronghold(self, coords: tuple[int, ...], source: StrongholdSource):
        stronghold = Stronghold(tuple((coord * 16 + 4 for coord in coords)), source)
        if not self.has_stronghold(stronghold):
            self.known_strongholds.append(stronghold)

    def has_stronghold(self, stronghold: Stronghold) -> bool:
        return len(list(filter(lambda sh: sh.x == stronghold.x and sh.y == stronghold.y, self.known_strongholds))) == 1

    def get_coords(self, angle: float) -> tuple[int, int]:
        return int(self.center_x + self.radius * math.cos(angle)), int(self.center_y + self.radius * math.sin(angle))


def get_focus_handles() -> tuple[int, int]:
    hwnd = win32gui.GetForegroundWindow()
    pid = win32process.GetWindowThreadProcessId(hwnd)[1]
    return hwnd, pid


class Instance:
    ring: StrongholdRing
    logs: typing.IO
    paused: bool
    # manager: Locator
    invalid_biome_stronghold: re.Pattern = re.compile(r"^Placed stronghold in INVALID biome at \((-?\d+), (-?\d+)\)$")
    proximity_stronghold: re.Pattern = re.compile(r"^(-?\d+), (-?\d+)$")

    def __init__(self, logs: typing.IO, manager):
        self.paused = True
        self.manager = manager
        self.logs = logs
        self.ring = StrongholdRing()

    def run(self):
        self.manager.update_text(self.ring)
        self.paused = False
        while not self.paused:
            line = self.logs.readline()
            if not line.__contains__("\n"):
                time.sleep(1)
                continue
            if line == "Scanning folders...\n":
                self.ring = StrongholdRing()
                self.manager.update_text(self.ring)
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
                self.manager.update_text(self.ring)
        print("pausing " + self.logs.name.split("\\")[-4])

    def pause(self):
        self.paused = True


class Locator:
    instances: dict[pathlib.Path, Instance] = dict()
    current_logs: pathlib.Path = None
    stronghold_text: list[ttk.Label]
    window_name = tk.StringVar

    def __init__(self, stronghold_text: list[ttk.Label], instance_dir: str, window_name: tk.StringVar):
        self.stronghold_text = stronghold_text
        self.instance_dir = instance_dir.replace("\\", "/")
        self.window_name = window_name
        self.set_window_name("unknown", None)

    def set_window_name(self, name: str, pid: typing.Optional[int]) -> None:
        self.window_name.set(f"window: {name} ({'unknown' if pid is None else pid})")

    def check_window(self):
        hwnd, pid = get_focus_handles()
        new_logs = self.get_logs(self.get_directory(pid))
        if new_logs:
            if new_logs not in self.instances:
                print("new instance")
                self.instances[new_logs] = Instance(new_logs.open(), self)
            if new_logs != self.current_logs:
                print("switch instance")
                if self.current_logs:
                    self.instances.get(self.current_logs).pause()
                self.current_logs = new_logs
                self.set_window_name(win32gui.GetWindowText(hwnd), pid)
                threading.Thread(target=lambda: self.instances.get(self.current_logs).run()).start()

    def get_directory(self, pid: int) -> typing.Optional[pathlib.Path]:
        # ~~stolen~~ adapted from easy-multi
        cmd = f'powershell.exe "$proc = Get-WmiObject Win32_Process -Filter \\"ProcessId = {str(pid)}\\"; ' \
              '$proc.CommandLine"'
        p = subprocess.Popen(args=cmd, stdout=subprocess.PIPE, shell=True)
        response = p.communicate()[0].decode()
        # print(pid, self.instance_dir, response)
        if self.instance_dir in response:
            start = response.index(self.instance_dir)
            end = response.index(r"/", start + len(self.instance_dir) + 1)
            return pathlib.Path(response[start:end])
        return None

    @classmethod
    def get_logs(cls, instance_dir: typing.Optional[pathlib.Path]) -> typing.Optional[pathlib.Path]:
        if instance_dir is None:
            return None
        logs = instance_dir.joinpath(".minecraft/logs/latest.log")
        if not logs.exists():
            return None
        return logs

    def update_text(self, ring: StrongholdRing):
        strongholds = ring.known_strongholds + ring.guess_strongholds()
        assert len(strongholds) == 3 or len(strongholds) == 0
        if len(strongholds) == 0:
            for stronghold_text in self.stronghold_text:
                stronghold_text.configure(foreground="black", text="unknown")
            return
        for stronghold, stronghold_text in zip(strongholds, self.stronghold_text):
            stronghold_text.configure(foreground=stronghold.source, text=str(stronghold))


if __name__ == '__main__':
    Window()
