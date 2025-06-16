def daemon():
    from ctypes import CDLL

    CDLL("libgtk4-layer-shell.so.0")

    import gi

    gi.require_version("Gtk4LayerShell", "1.0")
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")

    import signal

    from ._config import (
        config,
        DEFAULT_CSS_PROVIDER,
        DEFAULT_USER_CSS_PROVIDER,
        DEFAULT_DARK_CSS_PROVIDER,
        DEFAULT_DARK_USER_CSS_PROVIDER,
    )

    import logging

    logging.getLogger().setLevel(config.general.log_level)

    logger = logging.getLogger(__name__)

    from ._app import NiriswicherApp
    from ._wm import NiriWindowManager
    from gi.repository import Gtk, Gdk

    logger.info("Starting niriswitcher daemon")

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

    window_manager = NiriWindowManager()
    app = NiriswicherApp(window_manager)

    def signal_handler(signum, frame):
        if app._should_present_windows():
            if config.general.separate_workspaces:
                app.window.populate_separate_workspaces(
                    mru_sort=config.general.workspace_mru_sort,
                    active_output=config.general.current_output_only,
                )
            else:
                app.window.populate_unified_workspace(
                    active_output=config.general.current_output_only
                )
            app.window.set_visible(True)

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
    if app.get_is_remote():
        logger.info("niriswitcher is already running...")
    else:
        app.run()


def control():
    import sys
    import argparse
    from gi.repository import Gio, GLib

    parser = argparse.ArgumentParser(description="Control niriswitcher")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    show_parser = subparsers.add_parser("show", help="Show switcher")
    group = show_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--window", action="store_true", help="Show window switcher")
    group.add_argument(
        "--workspace", action="store_true", help="Show workspace switcher"
    )

    args = parser.parse_args()

    if args.command != "show":
        parser.print_help()
        return 1

    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        proxy = Gio.DBusProxy.new_sync(
            bus,
            Gio.DBusProxyFlags.NONE,
            None,
            "io.github.isaksamsten.Niriswitcher",
            "/io/github/isaksamsten/Niriswitcher",
            "io.github.isaksamsten.Niriswitcher",
            None,
        )

        if args.window:
            proxy.call_sync("application", None, Gio.DBusCallFlags.NONE, -1, None)
        elif args.workspace:
            proxy.call_sync("workspace", None, Gio.DBusCallFlags.NONE, -1, None)

        return 0

    except GLib.Error as e:
        print(
            f"Error: Failed to connect to DBus service 'io.github.isaksamsten.Niriswitcher' at '/io/github/isaksamsten/Niriswitcher'.\n"
            f"Reason: [{type(e).__name__}] {e.message}\n"
            "Possible causes:\n"
            "  - The niriswitcher service is not running.\n"
            "  - There is a problem with your DBus session.\n"
            "Suggestions:\n"
            "  - Start or restart niriswitcher.\n"
            "  - Ensure your DBus session is active.\n",
            file=sys.stderr,
        )
        return 1
