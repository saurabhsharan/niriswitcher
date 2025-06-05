from __future__ import annotations

import logging
import operator
from typing import TYPE_CHECKING

from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango
from gi.repository import Gtk4LayerShell as LayerShell

from ._config import config
from ._widgets import (
    WidgetPropertyAnimation,
    WorkspaceIndicator,
    WorkspaceStack,
    WorkspaceView,
)

if TYPE_CHECKING:
    from ._wm import NiriWindowManager, Workspace

logger = logging.getLogger(__name__)


class KeybindingAction:
    """
    Represents an action bound to a specific keybinding, including its key
    value, modifier state, and the action to execute.

    Attributes:
        keyval (int): The key value associated with the keybinding.
        state (int): The modifier state (e.g., Ctrl, Shift) for the keybinding.
        action (callable): The function or callable to execute when the keybinding is triggered.
        mod_count (int): The number of modifier keys active in the state.

    """

    def __init__(self, mapping, action):
        self.keyval = mapping[0]
        self.state = mapping[1]
        self.action = action
        self.mod_count = bin(int(self.state)).count("1")

    def matches(self, keyval, state):
        if keyval == self.keyval and (
            (state & Gtk.accelerator_get_default_mod_mask())
            == (self.state & Gtk.accelerator_get_default_mod_mask())
        ):
            return True
        return False

    def execute(self):
        try:
            self.action()
        except Exception:
            logger.debug("Failed to execute %s", self.action.__name__, exc_info=True)


class NiriswitcherWindow(Gtk.Window):
    def __init__(self, app, window_manager: NiriWindowManager):
        super().__init__(application=app, title="niriswitcher")
        self.window_manager = window_manager

        def show_hide_duration(visible):
            return (
                config.appearance.animation.activate.show_duration
                if visible
                else config.appearance.animation.activate.hide_duration
            )

        self.set_visible = WidgetPropertyAnimation(
            self.set_visible,
            before=lambda x: x,
            setter=self.set_opacity,
            initial=0.01,
            target=1,
            duration=show_hide_duration,
            easing=config.appearance.animation.activate.easing,
        )

        self.current_application_title = Gtk.Label()
        self.current_application_title.set_ellipsize(Pango.EllipsizeMode.END)
        self.current_application_title.set_max_width_chars(1)
        self.current_application_title.set_hexpand(True)
        self.current_application_title.set_name("application-title")

        self.current_workspace_name = Gtk.Label()
        self.current_workspace_name.set_ellipsize(Pango.EllipsizeMode.END)
        self.current_workspace_name.set_max_width_chars(-1)
        self.current_workspace_name.set_halign(Gtk.Align.END)
        self.current_workspace_name.set_name("workspace-name")

        self.workspace_stack = WorkspaceStack()
        self.workspace_stack.set_halign(Gtk.Align.CENTER)
        self.workspace_stack.set_size_request(config.appearance.min_width, -1)
        self.workspace_stack.set_transition_duration(
            config.appearance.animation.workspace.duration
        )
        self.workspace_stack.set_transition_type(
            config.appearance.animation.workspace.transition
        )

        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        left_margin = Gtk.Box()
        left_margin.set_halign(Gtk.Align.START)

        def sync_width(label, param):
            measure = self.current_workspace_name.measure(
                Gtk.Orientation.HORIZONTAL, -1
            )
            left_margin.set_size_request(measure.natural, -1)

        self.current_workspace_name.connect("notify::label", sync_width)
        top_bar.append(left_margin)
        top_bar.append(self.current_application_title)
        top_bar.append(self.current_workspace_name)
        top_bar.set_hexpand(True)
        top_bar.set_name("top-bar")
        main_view = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_view.set_name("main-view")
        main_view.set_halign(Gtk.Align.CENTER)
        main_view.set_valign(Gtk.Align.CENTER)
        main_view.set_hexpand(True)
        main_view.append(top_bar)
        main_view.append(self.workspace_stack)

        self.workspace_indicator = WorkspaceIndicator()
        self.workspace_indicator.connect(
            "selection-changed", self.on_workspace_selection_changed
        )

        self.workspace_stack.set_indicator(self.workspace_indicator)

        inner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        inner_box.append(self.workspace_indicator)
        inner_box.append(main_view)

        self.set_child(inner_box)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)
        self.set_decorated(False)
        self.set_modal(True)
        self.set_resizable(False)
        self.set_name("niriswitcher")
        self.set_default_size(-1, 100)

        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-released", self.on_key_released)
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(key_controller)
        self.connect("map", self.on_map)
        self.connect("show", self.on_show)
        self.connect("hide", self.on_hide)

        self.keybindings = self._create_keybindings()

    def on_key_released(self, controller, keyval, keycode, state):
        if keyval == config.keys.modifier:
            self.focus_selected_window()

    def on_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_ISO_Left_Tab:
            keyval = Gdk.KEY_Tab

        keyval_name = Gdk.keyval_name(keyval)
        if keyval_name and len(keyval_name) == 1 and keyval_name.isalpha():
            keyval = Gdk.keyval_from_name(keyval_name.lower())

        for keybinding in self.keybindings:
            if keybinding.matches(keyval, state):
                keybinding.execute()
                break

    def on_window_closed(self, wm, window):
        for workspace_view in self.workspace_stack:
            if workspace_view.remove_by_window_id(window.id):
                if workspace_view.is_empty():
                    self.set_visible(False)
                return

    def on_workspace_activated(self, wm, workspace):
        if self.is_visible():
            self.workspace_indicator.select_by_workspace_id(workspace.id)

    def on_workspace_selection_changed(
        self, widget: Gtk.Widget, workspace: Workspace, animate: bool
    ):
        try:
            self.current_workspace_name.set_label(
                config.appearance.workspace_format.format(
                    output=workspace.output,
                    idx=workspace.idx,
                    name=workspace.name,
                )
            )
        except Exception:
            self.current_workspace_name.set_label(workspace.identifier)
            logger.debug(
                "Invalid format specification for appearance.workspace_format, using default"
            )

    def on_window_focus_changed(self, vm, window):
        workspace_view = self.workspace_stack.get_visible_child()
        for application_view in workspace_view:
            if application_view.window.id == window.id:
                application_view.focus()
                workspace_view.scroll_to(application_view)
            else:
                application_view.unfocus()

    def on_application_selection_changed(self, widget, window):
        title = window.title if window.title is not None else ""
        self.current_application_title.set_label(title)

    def on_close_requested(self, widget, window):
        window.close()

    def on_focus_requested(self, widget, window, hide):
        window.focus()
        if config.general.center_on_focus:
            window.center()

        if hide:
            self.set_visible(False)

    def on_map(self, window):
        surface = self.get_surface()
        surface.inhibit_system_shortcuts(None)

    def on_hide(self, widget):
        self.window_manager.disconnect_by_func(self.on_window_closed)
        self.window_manager.disconnect_by_func(self.on_window_focus_changed)
        self.window_manager.disconnect_by_func(self.on_workspace_activated)
        for child in list(self.workspace_stack):
            self.workspace_stack.remove(child)

        for child in list(self.workspace_indicator):
            self.workspace_indicator.remove(child)

        self.current_application = None

    def on_show(self, widget):
        display = Gdk.Display.get_default()

        workspace = self.window_manager.get_active_workspace()
        if not any(
            (monitor := m).get_connector() == workspace.output
            for m in display.get_monitors()
        ):
            monitor = display.get_monitor_at_surface(self.get_surface())

        LayerShell.set_monitor(self, monitor)
        geometry = monitor.get_geometry()

        screen_width = int(geometry.width * 0.9)
        self.workspace_stack.set_width(
            min(config.appearance.min_width, screen_width),
            min(config.appearance.max_width, screen_width),
        )
        self.window_manager.connect("window-closed", self.on_window_closed)
        self.window_manager.connect(
            "workspace-activated",
            self.on_workspace_activated,
        )
        self.window_manager.connect(
            "window-focus-changed", self.on_window_focus_changed
        )

    def _create_keybindings(self):
        return sorted(
            [
                KeybindingAction(config.keys.next, self.select_next_application),
                KeybindingAction(config.keys.prev, self.select_prev_application),
                KeybindingAction(config.keys.abort, self.hide),
                KeybindingAction(config.keys.close, self.close_selected_window),
                KeybindingAction(
                    config.keys.next_workspace, self.select_next_workspace
                ),
                KeybindingAction(
                    config.keys.prev_workspace, self.select_prev_workspace
                ),
            ],
            key=operator.attrgetter("mod_count"),
            reverse=True,
        )

    def populate_unified_workspace(self):
        windows = self.window_manager.get_windows(active_workspace=False)
        workspace_view = WorkspaceView(
            None,
            windows,
            icon_size=config.appearance.icon_size,
        )
        workspace_view.set_scroll_duration(config.appearance.animation.switch.duration)
        workspace_view.set_scroll_easing(config.appearance.animation.switch.easing)
        workspace_view.set_resize_duration(config.appearance.animation.resize.duration)
        workspace_view.set_resize_easing(config.appearance.animation.resize.easing)
        workspace_view.connect("focus-requested", self.on_focus_requested)
        workspace_view.connect("close-requested", self.on_close_requested)
        workspace_view.connect(
            "selection-changed", self.on_application_selection_changed
        )
        self.workspace_indicator.set_visible(False)
        self.current_workspace_name.set_opacity(0)
        self.current_workspace_name.set_width_chars(10)
        self.workspace_stack.add_named(workspace_view, "all")
        workspace_view.select_current()

    def populate_separate_workspaces(self, mru=False):
        self.workspace_indicator.set_visible(True)
        self.current_workspace_name.set_visible(True)
        for workspace in self.window_manager.get_workspaces(mru=mru):
            windows = self.window_manager.get_windows(workspace_id=workspace.id)
            if len(windows) > 0:
                workspace_view = WorkspaceView(
                    workspace,
                    windows,
                    icon_size=config.appearance.icon_size,
                )
                workspace_view.set_scroll_duration(
                    config.appearance.animation.switch.duration
                )
                workspace_view.set_scroll_easing(
                    config.appearance.animation.switch.easing
                )
                workspace_view.set_resize_duration(
                    config.appearance.animation.resize.duration
                )
                workspace_view.set_resize_easing(
                    config.appearance.animation.resize.easing
                )
                workspace_view.connect(
                    "selection-changed", self.on_application_selection_changed
                )
                workspace_view.connect("focus-requested", self.on_focus_requested)
                workspace_view.connect("close-requested", self.on_close_requested)
                self.workspace_stack.add_workspace(workspace_view)

        active_workspace = self.window_manager.get_active_workspace()
        self.workspace_indicator.select_by_workspace_id(
            active_workspace.id, animate=False
        )
        current_workspace = self.workspace_stack.get_child_by_name(
            active_workspace.identifier
        )
        if current_workspace is not None:
            current_workspace.select_next()

    def focus_selected_window(self):
        workspace_view = self.workspace_stack.get_visible_child()
        workspace_view.focus_current(hide=True)

    def close_selected_window(self):
        workspace_view = self.workspace_stack.get_visible_child()
        workspace_view.close_current()

    def select_next_application(self):
        workspace_stack = self.workspace_stack.get_visible_child()
        workspace_stack.select_next()

    def select_prev_application(self):
        workspace_stack = self.workspace_stack.get_visible_child()
        workspace_stack.select_prev()

    def select_next_workspace(self, animate=True):
        if not config.general.separate_workspaces:
            return

        self.workspace_indicator.select_next(animate=animate)

    def select_prev_workspace(self, animate=True):
        if not config.general.separate_workspaces:
            return

        self.workspace_indicator.select_prev(animate=animate)


class NiriswicherApp(Adw.Application):
    DBUS_INTERFACE_XML = """
    <node>
        <interface name="io.github.isaksamsten.Niriswitcher">
            <method name="application">
            </method>
            <method name="workspace">
            </method>
            <property name="visible" type="b" access="read"/>
            <signal name="VisibilityChanged">
                <arg name="visible" type="b"/>
            </signal>
        </interface>
    </node>
    """

    def __init__(self, window_manager):
        super().__init__(
            application_id="io.github.isaksamsten.Niriswitcher",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.window_manager = window_manager
        self._dbus_registration_id = None

    def do_activate(self):
        self.window = NiriswitcherWindow(self, self.window_manager)
        LayerShell.init_for_window(self.window)
        LayerShell.set_namespace(self.window, "niriswitcher")
        LayerShell.set_layer(self.window, LayerShell.Layer.OVERLAY)
        LayerShell.auto_exclusive_zone_enable(self.window)
        LayerShell.set_keyboard_mode(self.window, LayerShell.KeyboardMode.EXCLUSIVE)

        self.window.connect("notify::visible", self._on_window_visibility_changed)

    def _on_window_visibility_changed(self, window, pspec):
        visible = window.get_visible()
        if self.get_dbus_connection() is not None:
            variant = GLib.Variant("(b)", (visible,))
            self.get_dbus_connection().emit_signal(
                None,
                self.get_dbus_object_path(),
                self.get_application_id(),
                "VisibilityChanged",
                variant,
            )

    def _should_present(self):
        separate_workspaces = config.general.separate_workspaces
        n_windows = self.window_manager.get_n_windows(
            active_workspace=separate_workspaces
        )
        return (separate_workspaces and n_windows > 0) or (
            not separate_workspaces and n_windows > 1
        )

    def _handle_dbus_method(
        self,
        connection,
        sender,
        object_path,
        interface_name,
        method_name,
        parameters,
        invocation,
    ):
        try:
            if method_name == "application":
                if self._should_present():
                    if config.general.separate_workspaces:
                        self.window.populate_separate_workspaces(
                            mru=config.general.workspace_mru_sort
                        )
                    else:
                        self.window.populate_unified_workspace()

                    self.window.set_visible(True)
                invocation.return_value(None)
            elif method_name == "workspace":
                if config.general.separate_workspaces:
                    self.window.populate_separate_workspaces(mru=True)
                    self.window.select_next_workspace(animate=False)
                else:
                    self.window.populate_unified_workspace()

                self.window.set_visible(True)
                invocation.return_value(None)
        except Exception as e:
            logger.exception("Failed to handle DBus message")
            invocation.return_error_literal(
                Gio.dbus_error_quark(), Gio.DBusError.FAILED, str(e)
            )

    def _unregister_dbus(self, connection):
        if self._dbus_registration_id is not None:
            try:
                connection.unregister_object(self._dbus_registration_id)
            except Exception:
                logger.debug("Failed to unregister DBus", exc_info=True)
            finally:
                self._dbus_registration_id = None

    def do_dbus_register(self, connection, object_path):
        self._unregister_dbus(connection)

        node_info = Gio.DBusNodeInfo.new_for_xml(self.DBUS_INTERFACE_XML)
        interface_info = node_info.interfaces[0]

        self._dbus_registration_id = connection.register_object(
            object_path,
            interface_info,
            self._handle_dbus_method,
            self._handle_dbus_get_property,
            None,
        )

        return Adw.Application.do_dbus_register(self, connection, object_path)

    def _handle_dbus_get_property(
        self, connection, sender, object_path, interface_name, property_name
    ):
        if property_name == "visible":
            return GLib.Variant("b", self.window.get_visible())
        return None

    def do_dbus_unregister(self, connection, object_path):
        self._unregister_dbus(connection)
        return Adw.Application.do_dbus_unregister(self, connection, object_path)
