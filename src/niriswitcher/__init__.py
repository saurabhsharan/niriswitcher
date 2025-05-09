from ctypes import CDLL

CDLL("libgtk4-layer-shell.so")

import importlib
import importlib.resources
import time
import os
import signal
import configparser

from dataclasses import dataclass

from ._wm import NiriWindowManager, Window


import gi

gi.require_version("Gtk4LayerShell", "1.0")
gi.require_version("Gtk", "4.0")

from gi.repository import Gtk, Gio, GLib, Gdk, Pango
from gi.repository import Gtk4LayerShell as LayerShell


@dataclass
class NiriswitcherConfigGeneral:
    icon_size: int = 128
    scroll_animaton_duration: int = 500
    max_width: int = 800
    active_workspace: bool = True
    double_click_to_hide: bool = False


@dataclass
class NiriswitcherConfig:
    general: NiriswitcherConfigGeneral


def load_configuration(config_path=None):
    config_home = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    config_dir = os.path.join(config_home, "niriswitcher")
    if config_path is None:
        config_path = os.path.join(config_dir, "config.ini")
    config = configparser.ConfigParser()
    config.read(config_path)

    if config.has_section("general"):
        section = config["general"]
        icon_size = section.getint("icon_size", fallback=128)
        max_width = section.getint("max_width", fallback=800)
        active_workspace = section.getboolean("active_workspace", fallback=True)
        scroll_animation_duration = section.getint("scroll_animation_duration", 500)
        double_click_to_hide = section.getint("double_click_to_hide", False)
        general = NiriswitcherConfigGeneral(
            icon_size=icon_size,
            max_width=max_width,
            active_workspace=active_workspace,
            scroll_animaton_duration=scroll_animation_duration,
            double_click_to_hide=double_click_to_hide,
        )
    else:
        general = NiriswitcherConfigGeneral()

    return NiriswitcherConfig(general=general)


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


def on_application_pressed(gesture, n_press, x, y, application, win):
    hide = True
    if win.config.general.double_click_to_hide:
        hide = n_press > 1

    button = gesture.get_current_button()
    if button == 1:
        win.focus_window(application, hide=hide)
        win.select_application(application)
    elif button == 3:
        win.close_window(application)


def on_key_release(controller, keyval, keycode, state, win):
    """
    Handles the key release event for the given controller.

    If the released key is either the left or right Alt key, this function
    hides and activates the currently selected window.
    """
    if keyval in (Gdk.KEY_Alt_L, Gdk.KEY_Alt_R):
        win.focus_selected_window()
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
        win.select_prev_application()
    elif (
        is_tab_combo(keyval) and (state & Gdk.ModifierType.ALT_MASK)  # Alt is held
    ):
        win.select_next_application()
    elif keyval == Gdk.KEY_Escape:
        win.hide()
    elif keyval == Gdk.KEY_q:
        win.close_selected_window()


class Application(Gtk.Box):
    def __init__(self, window: Window, *, size):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        icon = new_app_icon_or_default(window.app_info, size)
        name = Gtk.Label()
        name.set_ellipsize(Pango.EllipsizeMode.END)
        name.set_max_width_chars(1)
        name.set_hexpand(True)
        name.set_label(self.window.name)

        self.append(icon)
        self.append(name)

        name.add_css_class("application-name")
        self.add_css_class("application-area")
        icon.add_css_class("application-icon")

    def select(self):
        self.add_css_class("selected")

    def deselect(self):
        self.remove_css_class("selected")


def new_app_icon_or_default(app_info: Gio.DesktopAppInfo, size):
    if app_info:
        icon = app_info.get_icon()
        if isinstance(icon, Gio.ThemedIcon):
            icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
            icon_names = icon.get_names()
            for icon_name in icon_names:
                if icon_theme.has_icon(icon_name):
                    try:
                        gicon = Gio.ThemedIcon.new(icon_name)
                        image = Gtk.Image.new_from_gicon(gicon)
                        image.set_pixel_size(size)
                        return image
                    except Exception:
                        continue
        elif isinstance(icon, Gio.LoadableIcon):
            try:
                image = Gtk.Image.new_from_gicon(icon)
                image.set_pixel_size(size)
                return image
            except Exception:
                pass
        elif isinstance(icon, str):
            if icon_theme.has_icon(icon):
                try:
                    gicon = Gio.ThemedIcon.new(icon)
                    image = Gtk.Image.new_from_gicon(gicon)
                    image.set_pixel_size(size)
                    return image
                except Exception:
                    pass

    icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
    if icon_theme.has_icon("application-x-executable"):
        gicon = Gio.ThemedIcon.new("application-x-executable")
        image = Gtk.Image.new_from_gicon(gicon)
        image.set_pixel_size(size)
        return image

    image = Gtk.Image()
    image.set_pixel_size(size)
    return image


def animate_scroll_application_into_view(
    scrolled_application_strip, selected_application, duration=200
):
    def f(scrolled_application_strip, selected_application):
        hadj = scrolled_application_strip.get_hadjustment()
        child_x = selected_application.get_allocation().x
        child_width = selected_application.get_allocation().width
        visible_start = hadj.get_value()
        visible_end = visible_start + hadj.get_page_size()
        if child_x >= visible_start and (child_x + child_width) <= visible_end:
            return

        child_center = child_x + child_width / 2
        new_value = child_center - hadj.get_page_size() / 2

        new_value = max(
            hadj.get_lower(), min(new_value, hadj.get_upper() - hadj.get_page_size())
        )

        if duration == 0:
            hadj.set_value(new_value)
            return

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
                return True
            else:
                hadj.set_value(new_value)
                return False

        GLib.timeout_add(16, animate_scroll)

    GLib.idle_add(f, scrolled_application_strip, selected_application)


class ApplicationSwitcherWindow(Gtk.Window):
    def __init__(self, app, config, window_manager):
        super().__init__(application=app, title="niriswitcher")
        self.config = config
        self.window_manager = window_manager

        self.application_strip = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=12
        )
        self.application_strip.set_halign(Gtk.Align.CENTER)
        self.application_strip.set_valign(Gtk.Align.CENTER)
        self.application_strip.set_hexpand(False)
        self.application_strip.add_css_class("application-strip")

        self.current_application_title = Gtk.Label()
        self.current_application_title.set_ellipsize(Pango.EllipsizeMode.END)
        self.current_application_title.set_max_width_chars(1)
        self.current_application_title.set_hexpand(True)
        self.current_application_title.add_css_class("application-title")

        self.application_strip_scroll = Gtk.ScrolledWindow()
        self.application_strip_scroll.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER
        )
        self.application_strip_scroll.set_halign(Gtk.Align.CENTER)
        self.application_strip_scroll.set_child(self.application_strip)
        self.application_strip_scroll.add_css_class("application-strip-scroll")

        self.switcher_view = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.switcher_view.add_css_class("switcher-view")
        self.switcher_view.set_halign(Gtk.Align.CENTER)
        self.switcher_view.set_valign(Gtk.Align.CENTER)
        self.switcher_view.append(self.current_application_title)
        self.switcher_view.append(self.application_strip_scroll)

        self.set_child(self.switcher_view)
        self.set_decorated(False)
        self.set_modal(True)
        self.set_resizable(False)
        self.add_css_class("niriswitcher-window")
        self.set_default_size(-1, 100)
        self.current_application = None

        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-released", on_key_release, self)
        key_controller.connect("key-pressed", on_press_key, self)
        self.add_controller(key_controller)
        self.connect("map", self.on_map)

    def on_map(self, window):
        surface = self.get_surface()
        surface.inhibit_system_shortcuts(None)

    def activate_and_show(self):
        self._clear_applications()
        mru_windows = self.window_manager.get_windows(
            active_workspace=self.config.general.active_workspace
        )

        if len(mru_windows) > 1:
            for window in mru_windows:
                application = Application(window, size=self.config.general.icon_size)
                gesture = Gtk.GestureClick.new()
                gesture.set_button(0)
                gesture.connect("pressed", on_application_pressed, application, self)
                application.add_controller(gesture)

                self.application_strip.append(application)
            self.queue_resize()
            second = self.application_strip.get_first_child().get_next_sibling()
            self.select_application(second)
            self.resize_to_fit()
            self.present()

    def _clear_applications(self):
        application = self.application_strip.get_first_child()
        while application is not None:
            next = application.get_next_sibling()
            self.application_strip.remove(application)
            application = next

        self.current_application = None

    def focus_selected_window(self, hide=True):
        self.focus_window(self.current_application, hide=hide)

    def focus_window(self, application, hide=True):
        if application is not None:
            if hide:
                self.hide()

            self.window_manager.focus_window(application.window.id)

    def close_selected_window(self):
        self.close_window(self.current_application)

    def close_window(self, application):
        self.current_application = application.get_prev_sibling()
        if self.current_application is None:
            self.current_application = application.get_next_sibling()

        self.application_strip.remove(application)
        if self.current_application is not None:
            self.resize_to_fit()
            self.select_application(self.current_application)
        else:
            self.hide()

        self.window_manager.close_window(application.window.id)

    def resize_to_fit(self):
        measure = self.application_strip.measure(Gtk.Orientation.HORIZONTAL, -1)
        size = min(self.config.general.max_width, measure.natural)
        self.switcher_view.set_size_request(size, -1)
        self.application_strip_scroll.set_size_request(size, -1)

    def select_application(self, application):
        if self.current_application is not None:
            self.current_application.deselect()

        self.current_application = application
        self.current_application.select()
        self.current_application_title.set_label(self.current_application.window.title)
        animate_scroll_application_into_view(
            self.application_strip_scroll,
            self.current_application,
            duration=self.config.general.scroll_animaton_duration,
        )

    def select_next_application(self):
        next = self.current_application.get_next_sibling()
        if next is None:
            next = self.application_strip.get_first_child()
        self.select_application(next)

    def select_prev_application(self):
        prev = self.current_application.get_prev_sibling()
        if prev is None:
            prev = self.application_strip.get_last_child()
        self.select_application(prev)


class NiriswicherApp(Gtk.Application):
    def __init__(self):
        super().__init__()

    def do_activate(self):
        config = load_configuration()
        window_manager = NiriWindowManager()
        self.window = ApplicationSwitcherWindow(self, config, window_manager)
        LayerShell.init_for_window(self.window)
        LayerShell.set_namespace(self.window, "niriswitcher")
        LayerShell.set_layer(self.window, LayerShell.Layer.TOP)
        LayerShell.auto_exclusive_zone_enable(self.window)
        LayerShell.set_keyboard_mode(self.window, LayerShell.KeyboardMode.EXCLUSIVE)


def main():
    load_and_initialize_styles()
    app = NiriswicherApp()

    def signal_handler(signum, frame):
        app.window.activate_and_show()

    signal.signal(signal.SIGUSR1, signal_handler)
    app.register(None)
    app.run()
