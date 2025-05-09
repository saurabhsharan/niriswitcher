import json
import operator
import os
import socket
import threading
import time

from gi.repository import Gio

from dataclasses import dataclass


@dataclass
class Window:
    id: int
    workspace_id: int
    app_id: str
    app_info: Gio.DesktopAppInfo
    title: str
    last_focus_time: int


def new_window_from_niri(window, last_focus_time=None) -> Window:
    return Window(
        id=window["id"],
        workspace_id=window["workspace_id"],
        app_id=window["app_id"],
        app_info=get_app_info(window["app_id"]),
        title=window["title"],
        last_focus_time=last_focus_time
        if last_focus_time is not None
        else time.time_ns(),
    )


def get_app_info(app_id):
    try:
        return Gio.DesktopAppInfo.new(app_id + ".desktop")
    except Exception:
        desktop_files = Gio.AppInfo.get_all()
        for desktop_file in desktop_files:
            if app_id.lower() == desktop_file.get_string("StartupWMClass").lower():
                return desktop_file
        return None


def connect_niri_socket():
    niri_socket = socket.socket(socket.AF_UNIX)
    niri_socket.connect(os.environ.get("NIRI_SOCKET"))
    return niri_socket


def niri_request(request):
    with connect_niri_socket() as niri_socket:
        with niri_socket.makefile("w") as socket_file:
            socket_file.write(json.dumps(request))
            socket_file.write("\n")
            socket_file.flush()


class NiriWindowManager:
    def __init__(self):
        self.windows: dict[int, Window] = {}
        self.workspaces: dict[int, dict] = {}
        self.active_workspace_id: int | None = None
        self.lock = threading.Lock()
        threading.Thread(target=self.start_track_niri_windows, daemon=True).start()

    def focus_window(self, id):
        niri_request({"Action": {"FocusWindow": {"id": int(id)}}})

    def close_window(self, id):
        niri_request({"Action": {"CloseWindow": {"id": int(id)}}})

    def start_track_niri_windows(self):
        with connect_niri_socket() as niri_socket:
            with niri_socket.makefile("rw") as socket_file:
                socket_file.write('"EventStream"\n')
                socket_file.flush()
                niri_socket.shutdown(socket.SHUT_WR)
                self.track_niri_windows(socket_file)

    def track_niri_windows(self, socket_file):
        for line in socket_file:
            obj = json.loads(line)
            if workspace_changed := obj.get("WorkspacesChanged"):
                with self.lock:
                    for workspace in workspace_changed["workspaces"]:
                        if workspace["is_focused"]:
                            self.active_workspace_id = workspace["id"]

                        self.workspaces[workspace["id"]] = workspace
            elif windows_changed := obj.get("WindowsChanged"):
                with self.lock:
                    now = time.time_ns()
                    for window in windows_changed["windows"]:
                        last_focus_time = now
                        if window["is_focused"]:
                            last_focus_time = last_focus_time + 1
                        window_id = window["id"]
                        self.windows[window_id] = new_window_from_niri(
                            window, last_focus_time=last_focus_time
                        )
            elif window_closed := obj.get("WindowClosed"):
                window_id = window_closed["id"]
                with self.lock:
                    if window_id in self.windows:
                        del self.windows[window_id]
            elif opened_or_changed := obj.get("WindowOpenedOrChanged"):
                with self.lock:
                    window = opened_or_changed["window"]
                    window_id = window["id"]
                    self.windows[window_id] = new_window_from_niri(window)
            elif workspace_window := obj.get("WorkspaceActiveWindowChanged"):
                workspace_id = workspace_window["workspace_id"]
                with self.lock:
                    if workspace_id:
                        self.active_workspace_id = workspace_id
                    window_id = workspace_window["active_window_id"]
                    if window_id in self.windows:
                        self.windows[window_id].last_focus_time = time.time_ns()
            elif window_focus_changed := obj.get("WindowFocusChanged"):
                with self.lock:
                    window_id = window_focus_changed["id"]
                    if window_id in self.windows:
                        self.windows[window_id].last_focus_time = time.time_ns()
            elif workspace_activated := obj.get("WorkspaceActivated"):
                with self.lock:
                    self.active_workspace_id = workspace_activated["id"]

    def get_windows(self, active_workspace=True) -> list[Window]:
        with self.lock:
            windows = self.windows.values()
            if active_workspace:
                windows = filter(
                    lambda w: w.workspace_id == self.active_workspace_id, windows
                )

            return sorted(
                windows, key=operator.attrgetter("last_focus_time"), reverse=True
            )
