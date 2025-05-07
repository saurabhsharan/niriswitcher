import operator
import time
import json
import subprocess
import os
import gi
import queue
import threading
import sys
import signal

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk, Gio, GLib, Gdk


def find_appinfo_by_appid(app_id):
    # Try direct matches
    candidates = [app_id, app_id + ".desktop"]
    for cand in candidates:
        try:
            app_info = Gio.DesktopAppInfo.new(cand)
            return app_info
        except:
            pass

    # Search all desktop files for matching StartupWMClass or app_id in filename
    all_info = Gio.AppInfo.get_all()
    for info in all_info:
        if not isinstance(info, Gio.DesktopAppInfo):
            continue
        wmclass = info.get_string("StartupWMClass")
        filename = info.get_filename()
        basename = filename.rsplit("/", 1)[-1] if filename else ""
        if app_id == wmclass or app_id in (basename, basename.replace(".desktop", "")):
            return info
    return None


def icon_widget_for_app_id(app_id, size=64):
    app_info = find_appinfo_by_appid(app_id)
    if app_info:
        icon = app_info.get_icon()
        if icon:
            image = Gtk.Image.new_from_gicon(icon)
            image.set_pixel_size(size)
            return image
    return Gtk.Image()


def load_css_from_config(app_name="niriswitcher", filename="style.css"):
    config_home = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    css_path = os.path.join(config_home, app_name, filename)
    if not os.path.isfile(css_path):
        print("CSS file not found at:", css_path)
        return

    provider = Gtk.CssProvider()
    with open(css_path, "rb") as f:
        css_data = f.read()
        provider.load_from_data(css_data)

    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    print(f"Loaded CSS from {css_path}")


def on_key_release(controller, keyval, keycode, state, win):
    if keyval in (Gdk.KEY_Alt_L, Gdk.KEY_Alt_R):
        win.hide_and_activate_window()
        return True
    return False


def is_tab_combo(keyval):
    return keyval in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab)


def on_press_key(controller, keyval, keycode, state, win):
    print(keyval, keycode)
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


class IconBox(Gtk.Box):
    def __init__(self, id, icon, name, title):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.id = id
        self.title = title
        self.name = name
        self.add_css_class("iconbox")

        icon.add_css_class("icon")
        name = Gtk.Label()
        name.set_label(self.name)
        name.add_css_class("icon-text")

        self.append(icon)
        self.append(name)

    def select(self):
        self.add_css_class("selected")

    def deselect(self):
        self.remove_css_class("selected")


def get_app_info(window):
    try:
        return Gio.DesktopAppInfo.new(window["app_id"] + ".desktop")
    except Exception:
        return None


def get_app_icon(app_info, size):
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
    if child_x < visible_start:
        hadj.set_value(child_x)
    elif (child_x + child_width) > visible_end:
        hadj.set_value(child_x + child_width - hadj.get_page_size())


class IconStripWindow(Gtk.Window):
    def __init__(self, app):
        super().__init__(application=app, title="niriswitcher")
        self.key_controller = Gtk.EventControllerKey.new()
        self.add_controller(self.key_controller)
        self.add_css_class("main-window")

        self.set_default_size(600, 100)

        self.icons = []
        self.selected_icon = None
        main_view = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_view.add_css_class("main-view")
        main_view.set_halign(Gtk.Align.FILL)  # Center horizontally
        main_view.set_valign(Gtk.Align.FILL)  # Center vertically if desired

        self.icon_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.icon_hbox.add_css_class("center-box")

        self.title = Gtk.Label()
        self.title.add_css_class("title")

        self.scrollarea = Gtk.ScrolledWindow()
        self.scrollarea.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.scrollarea.set_child(self.icon_hbox)
        self.scrollarea.add_css_class("switcher-scroll")

        main_view.append(self.title)
        main_view.append(self.scrollarea)

        self.set_child(main_view)
        self.set_decorated(False)
        self.set_modal(True)
        self.set_resizable(False)

        self.key_controller.connect("key-released", on_key_release, self)
        self.key_controller.connect("key-pressed", on_press_key, self)
        self.connect("map", self.on_map)

    def on_map(self, window):
        surface = self.get_surface()
        surface.inhibit_system_shortcuts(None)

    def clear_app_icon(self):
        for icon in self.icons:
            self.icon_hbox.remove(icon)
        self.icons.clear()
        self.selected_icon = None

    def add_app_icon(self, window):
        app_info = get_app_info(window)
        if app_info is None:
            return

        icon = get_app_icon(app_info, 64)
        box = IconBox(window["id"], icon, app_info.get_name(), window["title"])

        self.icons.append(box)
        self.icon_hbox.append(box)

    def hide_and_activate_window(self):
        if self.selected_icon is not None:
            selected = self.get_selected_icon()
            subprocess.call(
                ["niri", "msg", "action", "focus-window", "--id", str(selected.id)]
            )
            self.hide()

    def get_selected_icon(self):
        if self.selected_icon is not None:
            return self.icons[self.selected_icon]

    def select(self, index):
        if self.selected_icon is not None:
            self.icons[self.selected_icon].deselect()

        self.selected_icon = index
        selected = self.icons[self.selected_icon]
        selected.select()
        self.title.set_label(selected.title)
        GLib.idle_add(scroll_child_into_view, self.scrollarea, selected)

    def select_next(self):
        if self.selected_icon is not None:
            self.icons[self.selected_icon].deselect()
            self.selected_icon = (self.selected_icon + 1) % len(self.icons)
            selected = self.icons[self.selected_icon]
            selected.select()
            self.title.set_label(selected.title)
            GLib.idle_add(scroll_child_into_view, self.scrollarea, selected)

    def select_prev(self):
        if self.selected_icon is not None:
            self.icons[self.selected_icon].deselect()
            self.selected_icon = (self.selected_icon - 1) % len(self.icons)
            selected = self.icons[self.selected_icon]
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
        threading.Thread(target=self.stdin_worker, daemon=True).start()

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

            self.window.select(1)

        self.window.present()

    def stdin_worker(self):
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
            # elif "WindowFocusChanged" in obj:
            #     window_focus = obj["WindowFocusChanged"]
            #     with self.lock:
            #         window_id = window_focus["id"]
            #         if window_id in self.windows:
            #             self.windows[window_id]["active_time"] = time.time()

            elif "WorkspaceActivated" in obj:
                with self.lock:
                    self.active_workspace = obj["WorkspaceActivated"]["id"]

            # app_id = line.strip()
            # if app_id:
            #     self.queue.put(app_id)

        print("done")


# Example:
def main():
    load_css_from_config()
    app = IconStreamApp()

    def on_show_switcher(app):
        app.activate()

    def signal_handler(signum, frame):
        GLib.idle_add(on_show_switcher, app)

    signal.signal(signal.SIGUSR1, signal_handler)
    app.register(None)
    app.run()
