from ctypes import CDLL

CDLL("libgtk4-layer-shell.so.0")

import gi  # noqa: E402

gi.require_version("Gtk4LayerShell", "1.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

import signal  # noqa: E402

from ._config import (  # noqa: E402
    config,
    DEFAULT_CSS_PROVIDER,
    DEFAULT_USER_CSS_PROVIDER,
    DEFAULT_DARK_CSS_PROVIDER,
    DEFAULT_DARK_USER_CSS_PROVIDER,
)
from ._app import NiriswicherApp  # noqa: E402
from ._wm import NiriWindowManager  # noqa: E402
from gi.repository import Gtk, Gdk  # noqa: E402


def main():
    window_manager = NiriWindowManager()
    app = NiriswicherApp(window_manager)

    def should_present():
        separate_workspaces = config.general.separate_workspaces
        n_windows = window_manager.get_n_windows(active_workspace=separate_workspaces)

        return (separate_workspaces and n_windows > 0) or (
            not separate_workspaces and n_windows > 1
        )

    def signal_handler(signum, frame):
        if should_present():
            app.window.present()

    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(),
        DEFAULT_CSS_PROVIDER,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
    if DEFAULT_USER_CSS_PROVIDER is not None:
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            DEFAULT_USER_CSS_PROVIDER,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 2,
        )

    if (
        app.get_style_manager().get_dark() and config.appearance.system_theme == "auto"
    ) or config.appearance.system_theme == "dark":
        _set_dark_style()
        if config.appearance.system_theme == "auto":
            app.get_style_manager().connect("notify::dark", on_dark)

    signal.signal(signal.SIGUSR1, signal_handler)
    app.register(None)
    app.run()


def _set_dark_style():
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(),
        DEFAULT_DARK_CSS_PROVIDER,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1,
    )
    if DEFAULT_DARK_USER_CSS_PROVIDER is not None:
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            DEFAULT_DARK_USER_CSS_PROVIDER,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 3,
        )


def on_dark(style_manager, prop):
    if style_manager.get_dark():
        _set_dark_style()
    else:
        Gtk.StyleContext.remove_provider_for_display(
            Gdk.Display.get_default(), DEFAULT_DARK_CSS_PROVIDER
        )
        if DEFAULT_DARK_USER_CSS_PROVIDER is not None:
            Gtk.StyleContext.remove_provider_for_display(
                Gdk.Display.get_default(), DEFAULT_DARK_USER_CSS_PROVIDER
            )
