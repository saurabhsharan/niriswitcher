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
