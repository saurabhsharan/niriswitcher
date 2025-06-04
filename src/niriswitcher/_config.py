import importlib
import importlib.resources
import logging
import os
from dataclasses import dataclass

import tomllib
from gi.repository import Gtk, Gdk

from ._anim import (
    ease_in_out_cubic,
    ease_out_cubic,
    get_easing_function,
    get_transition_function,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARN)


@dataclass(frozen=True)
class GeneralConfig:
    separate_workspaces: bool = True
    workspace_mru_sort: bool = True
    double_click_to_hide: bool = False
    center_on_focus: bool = False
    log_level: str = "WARN"


@dataclass(frozen=True)
class KeysConfig:
    modifier: int = Gdk.KEY_Alt_L
    next: (int, int) = (Gdk.KEY_Tab, Gdk.ModifierType.ALT_MASK)
    prev: (int, int) = (
        Gdk.KEY_Tab,
        Gdk.ModifierType.ALT_MASK | Gdk.ModifierType.SHIFT_MASK,
    )
    close: (int, int) = (Gdk.KEY_q, Gdk.ModifierType.ALT_MASK)
    abort: (int, int) = (Gdk.KEY_Escape, Gdk.ModifierType.ALT_MASK)
    next_workspace: (int, int | None) = (
        Gdk.KEY_grave,
        Gdk.ModifierType.ALT_MASK,
    )
    prev_workspace: (int, int) = (
        Gdk.KEY_asciitilde,
        Gdk.ModifierType.ALT_MASK | Gdk.ModifierType.SHIFT_MASK,
    )


@dataclass(frozen=True)
class ResizeAnimationConfig:
    duration: int = 200
    easing: callable = ease_out_cubic


@dataclass(frozen=True)
class SwitchAnimationConfig:
    duration: int = 200
    easing: callable = ease_in_out_cubic


@dataclass(frozen=True)
class WorkspaceAnimationConfig:
    duration: int = 200
    transition: Gtk.StackTransitionType = Gtk.StackTransitionType.SLIDE_UP_DOWN


@dataclass(frozen=True)
class ActivateAnimationConfig:
    hide_duration: int = 200
    show_duration: int = 200
    easing: callable = ease_out_cubic


@dataclass(frozen=True)
class AnimationConfig:
    resize: ResizeAnimationConfig = ResizeAnimationConfig()
    switch: SwitchAnimationConfig = SwitchAnimationConfig()
    workspace: WorkspaceAnimationConfig = WorkspaceAnimationConfig()
    activate: ActivateAnimationConfig = ActivateAnimationConfig()


@dataclass(frozen=True)
class AppearanceConfig:
    icon_size: int = 128
    max_width: int = 800
    min_width: int = 600
    animation: AnimationConfig = AnimationConfig()
    system_theme: str = "dark"  # auto, light
    workspace_format: str = "{output}-{idx}"


@dataclass(frozen=True)
class Config:
    general: GeneralConfig = GeneralConfig()
    keys: KeysConfig = KeysConfig()
    appearance: AppearanceConfig = AppearanceConfig()


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


def load_configuration(config_path: str = None) -> Config:
    config_home = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    config_dir = os.path.join(config_home, "niriswitcher")
    if config_path is None:
        config_path = os.path.join(config_dir, "config.toml")
    if os.path.isfile(config_path):
        try:
            with open(config_path, "rb") as f:
                config = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            logger.warning(f"Error parsing config file {config_path!r}: {e}")
            return Config()
    else:
        config = {}

    separate_workspaces = config.get("separate_workspaces", True)
    double_click_to_hide = config.get("double_click_to_hide", False)
    center_on_focus = config.get("center_on_focus", False)
    workspace_mru_sort = config.get("workspace_mru_sort", False)
    log_level = config.get("log_level", "WARN")
    if log_level not in ("WARN", "INFO", "DEBUG", "ERROR"):
        log_level = "DEBUG"

    general = GeneralConfig(
        separate_workspaces=separate_workspaces,
        double_click_to_hide=double_click_to_hide,
        center_on_focus=center_on_focus,
        workspace_mru_sort=workspace_mru_sort,
        log_level=log_level,
    )

    keys_section = config.get("keys", {})
    modifier = parse_modifier_key(keys_section.get("modifier", "Alt_L"))
    modifier_mask = get_modifier_as_mask(modifier)

    switch_section = keys_section.get("switch", {})
    window_section = keys_section.get("window", {})
    workspace_section = keys_section.get("workspace", {})

    next_key = switch_section.get("next", "Tab")
    prev_key = switch_section.get("prev", "Shift+Tab")
    close_key = window_section.get("close", "q")
    abort_key = window_section.get("abort", "Escape")
    next_workspace_key = workspace_section.get("next", "grave")
    prev_workspace_key = workspace_section.get("prev", "Shift+asciitilde")

    keys = KeysConfig(
        modifier=modifier,
        next=parse_accelerator_key(next_key, modifier_mask),
        prev=parse_accelerator_key(prev_key, modifier_mask),
        close=parse_accelerator_key(close_key, modifier_mask),
        abort=parse_accelerator_key(abort_key, modifier_mask),
        next_workspace=parse_accelerator_key(next_workspace_key, modifier_mask),
        prev_workspace=parse_accelerator_key(prev_workspace_key, modifier_mask),
    )

    appearance_section = config.get("appearance", {})
    appearance_icon_size = appearance_section.get("icon_size", 128)
    appearance_max_width = appearance_section.get("max_width", 800)
    appearance_min_width = appearance_section.get("min_width", 600)
    appearance_system_theme = appearance_section.get("system_theme", "dark")
    if appearance_system_theme not in ("light", "dark", "auto"):
        logger.warning(
            "appearance.system_theme is set to %s (valid options "
            "are 'light', 'dark' or 'auto')"
        )
        appearance_system_theme = "auto"

    appearance_workspace_format = appearance_section.get(
        "workspace_format", "{output}-{idx}"
    )

    animation_section = appearance_section.get("animation", {})
    resize_section = animation_section.get("resize", {})
    switch_section = animation_section.get("switch", {})
    workspace_section = animation_section.get("workspace", {})
    hide_section = animation_section.get("hide", {})
    reveal_section = animation_section.get("reveal", {})

    resize_animation = ResizeAnimationConfig(
        duration=resize_section.get("duration", 200),
        easing=get_easing_function(resize_section.get("easing", "ease-out-cubic")),
    )
    switch_animation = SwitchAnimationConfig(
        duration=switch_section.get("duration", 200),
        easing=get_easing_function(switch_section.get("easing", "ease-in-out-cubic")),
    )
    workspace_animation = WorkspaceAnimationConfig(
        duration=workspace_section.get("duration", 200),
        transition=get_transition_function(
            workspace_section.get("transition", "slide")
        ),
    )

    duration = 200
    easing = "ease-out-cubic"
    if len(hide_section) > 0:
        logger.warning(
            "The configuration option appearance.animation.hide has been "
            "renamed to reveal, with show_duration and hide_duration. "
            "Support for hide will be removed in 1.0.",
        )
        duration = hide_section.get("duration", 200)
        easing = hide_section.get("easing", "ease-out-cubic")

    reveal_animation = ActivateAnimationConfig(
        show_duration=reveal_section.get("show_duration", duration),
        hide_duration=reveal_section.get("hide_duration", duration),
        easing=get_easing_function(reveal_section.get("easing", easing)),
    )
    animation = AnimationConfig(
        resize=resize_animation,
        switch=switch_animation,
        workspace=workspace_animation,
        activate=reveal_animation,
    )

    appearance = AppearanceConfig(
        icon_size=appearance_icon_size,
        max_width=appearance_max_width,
        min_width=appearance_min_width,
        animation=animation,
        system_theme=appearance_system_theme,
        workspace_format=appearance_workspace_format,
    )

    return Config(general=general, keys=keys, appearance=appearance)


def load_system_style(filename="style.css", priority=0):
    with (
        importlib.resources.files("niriswitcher.resources")
        .joinpath(filename)
        .open("rb") as f
    ):
        provider = Gtk.CssProvider()
        css_data = f.read()
        provider.load_from_data(css_data)
        return provider


def load_user_style(filename="style.css"):
    config_home = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    user_css_path = os.path.join(config_home, "niriswitcher", filename)
    if os.path.isfile(user_css_path):
        with open(user_css_path, "rb") as f:
            user_provider = Gtk.CssProvider()
            css_data = f.read()
            user_provider.load_from_data(css_data)
            return user_provider
    return None


DEFAULT_CSS_PROVIDER = load_system_style(filename="style.css")
DEFAULT_DARK_CSS_PROVIDER = load_system_style(filename="style-dark.css")

DEFAULT_USER_CSS_PROVIDER = load_user_style(filename="style.css")
DEFAULT_DARK_USER_CSS_PROVIDER = load_user_style(filename="style-dark.css")

config: Config = load_configuration()
logging.basicConfig(level=config.general.log_level)
