from ctypes import CDLL

CDLL("libgtk4-layer-shell.so.0")

import importlib
import importlib.resources
import time
import os
import operator
import signal
import configparser

from dataclasses import dataclass

from ._wm import NiriWindowManager, Window
from ._anim import ease_in_out_cubic, ease_out_cubic

import gi

gi.require_version("Gtk4LayerShell", "1.0")
gi.require_version("Gtk", "4.0")

from gi.repository import Gtk, Gio, GLib, Gdk, Pango
from gi.repository import Gtk4LayerShell as LayerShell


@dataclass
class GeneralConfig:
    icon_size: int = 128
    scroll_animaton_duration: int = 500
    max_width: int = 800
    active_workspace: bool = True
    double_click_to_hide: bool = False


@dataclass
class KeysConfig:
    modifier: int = Gdk.KEY_Alt_L
    next: (int, int | None) = (Gdk.KEY_Tab, Gdk.ModifierType.ALT_MASK)
    prev: (int, int | None) = (
        Gdk.KEY_Tab,
        Gdk.ModifierType.ALT_MASK | Gdk.ModifierType.SHIFT_MASK,
    )
    close: (int, int | None) = (Gdk.KEY_q, Gdk.ModifierType.ALT_MASK)
    abort: (int, int | None) = (Gdk.KEY_Escape, Gdk.ModifierType.ALT_MASK)
    next_workspace: (int, int | None) = (
        Gdk.KEY_grave,
        Gdk.ModifierType.ALT_MASK,
    )
    prev_workspace: (int, int | None) = (
        Gdk.KEY_asciitilde,
        Gdk.ModifierType.ALT_MASK | Gdk.ModifierType.SHIFT_MASK,
    )


def get_modifier_as_mask(modifier):
    """
    Returns the corresponding Gdk.ModifierType mask for a given modifier key.

    Args:
        modifier: The GDK key value representing a modifier key.

    Returns:
        Gdk.ModifierType: The modifier mask corresponding to the provided
            modifier key, or None if the key does not match any known modifier.
    """
    if modifier in (Gdk.KEY_Alt_L, Gdk.KEY_Alt_R):
        return Gdk.ModifierType.ALT_MASK
    elif modifier in (Gdk.KEY_Super_L, Gdk.KEY_Super_R):
        return Gdk.ModifierType.SUPER_MASK
    elif modifier in (Gdk.KEY_Meta_L, Gdk.KEY_Meta_R):
        return Gdk.ModifierType.META_MASK
    elif modifier in (Gdk.KEY_Control_L, Gdk.KEY_Control_R):
        return Gdk.ModifierType.CONTROL_MASK
    elif modifier in (Gdk.KEY_Shift_L, Gdk.KEY_Shift_R):
        return Gdk.ModifierType.SHIFT_MASK
    else:
        return None


def parse_modifier_key(key):
    """
    Parses a modifier key string and returns the corresponding GDK key value.

    Converts common modifier key names (e.g., "alt", "super", "shift", "control") to their
    corresponding GDK key names. Raises a ValueError if the key is not a valid modifier.

    Args:
        key (str): The name of the modifier key to parse.

    Returns:
        int or None: The GDK key value for the modifier, or None if the key is invalid.

    Raises:
        ValueError: If the key is not a valid modifier.
    """
    if key.lower() == "alt":
        key = "Alt_L"
    elif key.lower() in ("super", "mod"):
        key = "Super_L"
    elif key.lower() == "shift":
        key = "Shift_L"
    elif key.lower() == "control":
        key = "Control_L"

    modifier = Gdk.keyval_from_name(key)
    if modifier == Gdk.KEY_VoidSymbol:
        return None

    if get_modifier_as_mask(modifier) is None:
        raise ValueError("configuration error: invalid modifier")

    return modifier


def parse_accelerator_key(binding, default_modifier):
    """
    Parses an accelerator key binding string and returns the corresponding key
    and modifier mask.

    The function supports modifier names such as "shift", "control", "ctrl",
    "alt", "super", "meta", and "hyper". The "mod" modifier is normalized to
    "super", and "ctrl" is normalized to "control". If the binding is invalid
    or contains unknown modifiers, a ValueError is raised.

    Args:
        binding (str): The key binding string (e.g., "Ctrl+Alt+T").
        default_modifier (int): The default modifier mask to use if none is
            specified in the binding.

    Returns:
        tuple: A tuple (key, mods) where 'key' is the parsed key value and 'mods' is the modifier mask.

    Raises:
        ValueError: If the binding contains unknown modifiers or cannot be parsed.
    """

    def binding_str_to_accel(binding):
        parts = binding.split("+")
        VALID_MODIFIERS = {"shift", "control", "ctrl", "alt", "super", "meta", "hyper"}
        accel = ""
        for part in parts[:-1]:
            normalized = part.strip().lower()
            if normalized == "mod":
                normalized = "super"
            elif normalized == "ctrl":
                normalized = "control"

            if normalized in VALID_MODIFIERS:
                accel += f"<{normalized.capitalize()}>"
            else:
                raise ValueError(f"configuration error: unknown modifier '{part}'")
        accel += parts[-1].strip()
        return accel

    ok, key, mods = Gtk.accelerator_parse(binding_str_to_accel(binding))
    if ok:
        return (key, mods | default_modifier if mods != 0 else default_modifier)
    else:
        raise ValueError(f"unable to parse keys: {binding}")


@dataclass
class Config:
    general: GeneralConfig
    keys: KeysConfig


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
        scroll_animation_duration = section.getint("scroll_animation_duration", 200)
        double_click_to_hide = section.getboolean("double_click_to_hide", False)
        general = GeneralConfig(
            icon_size=icon_size,
            max_width=max_width,
            active_workspace=active_workspace,
            scroll_animaton_duration=scroll_animation_duration,
            double_click_to_hide=double_click_to_hide,
        )
    else:
        general = GeneralConfig()

    if config.has_section("keys"):
        keys = config["keys"]
        modifier = parse_modifier_key(keys.get("modifier", fallback="Alt_L"))
        modifier_mask = get_modifier_as_mask(modifier)
        keys = KeysConfig(
            modifier=modifier,
            next=parse_accelerator_key(keys.get("next", fallback="Tab"), modifier_mask),
            prev=parse_accelerator_key(
                keys.get("prev", fallback="Shift+Tab"), modifier_mask
            ),
            close=parse_accelerator_key(keys.get("close", fallback="q"), modifier_mask),
            abort=parse_accelerator_key(
                keys.get("abort", fallback="Escape"), modifier_mask
            ),
            next_workspace=parse_accelerator_key(
                keys.get("next_workspace", fallback="grave"), modifier_mask
            ),
            prev_workspace=parse_accelerator_key(
                keys.get("prev_workspace", fallback="Shift+grave"), modifier_mask
            ),
        )
    else:
        keys = KeysConfig()

    return Config(general=general, keys=keys)


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


def on_application_released(gesture, n_press, x, y, application, win):
    """
    Handles the release event of an application gesture, determining whether to
    focus or close the application window based on the mouse button pressed and
    the number of presses.

    Args:
        gesture: The gesture object representing the user's input.
        n_press (int): The number of times the button was pressed.
        x (int): The x-coordinate of the gesture event.
        y (int): The y-coordinate of the gesture event.
        application: The application instance associated with the gesture.
        win: The window manager instance responsible for handling window actions.

    Returns:
        None
    """
    hide = True
    if win.config.general.double_click_to_hide:
        hide = n_press > 1

    button = gesture.get_current_button()
    if button == 1:
        win.focus_window(application, hide=hide)
    elif button == 3:
        win.close_window(application)


def on_application_enter(motion, x, y, application, win):
    """
    Handles the event when the application is entered.

    If the entered application is not the current application, updates the window's
    current application title and selects the new application.

    Args:
        motion: The motion event or object triggering the application enter.
        x (int): The x-coordinate of the event.
        y (int): The y-coordinate of the event.
        application: The application object being entered.
        win: The window object managing the applications.
    """
    if application is not win.current_application:
        win.current_application_title.set_label(application.window.title)
        application.select()


def on_application_leave(motion, application, win):
    """
    Handles the event when an application is left.

    If the specified application is not the current application, it will be deselected.
    If there is a current application, updates the window's current application title label.

    Args:
        motion: The motion event or object triggering the leave.
        application: The application instance being left.
        win: The window instance containing the applications.

    Returns:
        None
    """
    if application is not win.current_application:
        application.deselect()
        if win.current_application is not None:
            win.current_application_title.set_label(
                win.current_application.window.title
            )


def on_workspace_indicator_pressed(gesture, n_press, x, y, workspace_indicator, win):
    """
    Handles the event when a workspace indicator is pressed.

    Args:
        gesture: The gesture object triggering the event.
        n_press (int): The number of presses detected.
        x (float): The x-coordinate of the press event.
        y (float): The y-coordinate of the press event.
        workspace_indicator: The workspace indicator widget associated with the event.
        win: The main application window.

    Returns:
        None
    """
    current_workspace_view = win.workspace_stack.get_visible_child()
    if current_workspace_view.workspace.id != workspace_indicator.workspace.id:
        win.select_workspace(
            win.workspace_stack.get_child_by_name(workspace_indicator.workspace.name)
        )


def on_key_release(controller, keyval, keycode, state, win):
    """
    Handles the key release event for the given controller.

    If the released key is either the left or right Alt key, this function
    hides and activates the currently selected window.
    """
    if keyval == win.config.keys.modifier:
        win.focus_selected_window(hide=True)
        return True
    return False


def on_press_key(controller, keyval, keycode, state, win):
    """
    Handles key press events to manage window selection and visibility.

    Detects specific key combinations involving Tab, Shift, and Alt to
    trigger window navigation actions or hide the window.
    """

    if keyval == Gdk.KEY_ISO_Left_Tab:
        keyval = Gdk.KEY_Tab

    keyval_name = Gdk.keyval_name(keyval)
    if keyval_name and len(keyval_name) == 1 and keyval_name.isalpha():
        keyval = Gdk.keyval_from_name(keyval_name.lower())

    actions = win.get_actions()

    for action in actions:
        if action.matches(keyval, state):
            action()
            break


class ApplicationView(Gtk.Box):
    """
    A custom GTK Box widget representing an application view with an icon and name label.

    This class displays an application's icon and name within a vertical box layout.
    It provides methods to visually indicate selection and focus states.

    Attributes:
        window (Window): The window instance associated with this application view.

    Args:
        window (Window): The window object representing the application.
        size: The size to be used for the application icon.
    """

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

        self.add_css_class("application")
        name.add_css_class("application-name")
        icon.add_css_class("application-icon")

    def select(self):
        self.add_css_class("selected")

    def deselect(self):
        self.remove_css_class("selected")

    def focus(self):
        self.add_css_class("focused")

    def unfocus(self):
        self.remove_css_class("focused")


def new_app_icon_or_default(app_info: Gio.DesktopAppInfo, size):
    """
    Returns a Gtk.Image widget for the given application's icon or a default
    icon if unavailable.

    Attempts to retrieve the icon from the provided Gio.DesktopAppInfo object.
    Handles themed icons, loadable icons, and string icon names. If no suitable
    icon is found, falls back to the "application-x-executable" icon or an
    empty Gtk.Image.

    Args:
        app_info (Gio.DesktopAppInfo): The application info object containing icon data.
        size (int): The desired pixel size for the icon image.

    Returns:
        Gtk.Image: A Gtk.Image widget displaying the application's icon or a default icon.
    """
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


class AnimateScrollToWidget:
    """
    Animates scrolling of a Gtk.ScrolledWindow to bring a specified widget into
    view smoothly.

    This class provides a callable object that, when invoked with a widget,
    scrolls the associated Gtk.ScrolledWindow horizontally to center the widget
    within the visible area. The scrolling animation duration can be
    customized.

    Attributes:
        scrolled_window (Gtk.ScrolledWindow): The scrolled window to animate.
        _timer_id (int or None): The identifier for the active GLib timeout, if any.

    Example:
        animator = AnimateScrollToWidget(scrolled_window)
        animator(target_widget, duration=300)

    """

    def __init__(self, scrolled_window):
        self.scrolled_window = scrolled_window
        self._timer_id = None

    def __call__(self, widget, duration=200):
        def animate_scroll_to_application():
            hadj = self.scrolled_window.get_hadjustment()
            child_x = widget.get_allocation().x
            child_width = widget.get_allocation().width
            visible_start = hadj.get_value()
            visible_end = visible_start + hadj.get_page_size()
            if child_x >= visible_start and (child_x + child_width) <= visible_end:
                return

            child_center = child_x + child_width / 2
            new_value = child_center - hadj.get_page_size() / 2

            new_value = max(
                hadj.get_lower(),
                min(new_value, hadj.get_upper() - hadj.get_page_size()),
            )

            if duration == 0:
                hadj.set_value(new_value)
                self._timer_id = None
                return

            start_value = hadj.get_value()
            delta = new_value - start_value
            start_time = time.monotonic()

            def animate_scroll():
                elapsed = (time.monotonic() - start_time) * 1000
                t = min(elapsed / duration, 1.0)
                eased_t = ease_in_out_cubic(t)
                current_value = start_value + delta * eased_t
                hadj.set_value(current_value)
                if t < 1.0:
                    return True
                else:
                    self._timer_id = None
                    hadj.set_value(new_value)
                    return False

            if self._timer_id is not None:
                GLib.source_remove(self._timer_id)
                self._timer_id = None

            self._timer_id = GLib.timeout_add(16, animate_scroll)

        GLib.idle_add(animate_scroll_to_application)


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

    def __call__(self):
        self.action()


class GenericTransition:
    """
    Represents a generic transition animation between two values, applying an
    easing function over a specified duration.

    This class manages the timing and application of a transition, calling a
    setter function to update the animated value, and optionally invoking a
    method before or after the transition. The transition uses an ease-out
    cubic function for smooth animation.

    Attributes:
        initial (float): The starting value of the transition.
        target (float): The ending value of the transition.
        method (callable): The function to call before or after the transition,
            depending on the 'before' flag.
        setter (callable): The function used to update the animated value
            during the transition.
        before (bool): If True, the method is called before the transition; if
        False, after.
        duration (int): The duration of the transition in milliseconds.

    """

    def __init__(self, method, *, before, setter, initial, target, duration=200):
        self._timer_id = None
        self.initial = initial
        self.target = target
        self._current = None
        self.method = method
        self.setter = setter
        self.before = before
        self.duration = duration

    def __call__(self, *args, **kwargs):
        self._current = self.initial

        if self.before:
            self.setter(self.initial)
            self.method(*args, **kwargs)

        if self.duration == 0:
            self.setter(self.target)

        def idle_add():
            delta = self.target - self.initial
            start_time = time.monotonic()

            def do_animation():
                elapsed = (time.monotonic() - start_time) * 1000
                t = min(elapsed / self.duration, 1.0)
                eased_t = ease_out_cubic(t)
                self._current = self.initial + delta * eased_t
                if t < 1.0:
                    self.setter(self._current)
                    return True
                else:
                    self._timer_id = None
                    self._current = None
                    if not self.before:
                        self.setter(self.target)
                        self.method(*args, **kwargs)
                    return False

            if self._timer_id is not None:
                GLib.source_remove(self._timer_id)

            self._timer_id = GLib.timeout_add(16, do_animation)

        GLib.idle_add(idle_add)


class SizeTransition:
    """
    Handles smooth size transitions for a widget over a specified duration using cubic easing.

    This class manages the animation of a widget's size from an initial value to a target value,
    updating the size incrementally and triggering widget redraws as needed.

    Attributes:
        _timer_id (int or None): ID of the active GLib timeout source, or None if no animation is running.
        current_size (float or None): The current interpolated size during the transition, or None when idle.
        widget: The widget instance whose size is being animated.

    Example:
        transition = SizeTransition(widget)
        transition(initial_size=100, target_size=200, duration=300)
    """

    def __init__(self, widget):
        self._timer_id = None
        self.current_size = None
        self.widget = widget

    def __call__(self, initial_size, target_size, duration=200):
        self.current_size = initial_size

        if duration == 0:
            self.current_size = target_size
            return

        def idle_add():
            delta = target_size - initial_size
            start_time = time.monotonic()

            def do_animation():
                elapsed = (time.monotonic() - start_time) * 1000
                t = min(elapsed / duration, 1.0)
                eased_t = ease_out_cubic(t)
                self.current_size = initial_size + delta * eased_t
                if t < 1.0:
                    self.widget.queue_resize()
                    return True
                else:
                    self._timer_id = None
                    self.current_size = None
                    self.widget.queue_resize()
                    return False

            if self._timer_id is not None:
                GLib.source_remove(self._timer_id)

            self._timer_id = GLib.timeout_add(16, do_animation)

        GLib.idle_add(idle_add)


class WorkspaceView(Gtk.ScrolledWindow):
    # TODO: refactor parent
    def __init__(self, parent, workspace, windows, max_size=800, icon_size=128):
        super().__init__()
        self.application_views = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=12
        )
        self.add_css_class("workspace")
        self.workspace = workspace
        self.application_views.set_halign(Gtk.Align.CENTER)
        self.application_views.set_valign(Gtk.Align.CENTER)
        self.application_views.set_hexpand(False)
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.set_halign(Gtk.Align.CENTER)
        self.set_child(self.application_views)
        for window in windows:
            application = ApplicationView(window, size=icon_size)
            gesture = Gtk.GestureClick.new()
            gesture.set_button(0)
            gesture.connect("released", on_application_released, application, parent)
            motion = Gtk.EventControllerMotion.new()
            motion.connect("enter", on_application_enter, application, parent)
            motion.connect("leave", on_application_leave, application, parent)
            application.add_controller(motion)
            application.add_controller(gesture)

            self.application_views.append(application)

        self.max_size = max_size
        self.size_transition = SizeTransition(self)
        self.scroll_to = AnimateScrollToWidget(self)

    def get_first_application_view(self):
        """
        Returns the first application view from the list of application views.

        :return: The first application view object.
        :rtype: ApplicationView or None
        """
        return self.application_views.get_first_child()

    def get_last_application_view(self):
        """
        Returns the last application view in the list of application views.

        :return: The last application view object.
        """
        return self.application_views.get_last_child()

    def get_initial_selection(self):
        """
        Returns the initial selection for the application view.

        The initial selection is determined by retrieving the first application view
        and then attempting to get its next sibling. If there is no next sibling,
        the first application view is returned as the selection.

        Returns:
            ApplicationView: The initial selection, either the next sibling of the first
            application view or the first application view itself if no sibling exists.
        """
        first = self.get_first_application_view()
        second = first.get_next_sibling()
        if second is None:
            second = first

        return second

    def remove_application_by_window_id(self, window_id):
        """
        Removes the specified window from the application strip.

        Searches for the child in the application strip whose window ID matches
        the given window's ID. If found, removes the corresponding application
        and returns a tuple indicating success and the previous (or next)
        sibling. If not found, returns a tuple indicating failure and None.

        Args:
            window: The window object to be removed.

        Returns:
            tuple: A tuple (success, sibling), where 'success' is True if the
            window was found and removed, and 'sibling' is the previous sibling
            if available, otherwise the next sibling. If not found, returns
            (False, None).
        """
        if any(
            (current := application_view).window.id == window_id
            for application_view in self
        ):
            prev = current.get_prev_sibling()
            if prev is None:
                prev = current.get_next_sibling()
            self.remove_application(current)
            return True, prev

        return False, None

    def remove_application(self, application):
        """
        Removes the specified application from the application views and
        updates the size.

        Args:
            application: The application instance to be removed.
        """
        before = self.application_views.measure(Gtk.Orientation.HORIZONTAL, -1)
        self.application_views.remove(application)
        after = self.application_views.measure(Gtk.Orientation.HORIZONTAL, -1)
        self.size_transition(
            min(self.max_size, before.natural), min(self.max_size, after.natural)
        )

    def do_measure(self, orientation, for_size):
        measure = self.application_views.measure(orientation, -1)
        min_size = measure.minimum
        nat_size = measure.natural
        if orientation == Gtk.Orientation.HORIZONTAL:
            min_size = min(self.max_size, min_size)
            nat_size = min(self.max_size, nat_size)
            if self.size_transition.current_size is not None:
                nat_size = self.size_transition.current_size

        return (min_size, nat_size, -1, -1)

    def __iter__(self):
        current = self.application_views.get_first_child()
        while current is not None:
            yield current
            current = current.get_next_sibling()


class WorkspaceIndicatorView(Gtk.Box):
    """
    A GTK Box widget that visually represents a workspace indicator.

    This view is used to display an indicator for a workspace, allowing for
    customization of its width and visual appearance via CSS classes.

    Attributes:
        workspace: The workspace object associated with this indicator.

    Args:
        workspace: The workspace to represent.
        width (int, optional): The width of the indicator. Defaults to 5.
    """

    def __init__(self, workspace, width=5):
        super().__init__()
        self.workspace = workspace
        self.set_size_request(width, -1)
        self.add_css_class("workspace-indicator")
        self.set_vexpand(True)


class WorkspaceIndicatorsView(Gtk.Box):
    """
    A GTK Box-based view for displaying and managing workspace indicators.

    This class arranges workspace indicators vertically and provides methods
    to select an indicator by workspace ID and to iterate over all indicator widgets.

    Attributes:
        None
    """

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_halign(Gtk.Align.START)
        self.set_vexpand(True)
        self.set_name("workspace-indicators")

    def select_by_workspace_id(self, workspace_id):
        for current in self:
            if current.workspace.id == workspace_id:
                current.add_css_class("selected")
            else:
                current.remove_css_class("selected")

    def __iter__(self):
        current = self.get_first_child()
        while current is not None:
            yield current
            current = current.get_next_sibling()


def on_window_closed(window, workspace_stack, win):
    """
    Handles the event when a window is closed by removing the corresponding application from the workspace stack.
    If the application is found and removed, it selects the application or hides the window if none remain.

    Args:
        window: The window object that was closed.
        workspace_stack: A list of workspace views to search for the application.
        win: The window manager or controller responsible for selecting or hiding applications.
    """
    for workspace_view in workspace_stack:
        is_removed, application = workspace_view.remove_application_by_window_id(
            window.id
        )
        if is_removed:
            if application is not None:
                win.select_application(application)
            else:
                win.hide()
            return


def on_workspace_activated(workspace, win):
    """
    Handles actions to perform when a workspace is activated.

    If the activated workspace is visible, updates the current workspace label,
    sets the visible child in the workspace stack, updates the workspace indicator,
    and selects the first application in the workspace if available.

    Args:
        workspace: The workspace object that has been activated.
        win: The main window instance containing workspace and application views.
    """
    if win.is_visible() and (
        workspace_view := win.workspace_stack.get_child_by_name(workspace.name)
    ):
        win.current_workspace_name.set_label(workspace.name)
        win.workspace_stack.set_visible_child(workspace_view)
        win.workspace_indicators.select_by_workspace_id(workspace.id)
        first_application = (
            win.workspace_stack.get_visible_child().get_first_application_view()
        )
        if first_application is not None:
            win.select_application(first_application)


def on_window_focus_changed(window, win):
    """
    Handles the event when the window focus changes.

    Iterates through the application views in the current workspace and updates their focus state
    based on whether their window matches the newly focused window.

    Args:
        window: The window object that has gained focus.
        win: The main window object containing the workspace stack.
    """
    workspace_view = win.workspace_stack.get_visible_child()
    for application_view in workspace_view:
        if application_view.window.id == window.id:
            application_view.focus()
            workspace_view.scroll_to(application_view)
        else:
            application_view.unfocus()


class NiriswitcherWindow(Gtk.Window):
    def __init__(self, app, config, window_manager):
        super().__init__(application=app, title="niriswitcher")
        self.config = config
        self.window_manager = window_manager

        self.show = GenericTransition(
            self.show,
            before=True,
            setter=self.set_opacity,
            initial=0,
            target=1,
            duration=200,
        )
        self.present = GenericTransition(
            self.present,
            before=True,
            setter=self.set_opacity,
            initial=0,
            target=1,
            duration=200,
        )
        self.hide = GenericTransition(
            self.hide,
            before=False,
            setter=self.set_opacity,
            initial=1,
            target=0,
            duration=200,
        )

        self.current_application_title = Gtk.Label()
        self.current_application_title.set_ellipsize(Pango.EllipsizeMode.END)
        self.current_application_title.set_width_chars(30)
        self.current_application_title.set_max_width_chars(1)
        self.current_application_title.set_hexpand(True)
        self.current_application_title.set_halign(Gtk.Align.CENTER)
        self.current_application_title.set_name("application-title")

        self.current_workspace_name = Gtk.Label()
        self.current_workspace_name.set_ellipsize(Pango.EllipsizeMode.END)
        self.current_workspace_name.set_max_width_chars(1)
        self.current_workspace_name.set_halign(Gtk.Align.END)
        self.current_workspace_name.set_name("workspace-name")

        self.workspace_stack = Gtk.Stack()
        self.workspace_stack.set_name("workspaces")
        self.workspace_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_UP_DOWN)
        self.workspace_stack.set_hhomogeneous(False)
        self.workspace_stack.set_interpolate_size(True)
        self.workspace_stack.set_halign(Gtk.Align.CENTER)

        title_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        title_bar.append(self.current_application_title)
        title_bar.append(self.current_workspace_name)
        title_bar.set_hexpand(True)
        title_bar.set_name("top-bar")
        switcher_view = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        switcher_view.set_name("main-view")
        switcher_view.set_halign(Gtk.Align.CENTER)
        switcher_view.set_valign(Gtk.Align.CENTER)
        switcher_view.append(title_bar)
        switcher_view.append(self.workspace_stack)

        self.workspace_indicators = WorkspaceIndicatorsView()

        inner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        inner_box.append(self.workspace_indicators)
        inner_box.append(switcher_view)

        self.set_child(inner_box)
        self.set_decorated(False)
        self.set_modal(True)
        self.set_resizable(False)
        self.set_name("niriswitcher")
        self.set_default_size(-1, 100)
        self.current_application = None

        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-released", on_key_release, self)
        key_controller.connect("key-pressed", on_press_key, self)
        self.add_controller(key_controller)
        self.connect("map", self.on_map)
        self.connect("show", self.on_show)
        self.connect("hide", self.on_hide)

        self._actions = None

    def on_map(self, window):
        surface = self.get_surface()
        surface.inhibit_system_shortcuts(None)

    def get_actions(self):
        if self._actions is None:
            self._actions = [
                KeybindingAction(self.config.keys.next, self.select_next_application),
                KeybindingAction(self.config.keys.prev, self.select_prev_application),
                KeybindingAction(self.config.keys.abort, self.hide),
                KeybindingAction(self.config.keys.close, self.close_selected_window),
                KeybindingAction(
                    self.config.keys.next_workspace, self.select_next_workspace
                ),
                KeybindingAction(
                    self.config.keys.prev_workspace, self.select_prev_workspace
                ),
            ]
            self._actions.sort(key=operator.attrgetter("mod_count"), reverse=True)

        return self._actions

    def on_hide(self, widget):
        self.window_manager.disconnect("window-closed")
        self.window_manager.disconnect("window-focus-changed")
        self.window_manager.disconnect("workspace-activated")
        for child in list(self.workspace_stack):
            self.workspace_stack.remove(child)

        for child in list(self.workspace_indicators):
            self.workspace_indicators.remove(child)

        self.current_application = None

    def on_show_windows_from_all_workspaces(self, screen_width):
        windows = self.window_manager.get_windows(active_workspace=False)
        workspace_view = WorkspaceView(
            self,
            None,
            windows,
            max_size=min(self.config.general.max_width, screen_width),
            icon_size=self.config.general.icon_size,
        )
        self.workspace_indicators.set_visible(False)
        self.current_workspace_name.set_visible(False)
        self.workspace_stack.add_named(workspace_view, "all")
        init = self.workspace_stack.get_visible_child().get_initial_selection()
        if init is not None:
            self.select_application(init)
            self.window_manager.connect(
                "window-closed", on_window_closed, self.workspace_stack, self
            )
            self.window_manager.connect(
                "window-focus-changed", on_window_focus_changed, self
            )

    def on_show_windows_from_active_workspace(self, screen_width):
        self.workspace_indicators.set_visible(True)
        self.current_workspace_name.set_visible(True)
        for workspace in self.window_manager.get_workspaces():
            windows = self.window_manager.get_windows(workspace_id=workspace.id)
            if len(windows) > 0:
                workspace_view = WorkspaceView(
                    self,
                    workspace,
                    windows,
                    min(self.config.general.max_width, screen_width),
                    self.config.general.icon_size,
                )
                self.workspace_stack.add_named(workspace_view, workspace.name)
                workspace_indicator = WorkspaceIndicatorView(workspace)
                gesture = Gtk.GestureClick.new()
                gesture.set_button(0)
                gesture.connect(
                    "pressed", on_workspace_indicator_pressed, workspace_indicator, self
                )
                workspace_indicator.add_controller(gesture)

                self.workspace_indicators.append(workspace_indicator)

        active_workspace = self.window_manager.get_active_workspace()
        workspace_view = self.workspace_stack.get_child_by_name(active_workspace.name)
        if workspace_view is not None:
            self.current_workspace_name.set_label(active_workspace.name)
            self.workspace_stack.set_visible_child_full(
                active_workspace.name, Gtk.StackTransitionType.NONE
            )
            self.workspace_indicators.select_by_workspace_id(active_workspace.id)

            init = self.workspace_stack.get_visible_child().get_initial_selection()
            if init is not None:
                self.select_application(init)
                self.window_manager.connect(
                    "window-closed", on_window_closed, self.workspace_stack, self
                )
                self.window_manager.connect(
                    "workspace-activated",
                    on_workspace_activated,
                    self,
                )
                self.window_manager.connect(
                    "window-focus-changed", on_window_focus_changed, self
                )

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

        max_size = int(geometry.width * 0.9)
        if not self.config.general.active_workspace:
            self.on_show_windows_from_all_workspaces(max_size)
        else:
            self.on_show_windows_from_active_workspace(max_size)

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
        """
        Closes the window associated with the given application.

        Args:
            application: The application object whose window should be closed. It is expected to have a 'window' attribute with an 'id'.

        Returns:
            None
        """
        self.window_manager.close_window(application.window.id)

    def select_application(self, application):
        """
        Selects the specified application, deselecting the current one if
        necessary, and updates the UI accordingly.

        Args:
            application: The application object to be selected.
        """
        if self.current_application is not None:
            self.current_application.deselect()

        self.current_application = application
        self.current_application.select()
        self.current_application_title.set_label(self.current_application.window.title)
        self.workspace_stack.get_visible_child().scroll_to(self.current_application)

    def select_workspace(self, workspace_view):
        """
        Selects the specified workspace view, updates the current workspace label,
        displays the selected workspace, updates workspace indicators, and selects
        the first application in the workspace if available.

        Args:
            workspace_view: The workspace view to select. If None, no action is taken.
        """
        if workspace_view is not None:
            self.current_workspace_name.set_label(workspace_view.workspace.name)
            self.workspace_stack.set_visible_child(workspace_view)
            self.workspace_indicators.select_by_workspace_id(
                workspace_view.workspace.id
            )
            first_app = workspace_view.get_first_application_view()
            if first_app is not None:
                self.select_application(first_app)

    def select_next_application(self):
        """
        Selects the next application in the sequence. If there is no next sibling application,
        selects the first application view in the currently visible workspace.
        """
        next = self.current_application.get_next_sibling()
        if next is None:
            next = self.workspace_stack.get_visible_child().get_first_application_view()
        self.select_application(next)

    def select_prev_application(self):
        """
        Selects the previous application in the workspace stack. If there is no
        previous sibling application, selects the last application view in the
        currently visible workspace.
        """
        prev = self.current_application.get_prev_sibling()
        if prev is None:
            prev = self.workspace_stack.get_visible_child().get_last_application_view()
        self.select_application(prev)

    def select_next_workspace(self):
        """
        Selects the next workspace in the workspace stack.

        If there is no active workspace, the method returns immediately.
        Otherwise, it selects the next sibling workspace. If the current workspace
        is the last one, it wraps around and selects the first workspace.

        Returns:
            None
        """
        if not self.config.general.active_workspace:
            return

        current = self.workspace_stack.get_visible_child()
        next = current.get_next_sibling()
        if next is None:
            next = self.workspace_stack.get_first_child()
        self.select_workspace(next)

    def select_prev_workspace(self):
        """
        Selects the previous workspace in the workspace stack.

        If there is no currently active workspace, the method returns immediately.
        If the current workspace is the first in the stack, wraps around to the last workspace.

        """
        if not self.config.general.active_workspace:
            return

        current = self.workspace_stack.get_visible_child()
        prev = current.get_prev_sibling()
        if prev is None:
            prev = self.workspace_stack.get_last_child()
        self.select_workspace(prev)


class NiriswicherApp(Gtk.Application):
    def __init__(self):
        super().__init__()

    def do_activate(self):
        config = load_configuration()
        window_manager = NiriWindowManager()
        self.window = NiriswitcherWindow(self, config, window_manager)
        LayerShell.init_for_window(self.window)
        LayerShell.set_namespace(self.window, "niriswitcher")
        LayerShell.set_layer(self.window, LayerShell.Layer.TOP)
        LayerShell.auto_exclusive_zone_enable(self.window)
        LayerShell.set_keyboard_mode(self.window, LayerShell.KeyboardMode.EXCLUSIVE)


def main():
    load_and_initialize_styles()
    app = NiriswicherApp()

    def signal_handler(signum, frame):
        active_workspace = app.window.config.general.active_workspace
        n_windows = app.window.window_manager.get_n_windows(
            active_workspace=active_workspace
        )

        if n_windows > 0 and active_workspace or n_windows > 1 and not active_workspace:
            app.window.present()

    signal.signal(signal.SIGUSR1, signal_handler)
    app.register(None)
    app.run()
