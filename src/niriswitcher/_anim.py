import logging
import math

from gi.repository import Gtk

logger = logging.getLogger(__name__)


def ease_in_cubic(t):
    """
    Cubic ease-in.

    Args:
        t (float): Normalized time [0, 1].

    Returns:
        float: The eased value.
    """
    return t * t * t


def ease_in_out_cubic(t):
    """
    Applies an ease-in-out cubic interpolation to the input value.

    This function is typically used for smooth transitions in animations,
    providing acceleration until halfway, then deceleration.

    Args:
        t (float): A value between 0 and 1 representing the normalized time.

    Returns:
        float: The interpolated value after applying the ease-in-out cubic function.
    """
    if t < 0.5:
        return 4 * t * t * t
    else:
        return 1 - pow(-2 * t + 2, 3) / 2


def ease_out_cubic(t):
    """
    Eases a value using the cubic ease-out function.

    This function interpolates the input value `t` (typically in the range [0,
    1]) using a cubic ease-out curve, which starts quickly and slows down
    towards the end.

    Args:
        t (float): The interpolation parameter, usually between 0 and 1.

    Returns:
        float: The eased value.
    """
    return 1 - pow(1 - t, 3)


def linear(t):
    """
    Linear interpolation (no easing).

    Args:
        t (float): Normalized time [0, 1].

    Returns:
        float: The interpolated value.
    """
    return t


def ease_in_quad(t):
    """
    Quadratic ease-in.

    Args:
        t (float): Normalized time [0, 1].

    Returns:
        float: The eased value.
    """
    return t * t


def ease_out_quad(t):
    """
    Quadratic ease-out.

    Args:
        t (float): Normalized time [0, 1].

    Returns:
        float: The eased value.
    """
    return 1 - (1 - t) * (1 - t)


def ease_in_out_quad(t):
    """
    Quadratic ease-in-out.

    Args:
        t (float): Normalized time [0, 1].

    Returns:
        float: The eased value.
    """
    if t < 0.5:
        return 2 * t * t
    else:
        return 1 - pow(-2 * t + 2, 2) / 2


def ease_in_quart(t):
    """
    Quartic ease-in.

    Args:
        t (float): Normalized time [0, 1].

    Returns:
        float: The eased value.
    """
    return t * t * t * t


def ease_out_quart(t):
    """
    Quartic ease-out.

    Args:
        t (float): Normalized time [0, 1].

    Returns:
        float: The eased value.
    """
    return 1 - pow(1 - t, 4)


def ease_in_out_quart(t):
    """
    Quartic ease-in-out.

    Args:
        t (float): Normalized time [0, 1].

    Returns:
        float: The eased value.
    """
    if t < 0.5:
        return 8 * t * t * t * t
    else:
        return 1 - pow(-2 * t + 2, 4) / 2


def ease_in_quint(t):
    """
    Quintic ease-in.

    Args:
        t (float): Normalized time [0, 1].

    Returns:
        float: The eased value.
    """
    return t * t * t * t * t


def ease_out_quint(t):
    """
    Quintic ease-out.

    Args:
        t (float): Normalized time [0, 1].

    Returns:
        float: The eased value.
    """
    return 1 - pow(1 - t, 5)


def ease_in_out_quint(t):
    """
    Quintic ease-in-out.

    Args:
        t (float): Normalized time [0, 1].

    Returns:
        float: The eased value.
    """
    if t < 0.5:
        return 16 * t * t * t * t * t
    else:
        return 1 - pow(-2 * t + 2, 5) / 2


def ease_in_sine(t):
    """
    Sine ease-in.

    Args:
        t (float): Normalized time [0, 1].

    Returns:
        float: The eased value.
    """

    return 1 - math.cos((t * math.pi) / 2)


def ease_out_sine(t):
    """
    Sine ease-out.

    Args:
        t (float): Normalized time [0, 1].

    Returns:
        float: The eased value.
    """

    return math.sin((t * math.pi) / 2)


def ease_in_out_sine(t):
    """
    Sine ease-in-out.

    Args:
        t (float): Normalized time [0, 1].

    Returns:
        float: The eased value.
    """

    return -(math.cos(math.pi * t) - 1) / 2


def ease_in_expo(t):
    """
    Exponential ease-in.

    Args:
        t (float): Normalized time [0, 1].

    Returns:
        float: The eased value.
    """
    if t == 0:
        return 0
    return pow(2, 10 * t - 10)


def ease_out_expo(t):
    """
    Exponential ease-out.

    Args:
        t (float): Normalized time [0, 1].

    Returns:
        float: The eased value.
    """
    if t == 1:
        return 1
    return 1 - pow(2, -10 * t)


def ease_in_out_expo(t):
    """
    Exponential ease-in-out.

    Args:
        t (float): Normalized time [0, 1].

    Returns:
        float: The eased value.
    """
    if t == 0:
        return 0
    if t == 1:
        return 1
    if t < 0.5:
        return pow(2, 20 * t - 10) / 2
    else:
        return (2 - pow(2, -20 * t + 10)) / 2


def ease_in_circ(t):
    """
    Circular ease-in.

    Args:
        t (float): Normalized time [0, 1].

    Returns:
        float: The eased value.
    """

    return 1 - math.sqrt(1 - t * t)


def ease_out_circ(t):
    """
    Circular ease-out.

    Args:
        t (float): Normalized time [0, 1].

    Returns:
        float: The eased value.
    """

    return math.sqrt(1 - pow(t - 1, 2))


def ease_in_out_circ(t):
    """
    Circular ease-in-out.

    Args:
        t (float): Normalized time [0, 1].

    Returns:
        float: The eased value.
    """

    if t < 0.5:
        return (1 - math.sqrt(1 - pow(2 * t, 2))) / 2
    else:
        return (math.sqrt(1 - pow(-2 * t + 2, 2)) + 1) / 2


def ease_in_back(t):
    """
    Back ease-in.

    Args:
        t (float): Normalized time [0, 1].

    Returns:
        float: The eased value.
    """
    c1 = 1.70158
    c3 = c1 + 1
    return c3 * t * t * t - c1 * t * t


def ease_out_back(t):
    """
    Back ease-out.

    Args:
        t (float): Normalized time [0, 1].

    Returns:
        float: The eased value.
    """
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)


def ease_in_out_back(t):
    """
    Back ease-in-out.

    Args:
        t (float): Normalized time [0, 1].

    Returns:
        float: The eased value.
    """
    c1 = 1.70158
    c2 = c1 * 1.525
    if t < 0.5:
        return (pow(2 * t, 2) * ((c2 + 1) * 2 * t - c2)) / 2
    else:
        return (pow(2 * t - 2, 2) * ((c2 + 1) * (t * 2 - 2) + c2) + 2) / 2


EASING_FUNCTIONS = {
    "linear": linear,
    "ease-in-quad": ease_in_quad,
    "ease-out-quad": ease_out_quad,
    "ease-in-out_quad": ease_in_out_quad,
    "ease-in-cubic": ease_in_cubic,
    "ease-out-cubic": ease_out_cubic,
    "ease-in-out-cubic": ease_in_out_cubic,
    "ease-in-quart": ease_in_quart,
    "ease-out-quart": ease_out_quart,
    "ease-in-out-quart": ease_in_out_quart,
    "ease-in-quint": ease_in_quint,
    "ease-out-quint": ease_out_quint,
    "ease-in-out-quint": ease_in_out_quint,
    "ease-in-sine": ease_in_sine,
    "ease-out-sine": ease_out_sine,
    "ease-in-out-sine": ease_in_out_sine,
    "ease-in-expo": ease_in_expo,
    "ease-out-expo": ease_out_expo,
    "ease-in-out-expo": ease_in_out_expo,
    "ease-in-circ": ease_in_circ,
    "ease-out-circ": ease_out_circ,
    "ease-in-out-circ": ease_in_out_circ,
    "ease-in-back": ease_in_back,
    "ease-out-back": ease_out_back,
    "ease-in-out-back": ease_in_out_back,
}


def get_easing_function(name, *, default):
    if func := EASING_FUNCTIONS.get(name):
        return func
    else:
        logger.error(
            f"Unknown easing function: {name!r}. "
            f"Available options: {', '.join(EASING_FUNCTIONS.keys())}",
        )
        return default


def get_transition_function(name):
    if name == "slide":
        return Gtk.StackTransitionType.SLIDE_UP_DOWN
    elif name == "over":
        return Gtk.StackTransitionType.OVER_UP_DOWN
    elif name == "crossfade":
        return Gtk.StackTransitionType.CROSSFADE
    else:
        logger.error(
            f"Unknown trainstion function: {name!r}. "
            f"Available options: slide, over, crossfade"
        )
        return Gtk.StackTransitionType.SLIDE_UP_DOWN
