from ctypes import CDLL

CDLL("libgtk4-layer-shell.so.0")

import gi  # noqa: E402

gi.require_version("Gtk4LayerShell", "1.0")
gi.require_version("Gtk", "4.0")

import signal  # noqa: E402

from ._config import config  # noqa: E402
from ._app import NiriswicherApp  # noqa: E402


def main():
    app = NiriswicherApp()

    def signal_handler(signum, frame):
        separate_workspaces = config.general.separate_workspaces
        n_windows = app.window.window_manager.get_n_windows(
            active_workspace=separate_workspaces
        )

        if (separate_workspaces and n_windows > 0) or (
            not separate_workspaces and n_windows > 1
        ):
            app.window.present()

    signal.signal(signal.SIGUSR1, signal_handler)
    app.register(None)
    app.run()
