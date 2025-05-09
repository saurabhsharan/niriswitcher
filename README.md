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

  # Known issues
  If `Alt` is released before `niriswitcher` has been fully initialized, the window will not close unless the `Alt` key is pressed and released (to change to the next application) or `Esc` is pressed to close the window.
