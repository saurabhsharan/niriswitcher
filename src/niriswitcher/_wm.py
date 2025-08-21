import json
import operator
import os
import socket
import time

from gi.repository import Gio, GObject, GLib, Gtk, Gdk

import logging

logger = logging.getLogger(__name__)


def find_icon(app_info: Gio.DesktopAppInfo) -> Gio.Icon | None:
    app_name = "unknown-application"
    icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
    if app_info:
        app_name = app_info.get_name()
        icon = app_info.get_icon()
        if isinstance(icon, Gio.ThemedIcon):
            icon_names = icon.get_names()
            for icon_name in icon_names:
                if icon_theme.has_icon(icon_name):
                    try:
                        return icon
                    except Exception:
                        continue
        elif isinstance(icon, Gio.LoadableIcon):
            try:
                return icon
            except Exception:
                pass

    if icon_theme.has_icon("application-x-executable"):
        logger.debug("Can't find icon for %s, using default fallback", app_name)
        icon = Gio.ThemedIcon.new("application-x-executable")
        return icon

    logger.error("Can't find icon for %s", app_name)
    return None


class Window(GObject.Object):
    id = GObject.Property(type=int)
    workspace_id = GObject.Property(type=int)
    app_id = GObject.Property(type=str)
    app_info = GObject.Property(type=Gio.DesktopAppInfo)
    title = GObject.Property(type=str)
    is_urgent = GObject.Property(type=bool, default=False)
    last_focus_time = GObject.Property(type=float)
    icon = GObject.Property(type=Gio.Icon)
    name = GObject.Property(type=str)

    def __init__(self, window, last_focus_time=None):
        app_id = window["app_id"]
        workspace_id = window["workspace_id"]
        app_info = get_app_info(app_id) if app_id is not None else None
        if self.app_info is not None:
            name = self.app_info.get_display_name()
        else:
            name = self.app_id if self.app_id is not None else "Unknown"
        super().__init__(
            id=window["id"],
            workspace_id=workspace_id if workspace_id is not None else -1,
            app_id=app_id,
            name=name,
            icon=find_icon(app_info),
            app_info=get_app_info(app_id) if app_id is not None else None,
            title=window["title"],
            last_focus_time=(
                last_focus_time if last_focus_time is not None else time.time()
            ),
        )

    def update(self, new):
        self.last_focus_time = time.time()
        if title := new.get("title"):
            if self.title != title:
                self.title = title
        if workspace_id := new.get("workspace_id"):
            if self.workspace_id != workspace_id:
                self.workspace_id = workspace_id
        else:
            self.workspace_id = -1

    def center(self):
        niri_request({"Action": {"CenterWindow": {"id": int(self.id)}}})

    def focus(self):
        niri_request({"Action": {"FocusWindow": {"id": int(self.id)}}})

    def close(self):
        niri_request({"Action": {"CloseWindow": {"id": int(self.id)}}})


class Workspace(GObject.Object):
    id = GObject.Property(type=int)
    idx = GObject.Property(type=int)
    name = GObject.Property(type=str)
    output = GObject.Property(type=str)
    is_active = GObject.Property(type=bool, default=False)
    is_focused = GObject.Property(type=bool, default=False)
    is_urgent = GObject.Property(type=bool, default=False)
    last_focus_time = GObject.Property(type=float)

    @GObject.Property(type=str)
    def identifier(self):
        if self.output is not None:
            return f"{self.output}-{self.idx}"
        else:
            return str(self.idx)

    def __init__(self, workspace, last_focus_time=None):
        super().__init__(
            id=workspace["id"],
            idx=workspace["idx"],
            name=(
                workspace["name"] if workspace["name"] is not None else str(self.idx)
            ),
            output=workspace["output"],
            is_active=workspace["is_active"],
            is_focused=workspace["is_focused"],
            last_focus_time=(
                last_focus_time if last_focus_time is not None else time.time()
            ),
        )

    def update(self, new):
        self.last_focus_time = time.time()
        if output := new.get("output"):
            if self.output != output:
                self.output = output
        if is_active := new.get("is_active"):
            if self.is_active != is_active:
                self.is_active = is_active
        if is_focused := new.get("is_focused"):
            if self.is_focused != is_focused:
                self.is_focused = is_focused
        if name := new.get("name"):
            if self.name != name:
                self.name = name
        if idx := new.get("idx"):
            if self.idx != idx:
                self.idx = idx


def get_app_info(app_id: str) -> Gio.AppInfo | None:
    try:
        return Gio.DesktopAppInfo.new(app_id + ".desktop")
    except Exception:
        return get_app_info_fallback(app_id)


def get_app_info_fallback(app_id: str) -> Gio.AppInfo | None:
    app_id = app_id.lower()
    try:
        return Gio.DesktopAppInfo.new(app_id + ".desktop")
    except Exception:
        desktop_files = Gio.AppInfo.get_all()
        for desktop_file in desktop_files:
            startup_wm_class = desktop_file.get_string("StartupWMClass")
            name = desktop_file.get_name()
            if (name and app_id == name.lower()) or (
                startup_wm_class and app_id == startup_wm_class.lower()
            ):
                return desktop_file
        return None


def connect_niri_socket():
    niri_socket = socket.socket(socket.AF_UNIX)
    niri_socket.connect(os.environ.get("NIRI_SOCKET"))
    return niri_socket


def niri_request(request):
    with connect_niri_socket() as niri_socket:
        with niri_socket.makefile("rw") as socket_file:
            socket_file.write(json.dumps(request))
            socket_file.write("\n")
            socket_file.flush()
            niri_socket.shutdown(socket.SHUT_WR)
            socket_file.readline()  # Avoid broken pipe in niri


class NiriWindowManager(GObject.Object):
    __gsignals__ = {
        "window-closed": (GObject.SignalFlags.RUN_FIRST, None, (Window,)),
        "window-opened": (GObject.SignalFlags.RUN_FIRST, None, (Window,)),
        "window-focus-changed": (GObject.SignalFlags.RUN_FIRST, None, (Window,)),
        "workspace-activated": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (Workspace, Workspace),
        ),
        "workspace-urgency-changed": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (Workspace,),
        ),
        "window-urgency-changed": (GObject.SignalFlags.RUN_FIRST, None, (Window,)),
    }

    active_workspace = GObject.Property(type=int, default=-1)
    active_window = GObject.Property(type=int, default=-1)

    def __init__(self):
        super().__init__()
        self.windows: dict[int, Window] = {}
        self.workspaces: dict[int, Workspace] = {}
        self._windows_loaded = False
        self._workspaces_loaded = False
        self._n_failed_connection_attempts = 0
        self._start_socket_connection()

    def _start_socket_connection(self):
        socket_path = os.environ.get("NIRI_SOCKET")
        try:
            address = Gio.UnixSocketAddress.new(socket_path)
            client = Gio.SocketClient.new()

            self.socket_connection = client.connect(address, None)
            self.input_stream = self.socket_connection.get_input_stream()
            self.data_input_stream = Gio.DataInputStream.new(self.input_stream)
            self.output_stream = self.socket_connection.get_output_stream()

            self.output_stream.write_all(b'"EventStream"\n', None)
            self._n_failed_connection_attempts = 0
            self._queue_next_line_read()
        except GLib.GError as e:
            logger.error("Error reading from socket. Is NIRI_SOCKET set?")
            raise e

    def on_workspaces_changed(self, workspace_changed):
        now = time.time()
        for workspace in workspace_changed["workspaces"]:
            last_focus_time = now
            workspace_id = workspace["id"]
            if workspace["is_focused"]:
                last_focus_time = last_focus_time + 1
                self.active_workspace = workspace_id

            self.workspaces[workspace_id] = Workspace(
                workspace, last_focus_time=last_focus_time
            )
        self._workspaces_loaded = True

    def on_windows_changed(self, windows_changed):
        self.windows.clear()
        now = time.time()
        for window in windows_changed["windows"]:
            last_focus_time = now
            window_id = window["id"]
            if window["is_focused"]:
                last_focus_time = last_focus_time + 1
                self.active_window = window_id
            window = Window(window, last_focus_time=last_focus_time)
            self.windows[window_id] = window
        self._windows_loaded = True

    def _queue_next_line_read(self):
        self.data_input_stream.read_line_async(
            GLib.PRIORITY_DEFAULT, None, self._on_line_read
        )

    def _on_line_read(self, stream, result):
        try:
            line = stream.read_line_finish_utf8(result)[0]
            if line:
                obj = json.loads(line)
                self._process_event(obj)

            self._queue_next_line_read()
        except GLib.Error:
            self._n_failed_connection_attempts += 1
            logger.debug(
                "Error reading from the socket. Retrying %d/3...",
                self._n_failed_connection_attempts,
                exc_info=True,
            )
            if self._n_failed_connection_attempts < 3:
                self._start_socket_connection()
            else:
                logger.error("Error reading from socket. Is NIRI_SOCKET set?")

    def _process_event(self, obj):
        if workspace_changed := obj.get("WorkspacesChanged"):
            self.on_workspaces_changed(workspace_changed)
        elif windows_changed := obj.get("WindowsChanged"):
            self.on_windows_changed(windows_changed)
        elif window_closed := obj.get("WindowClosed"):
            window_id = window_closed["id"]
            if window_id in self.windows:
                window = self.windows[window_id]
                del self.windows[window_id]
                self.emit("window-closed", window)
        elif opened_or_changed := obj.get("WindowOpenedOrChanged"):
            window = opened_or_changed["window"]
            window_id = window["id"]
            if exists := self.windows.get(window_id):
                exists.update(window)
            else:
                self.windows[window_id] = Window(window)
                self.emit("window-opened", self.windows[window_id])
        elif window_focus_changed := obj.get("WindowFocusChanged"):
            window_id = window_focus_changed["id"]
            if window_id in self.windows:
                self.windows[window_id].last_focus_time = time.time()
                self.active_window = window_id
                self.emit("window-focus-changed", self.windows[window_id])
        elif workspace_activated := obj.get("WorkspaceActivated"):
            previous = self.active_workspace
            self.active_workspace = workspace_activated["id"]
            workspace = self.workspaces[self.active_workspace]
            workspace.last_focus_time = time.time()
            self.emit("workspace-activated", workspace, self.workspaces.get(previous))
        elif workspace_urgency_changed := obj.get("WorkspaceUrgencyChanged"):
            workspace_id = workspace_urgency_changed["id"]
            if workspace := self.workspaces.get(workspace_id):
                workspace.is_urgent = workspace_urgency_changed["urgent"]
                self.emit("workspace-urgency-changed", workspace)
        elif window_urgency_changed := obj.get("WindowUrgencyChanged"):
            window_id = window_urgency_changed["id"]
            if window := self.windows.get(window_id):
                window.is_urgent = window_urgency_changed["urgent"]
                self.emit("window-urgency-changed", window)

    def get_workspace(self, workspace_id: int) -> Workspace | None:
        return self.workspaces.get(workspace_id, None)

    def get_workspace_by_idx(self, workspace_idx: int) -> list[Workspace]:
        return [
            workspace
            for workspace in self.workspaces.values()
            if workspace.idx == workspace_idx
        ]

    def get_active_workspace(self):
        if not self._workspaces_loaded:
            return None
        return self.workspaces[self.active_workspace]

    def get_n_workspaces(self, active_output=False):
        if not self._workspaces_loaded:
            return 0
        if current_workspace := self.get_active_workspace():
            count = 0
            for workspace in self.workspaces.values():
                if not active_output or workspace.output == current_workspace.output:
                    count += 1
            return count
        else:
            return 0

    def get_n_windows(self, active_workspace=True, active_output=False):
        if not self._windows_loaded:
            return 0

        if current_workspace := self.get_active_workspace():
            count = 0
            if not active_workspace:
                for window in self.windows.values():
                    if workspace := self.get_workspace(window.workspace_id):
                        if (
                            not active_output
                            or workspace.output == current_workspace.output
                        ):
                            count += 1
            else:
                for window in self.windows.values():
                    if workspace := self.get_workspace(window.workspace_id):
                        if window.workspace_id == current_workspace.id and (
                            not active_output
                            or workspace.output == current_workspace.output
                        ):
                            count += 1
            return count
        else:
            return 0

    def get_windows(
        self, active_workspace=True, workspace_id=None, active_output=False
    ) -> list[Window]:
        windows = self.windows.values()
        if active_output:
            current_workspace = self.get_active_workspace()

            def f(w: Window) -> bool:
                if workspace := self.get_workspace(w.workspace_id):
                    if workspace.output == current_workspace.output:
                        return True

                return False

            windows = filter(f, windows)

        if active_workspace and workspace_id is None:
            windows = filter(
                lambda w: w.workspace_id == -1
                or w.workspace_id == self.active_workspace,
                windows,
            )
        if workspace_id is not None:
            windows = filter(
                lambda w: w.workspace_id == -1 or w.workspace_id == workspace_id,
                windows,
            )

        return sorted(windows, key=operator.attrgetter("last_focus_time"), reverse=True)

    def get_windows_by_app_id(self, app_id: str) -> list[Window]:
        app_windows = [
            w for w in self.windows.values() if w.app_id and w.app_id.lower() == app_id.lower()
        ]
        return sorted(app_windows, key=operator.attrgetter("last_focus_time"), reverse=True)

    def get_workspaces(self, mru=False, active_output=False):
        workspaces = []
        if active_workspace := self.get_active_workspace():
            for workspace in self.workspaces.values():
                if not active_output or workspace.output == active_workspace.output:
                    workspaces.append(workspace)

        if mru:
            return sorted(
                workspaces, key=operator.attrgetter("last_focus_time"), reverse=True
            )
        else:
            return sorted(workspaces, key=operator.attrgetter("idx"))
