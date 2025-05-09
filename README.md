# niriswitcher

An application switcher for niri.

https://github.com/user-attachments/assets/775fd88c-9991-4692-a880-30d083304be9

## Installation

```bash
pipx install git+https://github.com/isaksamsten/niriswitcher.git
```

### Requirements

The following system packages:

- `python3-gobject`
- `python3-devel`
- `gtk4-layer-shell-devel`

These are the names of the packages on Fedora, but I'm sure they are
distributed for other distributions.

### Configuration

First we need to execute the `niriswitcher` application. The program is deamonized and waits for `USR1` signal to be shown. In the niri `config.kdl`-file we first start `niriswitcher` at startup:

```kdl
spawn-at-startup "~/.local/bin/niriswitcher"
```

Next, we add keybindings to send the `USR1` signal to `niriswitcher` on `Alt+Tab` and `Alt+Shift+Tab`.

```kdl
bind {
    Alt+Tab repeat=false { spawn "pkill" "-USR1" "niriswitcher"; }
    Alt+Shift+Tab repeat=false { spawn "pkill" "-USR1" "niriswitcher"; }
}
```

#### Keybindings

- `Alt+Tab` select next application
- `Alt+Shift+Tab` select previous application
- `Alt+Esc` close `niriswitcher` and do not focus
- `Alt+q` to close the selected application
- Release `Alt` to focus to currently selected application and close `niriswitcher`

#### Options

`niriswitcher` has a few options that we can change

- The icon size
- The maximum width of the switcher window (before scrolling)
- The scroll animation speed (set to 0 to disable)
- If single click change application without hiding the switcher (double
  clicking an application changes focus and hides the switcher)
- If only applications from the current workspace is visible

The configuration file is a simple `.ini` file in
`$XDG_CONFIG_HOME/niriswitcher/config.ini`. This is the default config:

```ini
[general]
icon_size = 128
scroll_animaton_duration = 500
max_width = 800
active_workspace = true
double_click_to_hide = false
```

We can also change/improve the style of the switcher using a `style.css` file
in the same configuration directory.

The following CSS-classes can be styled:

- `.niriswitcher-window`: the main window
- `.application-icon`: the icon
- `.application-title`: the title (above the icons)
- `.application-name`: the application name (below the icon)
- `.application-strip`: the area behind the icons (inside the scroll)
- `.application`: the application area (name + icon)
- `.application.selected`: the currently selected application (by keyboard or mouse)

Example (see `./src/niriswitcher/resources/style.css` for the default config):

To make the application title and selected application name red.

```css
.application-title {
  color: red;
}
.application.selected .application-name {
  color: red;
}
```

To make the application name visible for non-selected applications (but dimmed):

```css
.application-name {
  opacity: 1;
  color: rgba(255, 255, 255, 0.6);
}
.application.selected .application-name {
  color: rgba(255, 255, 255, 1);
}
```

# Known issues

If `Alt` is released before `niriswitcher` has been fully initialized, the window will not close unless the `Alt` key is pressed and released (to change to the next application) or `Esc` is pressed to close the window.
