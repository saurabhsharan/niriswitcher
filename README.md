# niriswitcher

An application switcher for niri.

https://github.com/user-attachments/assets/775fd88c-9991-4692-a880-30d083304be9

## Installation

```bash
pipx install --system-site-packages git+https://github.com/isaksamsten/niriswitcher.git
```
> [!NOTE]
> You must use `--system-site-packages` to avoid having to build `pygobjects` from source.
> You also need to install the following system packages:
> - `python3-gobject`
> - `gtk4-layer-shell`
>
> These are the names of the packages on Fedora, but I'm sure they are
> distributed for other distributions.

For users of Fedora, I maintain a COPR built for every release.

[![Copr build status](https://copr.fedorainfracloud.org/coprs/isaksamsten/niriswitcher/package/niriswitcher/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/isaksamsten/niriswitcher/package/niriswitcher/) 

```bash
dnf copr enable isaksamsten/niriswitcher
dnf install niriswitcher
```

### Configuration

First we need to execute the `niriswitcher` application. The program is deamonized and waits for `USR1` signal to be shown. In the niri `config.kdl`-file we first start `niriswitcher` at startup:

```kdl
spawn-at-startup "niriswitcher"
```

> [!NOTE]
> Replace `niriswitcher` with `~/.local/bin/niriswitcher` if you installed using `pipx` and the binary is not on `$PATH`

Next, we add keybindings to send the `USR1` signal to `niriswitcher` on `Alt+Tab` and `Alt+Shift+Tab`.

```kdl
bind {
    Alt+Tab repeat=false { spawn "pkill" "-USR1" "niriswitcher"; }
    Alt+Shift+Tab repeat=false { spawn "pkill" "-USR1" "niriswitcher"; }
}
```

> [!NOTE]
> Remember to synchronize the keybinding set in Niri, with the one set for `niriswitcher`. For example, if you use `Mod+Tab` to trigger `niriswitcher` ensure that `modifier=Mod` in `config.ini` (see below).

#### Keybindings

By default, `niriswitcher` uses the following keybindings:

- `Alt+Tab` select next application
- `Alt+Shift+Tab` select previous application
- `Alt+Esc` close `niriswitcher` and do not focus
- `Alt+q` to close the selected application
- Release `Alt` to focus to currently selected application and close `niriswitcher`

The default mappings and modifier key can be configured in the `config.ini` file.

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

[keys]
modifier=Alt_L
next=Tab
prev=Shift+Tab
close=q
abort=Escape
```

The `modifier` key keeps `niriswitcher` active (once released, `niriswitcher`
is closed and the selected application activated). It's implicitly part of the
other key mappings, so in the default configuration `Alt+Tab` moves to the next
application, `Alt+Shift+Tab` to the previous, and so forth. To change the
modifier key, select another key among: `Alt`, `Super`, `Shift`, or `Control`.

The other bindings are expressed as bindings, e.g.,
`Shift+Tab` or `Control+j`. Note that `modifier` is implicit in all
bindings.

> [!WARNING]
> When using `Mod` or `Super` as the `modifier`, `niri` seems to inhibit
> `Super+Escape` reaching `niriswitcher`. Please select another binding for
> `abort`.

#### Themes
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

If `Alt` (the modifier key) is released before `niriswitcher` has been fully initialized, the window will not close unless the modifier key is pressed and released (to change to the next application) or `Esc` is pressed to close the window.
