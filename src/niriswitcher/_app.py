from __future__ import annotations

import logging
import operator
import inspect
from typing import TYPE_CHECKING, Callable, Union

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
    from ._wm import NiriWindowManager, Workspace, Window

logger = logging.getLogger(__name__)


class KeybindingAction:
    action: Union[Callable[[], None], Callable[[int], None]]

    def __init__(
        self,
        mapping: tuple[int, int] | tuple[list[int], int],
        action: Callable[None, None],
    ):
        self.keyval = (
            mapping[0] if hasattr(mapping[0], "__contains__") else [mapping[0]]
        )
        self.state = mapping[1]
        self.action = action
        self.mod_count = bin(int(self.state)).count("1")
        sig = inspect.signature(self.action)
        self.arg_count = len(
            [
                p
                for p in sig.parameters.values()
                if p.kind
                in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                )
            ]
        )

    def matches(self, keyval, state):
        if keyval in self.keyval and (
            (state & Gtk.accelerator_get_default_mod_mask())
            == (self.state & Gtk.accelerator_get_default_mod_mask())
        ):
            return True
        return False

    def execute(self, keyval):
        try:
            if self.arg_count == 1:
                self.action(keyval)
            else:
                self.action()
        except Exception:
            logger.debug("Failed to execute %s", self.action.__name__, exc_info=True)


NUMBER_KEY_TO_NUMBER: dict[int, int] = {
    Gdk.KEY_1: 1,
    Gdk.KEY_2: 2,
    Gdk.KEY_3: 3,
    Gdk.KEY_4: 4,
    Gdk.KEY_5: 5,
    Gdk.KEY_6: 6,
    Gdk.KEY_7: 7,
    Gdk.KEY_8: 8,
    Gdk.KEY_9: 9,
    Gdk.KEY_0: 10,
}

CYCLE_SESSION_TIMEOUT_SECONDS = 1.5


class CycleSession:
    def __init__(self, app_id: str, windows: list["Window"]):
        self.app_id = app_id
        self.original_windows = windows.copy()
        self.current_index = 0
        self.timer_id = None
        print(f"[CycleSession] Starting session for {app_id} with {len(windows)} windows")
        print(f"[CycleSession] Window order: {[w.title for w in windows]}")
    
    def get_current_window(self) -> "Window":
        return self.original_windows[self.current_index]
    
    def cycle_next(self) -> "Window":
        old_index = self.current_index
        self.current_index = (self.current_index + 1) % len(self.original_windows)
        current_window = self.get_current_window()
        print(f"[CycleSession] Cycling from index {old_index} to {self.current_index}: {current_window.title} (ID: {current_window.id})")
        print(f"[CycleSession] All windows in session: {[(i, w.title, w.id) for i, w in enumerate(self.original_windows)]}")
        return current_window
    
    def extend_session(self, timeout_callback):
        if self.timer_id:
            GLib.source_remove(self.timer_id)
        self.timer_id = GLib.timeout_add(
            int(CYCLE_SESSION_TIMEOUT_SECONDS * 1000), 
            timeout_callback
        )
        print(f"[CycleSession] Extended session for {self.app_id}")
    
    def is_active(self) -> bool:
        """Check if the session timer is still active"""
        return self.timer_id is not None
    
    def end_session(self):
        if self.timer_id:
            GLib.source_remove(self.timer_id)
            self.timer_id = None
        print(f"[CycleSession] Ended session for {self.app_id}")
        return False


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

        keyval = Gdk.keyval_to_lower(keyval)

        for keybinding in self.keybindings:
            if keybinding.matches(keyval, state):
                keybinding.execute(keyval)
                break

    def on_window_closed(self, wm, window):
        for workspace_view in self.workspace_stack:
            if workspace_view.remove_by_window_id(window.id):
                if workspace_view.is_empty():
                    self.set_visible(False)
                return

    def on_workspace_activated(self, wm, current: Workspace, previous: Workspace):
        if self.is_visible():
            if config.general.current_output_only and previous is not None:
                if previous.output != current.output:
                    self.set_visible(False)
                    return

            self.workspace_indicator.select_by_workspace_id(current.id)

    def on_workspace_selection_changed(
        self, widget: Gtk.Widget, workspace: Workspace, animate: bool
    ):
        self._set_workspace_name(workspace)

    def on_window_focus_changed(self, vm, window):
        workspace_view = self.workspace_stack.get_visible_child()
        for application_view in workspace_view:
            if application_view.window.id == window.id:
                application_view.focus()
                workspace_view.scroll_to(application_view)
            else:
                application_view.unfocus()

    def on_application_selection_changed(self, widget: Gtk.Widget, window: Window):
        title = window.title if window.title is not None else ""
        self.current_application_title.set_label(title)
        if not config.general.separate_workspaces:
            workspace = self.window_manager.get_workspace(window.workspace_id)
            if workspace is not None:
                self._set_workspace_name(workspace)

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

    def _set_workspace_name(self, workspace: Workspace):
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

    def _create_keybindings(self):
        mappings = [
            KeybindingAction(config.keys.next, self.select_next_application),
            KeybindingAction(config.keys.prev, self.select_prev_application),
            KeybindingAction(config.keys.abort, self.hide),
            KeybindingAction(config.keys.close, self.close_selected_window),
            KeybindingAction(config.keys.next_workspace, self.select_next_workspace),
            KeybindingAction(config.keys.prev_workspace, self.select_prev_workspace),
        ]
        if config.general.current_output_only:
            mappings.append(
                KeybindingAction(
                    (NUMBER_KEY_TO_NUMBER.keys(), config.keys.modifier_mask),
                    self._select_workspace_by_idx,
                )
            )
        return sorted(
            mappings,
            key=operator.attrgetter("mod_count"),
            reverse=True,
        )

    def populate_unified_workspace(self, active_output=False):
        windows = self.window_manager.get_windows(
            active_workspace=False, active_output=active_output
        )
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
        self.workspace_stack.add_named(workspace_view, "all")
        workspace_view.select_next()

    def populate_separate_workspaces(
        self, mru_sort=False, mru_select=False, active_output=False
    ):
        self.workspace_indicator.set_visible(True)
        workspaces = self.window_manager.get_workspaces(
            mru=mru_sort, active_output=active_output
        )
        for current_workspace in workspaces:
            windows = self.window_manager.get_windows(workspace_id=current_workspace.id)
            if len(windows) > 0:
                workspace_view = WorkspaceView(
                    current_workspace,
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

        if mru_select:
            if not mru_sort:
                workspaces = sorted(
                    workspaces,
                    key=operator.attrgetter("last_focus_time"),
                    reverse=True,
                )
            active_workspace = None
            for current_workspace in workspaces[1:]:
                windows = self.window_manager.get_windows(
                    workspace_id=current_workspace.id
                )
                if len(windows) > 0:
                    active_workspace = current_workspace
                    break
            if active_workspace is None:
                active_workspace = workspaces[0]
            self.workspace_indicator.select_by_workspace_id(
                active_workspace.id, animate=False
            )
        else:
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

    def _select_workspace_by_idx(self, keyval: int):
        idx = NUMBER_KEY_TO_NUMBER.get(keyval)
        if idx is not None:
            if workspaces := self.window_manager.get_workspace_by_idx(idx):
                if active_workspace := self.window_manager.get_active_workspace():
                    if workspace := next(
                        (
                            workspace
                            for workspace in workspaces
                            if workspace.output == active_workspace.output
                        ),
                        None,
                    ):
                        self.workspace_indicator.select_by_workspace_id(workspace.id)


class NiriswicherApp(Adw.Application):
    DBUS_INTERFACE_XML = """
    <node>
        <interface name="io.github.isaksamsten.Niriswitcher">
            <method name="application">
            </method>
            <method name="workspace">
            </method>
            <method name="cycleApplication">
                <arg name="app_id" type="s" direction="in" />
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
        self._cycle_session = None

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

    def _should_present_windows(self, active_output=False):
        if self.window.is_visible():
            return False

        separate_workspaces = config.general.separate_workspaces
        n_windows = self.window_manager.get_n_windows(
            active_workspace=separate_workspaces, active_output=active_output
        )
        return (separate_workspaces and n_windows > 0) or (
            not separate_workspaces and n_windows > 1
        )

    def _should_present_workspaces(self, active_output=False):
        if self.window.is_visible():
            return False

        n_windows = self.window_manager.get_n_windows(
            active_workspace=False, active_output=active_output
        )
        n_workspaces = self.window_manager.get_n_workspaces(active_output=active_output)
        return n_windows > 0 and n_workspaces > 1

    def _cycle_application_by_id(self, app_id: str):
        if self.window.get_visible():
            print(f"[CycleApp] Ignoring cycle request - switcher is already open")
            return

        app_windows = self.window_manager.get_windows_by_app_id(app_id)
        if not app_windows:
            print(f"[CycleApp] No windows found for app_id '{app_id}'")
            return

        if len(app_windows) == 1:
            print(f"[CycleApp] Only one window for {app_id}, focusing it")
            app_windows[0].focus()
            return

        create_new_session = (
            self._cycle_session is None or 
            self._cycle_session.app_id != app_id or
            not self._cycle_session.is_active()
        )
        
        if create_new_session:
            print(f"[CycleApp] Creating new session (active: {self._cycle_session.is_active() if self._cycle_session else False})")
            self._end_cycle_session()
            self._cycle_session = CycleSession(app_id, app_windows)
            
            active_window_id = self.window_manager.active_window
            print(f"[CycleApp] Active window ID: {active_window_id}")
            print(f"[CycleApp] All app windows: {[(w.id, w.title) for w in app_windows]}")
            
            try:
                current_window_idx = next(
                    i for i, w in enumerate(app_windows) if w.id == active_window_id
                )
                self._cycle_session.current_index = current_window_idx
                print(f"[CycleApp] Found current window at index {current_window_idx} ('{app_windows[current_window_idx].title}')")
            except StopIteration:
                print(f"[CycleApp] Current window not found in app windows, starting from -1")
                self._cycle_session.current_index = -1

        print(f"[CycleApp] Before cycle_next: current_index = {self._cycle_session.current_index}")
        window_to_focus = self._cycle_session.cycle_next()
        self._cycle_session.extend_session(self._end_cycle_session)
        
        print(f"[CycleApp] Focusing window: {window_to_focus.title} (ID: {window_to_focus.id})")
        window_to_focus.focus()

    def _end_cycle_session(self):
        if self._cycle_session:
            self._cycle_session.end_session()
            self._cycle_session = None
        return False

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
                if self._should_present_windows(
                    active_output=config.general.current_output_only
                ):
                    if config.general.separate_workspaces:
                        self.window.populate_separate_workspaces(
                            mru_sort=config.workspace.mru_sort_in_workspace,
                            active_output=config.general.current_output_only,
                        )
                    else:
                        self.window.populate_unified_workspace(
                            active_output=config.general.current_output_only
                        )

                    self.window.set_visible(True)
                invocation.return_value(None)
            elif method_name == "workspace":
                if config.general.separate_workspaces:
                    if self._should_present_workspaces(
                        active_output=config.general.current_output_only
                    ):
                        self.window.populate_separate_workspaces(
                            mru_sort=config.workspace.mru_sort_across_workspace,
                            mru_select=True,
                            active_output=config.general.current_output_only,
                        )
                        self.window.set_visible(True)
                else:
                    if self._should_present_windows(
                        active_output=config.general.current_output_only
                    ):
                        self.window.populate_unified_workspace(
                            active_output=config.general.current_output_only
                        )
                        self.window.set_visible(True)
                invocation.return_value(None)
            elif method_name == "cycleApplication":
                    app_id = parameters.get_child_value(0).get_string()
                    self._cycle_application_by_id(app_id)
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
