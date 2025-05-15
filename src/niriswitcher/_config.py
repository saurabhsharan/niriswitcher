import configparser
import os
import importlib
import importlib.resources
from gi.repository import Gtk, Gdk
from dataclasses import dataclass


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


@dataclass
class Config:
    general: GeneralConfig
    keys: KeysConfig


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


config = load_configuration()
load_and_initialize_styles()
