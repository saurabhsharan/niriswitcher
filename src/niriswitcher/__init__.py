from ctypes import CDLL

CDLL("libgtk4-layer-shell.so")

import importlib
import importlib.resources
import operator
import time
import json
import subprocess
import os
import queue
import threading
import sys
import signal

import gi

gi.require_version("Gtk4LayerShell", "1.0")
gi.require_version("Gtk", "4.0")

from gi.repository import Gtk, Gio, GLib, Gdk, Pango
from gi.repository import Gtk4LayerShell as LayerShell


def load_and_initialize_styles(filename="style.css"):
    with (
        importlib.resources.files("niriswitcher.resources")
        .joinpath(filename)
        .open("rb") as f
    ):
        provider = Gtk.CssProvider()
        css_data = f.read()
        provider.load_from_data(css_data)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    config_home = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    user_css_path = os.path.join(config_home, "niriswitcher", filename)
    if os.path.isfile(user_css_path):
        with open(user_css_path, "rb") as f:
            user_provider = Gtk.CssProvider()
            css_data = f.read()
            user_provider.load_from_data(css_data)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                user_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1,
            )


def on_key_release(controller, keyval, keycode, state, win):
    """
    Handles the key release event for the given controller.

    If the released key is either the left or right Alt key, this function
    hides and activates the currently selected window.
    """
    if keyval in (Gdk.KEY_Alt_L, Gdk.KEY_Alt_R):
        win.hide_and_activate_window()
        return True
    return False


def on_press_key(controller, keyval, keycode, state, win):
    """
    Handles key press events to manage window selection and visibility.

    Detects specific key combinations involving Tab, Shift, and Alt to
    trigger window navigation actions or hide the window.
    """

    # helper to detect tab while holding shift
    def is_tab_combo(keyval):
        return keyval in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab)

    if (
        is_tab_combo(keyval)
        and (state & Gdk.ModifierType.ALT_MASK)  # Alt is held
        and (state & Gdk.ModifierType.SHIFT_MASK)
    ):
        win.select_prev()
    elif (
        is_tab_combo(keyval) and (state & Gdk.ModifierType.ALT_MASK)  # Alt is held
    ):
        win.select_next()
    elif keyval == Gdk.KEY_Escape:
        win.hide()
    elif keyval == Gdk.KEY_q:
        win.quit_selected()


class IconBox(Gtk.Box):
    def __init__(self, id, icon, name, title):
        """
        Initializes a new instance of the class with the specified ID, icon, name, and title.

        Args:
            id: The unique identifier for the instance.
            icon: The Gtk widget representing the icon to be displayed.
            name: The display name for the instance.
            title: The title associated with the instance.
        """
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.id = id
        self.title = title
        self.name = name
        name = Gtk.Label()
        name.set_label(self.name)

        self.append(icon)
        self.append(name)

        name.add_css_class("icon-text")
        self.add_css_class("iconbox")

        icon.add_css_class("icon")

    def select(self):
        self.add_css_class("selected")

    def deselect(self):
        self.remove_css_class("selected")


def get_app_info(window):
    try:
        return Gio.DesktopAppInfo.new(window["app_id"] + ".desktop")
    except Exception:
        return None


def new_app_icon_or_default(app_info, size):
    if app_info:
        icon = app_info.get_icon()
        if icon:
            image = Gtk.Image.new_from_gicon(icon)
            image.set_pixel_size(size)
            return image

    image = Gtk.Image()
    image.set_pixel_size(size)
    return image


def scroll_child_into_view(scrolled_window, child):
    hadj = scrolled_window.get_hadjustment()
    child_x = child.get_allocation().x
    child_width = child.get_allocation().width
    visible_start = hadj.get_value()
    visible_end = visible_start + hadj.get_page_size()
    if child_x >= visible_start and (child_x + child_width) <= visible_end:
        return
    # Center the child in the visible area when scrolling
    child_center = child_x + child_width / 2
    new_value = child_center - hadj.get_page_size() / 2
    # Clamp the value to valid range
    new_value = max(
        hadj.get_lower(), min(new_value, hadj.get_upper() - hadj.get_page_size())
    )
    duration = 200
    start_value = hadj.get_value()
    delta = new_value - start_value
    start_time = time.monotonic()

    def ease_in_out_cubic(t):
        if t < 0.5:
            return 4 * t * t * t
        else:
            return 1 - pow(-2 * t + 2, 3) / 2

    def animate_scroll():
        elapsed = (time.monotonic() - start_time) * 1000
        t = min(elapsed / duration, 1.0)
        eased_t = ease_in_out_cubic(t)
        current_value = start_value + delta * eased_t
        hadj.set_value(current_value)
        if t < 1.0:
            return True  # Continue
        else:
            hadj.set_value(new_value)
            return False  # Stop

    GLib.timeout_add(16, animate_scroll)


class IconStripWindow(Gtk.Window):
    def __init__(self, app):
        super().__init__(application=app, title="niriswitcher")
        self.key_controller = Gtk.EventControllerKey.new()
        self.add_controller(self.key_controller)
        self.add_css_class("main-window")

        self.set_default_size(-1, 100)

        self.icons = []
        self.selected_index = None
        self.main_view = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.main_view.add_css_class("main-view")
        self.main_view.set_halign(Gtk.Align.CENTER)
        self.main_view.set_valign(Gtk.Align.CENTER)

        self.icon_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.icon_hbox.add_css_class("icon-strip")

        self.title = Gtk.Label()
        self.title.set_ellipsize(Pango.EllipsizeMode.END)
        self.title.set_max_width_chars(1)
        self.title.set_hexpand(True)
        self.title.add_css_class("title")

        self.scrollarea = Gtk.ScrolledWindow()
        self.scrollarea.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.scrollarea.set_halign(Gtk.Align.CENTER)
        self.scrollarea.set_child(self.icon_hbox)
        self.scrollarea.add_css_class("icon-strip-scroll")

        self.main_view.append(self.title)
        self.main_view.append(self.scrollarea)

        self.set_child(self.main_view)
        self.set_decorated(False)
        self.set_modal(True)
        self.set_resizable(False)

        self.key_controller.connect("key-released", on_key_release, self)
        self.key_controller.connect("key-pressed", on_press_key, self)
        self.connect("map", self.on_map)

    def on_map(self, window):
        surface = self.get_surface()
        surface.inhibit_system_shortcuts(None)

    def get_current_key_event(self):
        return self.key_controller.get_current_event()

    def clear_app_icon(self):
        for icon in self.icons:
            self.icon_hbox.remove(icon)
        self.icons.clear()
        self.selected_index = None

    def add_app_icon(self, window):
        app_info = get_app_info(window)
        if app_info is None:
            return

        icon = new_app_icon_or_default(app_info, 128)
        box = IconBox(window["id"], icon, app_info.get_name(), window["title"])

        self.icons.append(box)
        self.icon_hbox.append(box)

    def hide_and_activate_window(self):
        if self.selected_index is not None:
            selected = self.get_selected_icon()
            subprocess.call(
                ["niri", "msg", "action", "focus-window", "--id", str(selected.id)]
            )
            self.selected_index = None
            self.hide()

    def quit_selected(self):
        if self.selected_index is not None:
            selected = self.get_selected_icon()
            subprocess.call(
                ["niri", "msg", "action", "close-window", "--id", str(selected.id)]
            )
            selected_index = self.selected_index
            self.icon_hbox.remove(selected)
            self.icons.remove(selected)
            if len(self.icons) > 0:
                self.resize_to_fit()
                self.selected_index = None
                self.select(max(0, selected_index - 1))
            else:
                self.selected_index = None
                self.hide()

    def resize_to_fit(self):
        size = self.icon_hbox.get_width()
        measure = self.icon_hbox.measure(Gtk.Orientation.HORIZONTAL, -1)
        size = min(800, measure.natural)
        self.main_view.set_size_request(size, -1)
        self.scrollarea.set_size_request(size, -1)

    def get_selected_icon(self):
        if self.selected_index is not None and self.selected_index < len(self.icons):
            return self.icons[self.selected_index]

    def select(self, index):
        if self.selected_index is not None:
            self.icons[self.selected_index].deselect()

        self.selected_index = index
        selected = self.icons[self.selected_index]
        selected.select()
        self.title.set_label(selected.title)
        GLib.idle_add(scroll_child_into_view, self.scrollarea, selected)

    def select_next(self):
        if self.selected_index is not None:
            self.icons[self.selected_index].deselect()
            self.selected_index = (self.selected_index + 1) % len(self.icons)
            selected = self.icons[self.selected_index]
            selected.select()
            self.title.set_label(selected.title)
            GLib.idle_add(scroll_child_into_view, self.scrollarea, selected)

    def select_prev(self):
        if self.selected_index is not None:
            self.icons[self.selected_index].deselect()
            self.selected_index = (self.selected_index - 1) % len(self.icons)
            selected = self.icons[self.selected_index]
            selected.select()
            self.title.set_label(selected.title)
            GLib.idle_add(scroll_child_into_view, self.scrollarea, selected)


class IconStreamApp(Gtk.Application):
    def __init__(self):
        super().__init__()
        self.windows = {}
        self.workspaces = {}
        self.active_workspace = None
        self.focused_window = None
        self.window = None
        self.lock = threading.Lock()

    def do_activate(self):
        self.window = IconStripWindow(self)
        LayerShell.init_for_window(self.window)
        LayerShell.set_namespace(self.window, "niriswitcher")
        LayerShell.set_layer(self.window, LayerShell.Layer.TOP)
        LayerShell.auto_exclusive_zone_enable(self.window)
        LayerShell.set_keyboard_mode(self.window, LayerShell.KeyboardMode.EXCLUSIVE)
        threading.Thread(target=self.track_niri_windows, daemon=True).start()

    def activate(self):
        self.window.clear_app_icon()
        with self.lock:
            mru_windows = sorted(
                filter(
                    lambda w: w["workspace_id"] == self.active_workspace,
                    self.windows.values(),
                ),
                key=operator.itemgetter("active_time"),
                reverse=True,
            )
            for window in mru_windows:
                self.window.add_app_icon(window)

        if len(mru_windows) > 1:
            self.window.queue_resize()
            self.window.select(1)
            self.window.resize_to_fit()
            self.window.present()

    def track_niri_windows(self):
        # Runs 'niri msg' and reads its output lines.
        process = subprocess.Popen(
            ["niri", "msg", "-j", "event-stream"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        for line in process.stdout:
            obj = json.loads(line)
            if "WorkspacesChanged" in obj:
                workspace_changed = obj["WorkspacesChanged"]
                with self.lock:
                    for workspace in workspace_changed["workspaces"]:
                        if workspace["is_focused"]:
                            self.active_workspace = workspace["id"]

                        self.workspaces[workspace["id"]] = workspace
            elif "WindowsChanged" in obj:
                windows_changed = obj["WindowsChanged"]
                with self.lock:
                    now = time.time()
                    for window in windows_changed["windows"]:
                        active_time = now
                        if window["is_focused"]:
                            active_time = 0

                        window["active_time"] = active_time
                        self.windows[window["id"]] = window
            elif "WindowClosed" in obj:
                window_closed = obj["WindowClosed"]
                window_id = window_closed["id"]
                with self.lock:
                    if window_id in self.windows:
                        del self.windows[window_id]
            elif "WindowOpenedOrChanged" in obj:
                opened_or_changed = obj["WindowOpenedOrChanged"]
                with self.lock:
                    window = opened_or_changed["window"]
                    window_id = window["id"]
                    window["active_time"] = time.time()
                    self.windows[window_id] = window
            elif "WorkspaceActiveWindowChanged" in obj:
                workspace_window = obj["WorkspaceActiveWindowChanged"]
                workspace_id = workspace_window["workspace_id"]
                with self.lock:
                    if workspace_id:
                        self.active_workspace = workspace_id
                    window_id = workspace_window["active_window_id"]
                    if window_id in self.windows:
                        self.windows[window_id]["active_time"] = time.time()
            elif "WorkspaceActivated" in obj:
                with self.lock:
                    self.active_workspace = obj["WorkspaceActivated"]["id"]


def main():
    load_and_initialize_styles()
    app = IconStreamApp()

    def on_show_switcher(app):
        app.activate()

    def signal_handler(signum, frame):
        app.activate()
        # GLib.idle_add(on_show_switcher, app)

    signal.signal(signal.SIGUSR1, signal_handler)
    app.register(None)
    app.run()
