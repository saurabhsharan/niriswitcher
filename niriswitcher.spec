%define version 0.7.1

Name:           niriswitcher
Version:        %{version}
Release:        1%{?dist}
Summary:        An application switcher for niri

License:        MIT
URL:            https://github.com/isaksamsten/niriswitcher
Source0:        %{url}/archive/%{version}/%{name}-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-gobject
BuildRequires:  python3-hatchling
BuildRequires:  python3-pip
Requires:       python3-gobject
Requires:       niri
Requires:       gtk4-layer-shell
Requires:       gtk4
Requires:       libadwaita

%description
An application switcher for niri.

%prep
%autosetup -n %{name}-%{version}

%build
%pyproject_wheel

%install
%pyproject_install

%files
%license LICENSE
%doc README.md
%{_bindir}/niriswitcher
%{_bindir}/niriswitcherctl
%{python3_sitelib}/niriswitcher*

%changelog
* Wed Aug 13 Isak Samsten <isak@samsten.se> - 0.7.1-1
- Fix a bug where MRU order was incorrect while using the overview.

* Mon June 16 Isak Samsten <isak@samsten.se> - 0.7.0-1
- Add option to show windows/workspaces from current output only
- Add number key workspace switching via keybindings
- Correctly select the most recently used application if separate_workspaces=false
- Unless separate workspaces are enabled, display the current workspace name
  when an application is selected
- Refactor app info lookup with fallback to more reliably detect applications

* Wed June 5 Isak Samsten <isak@samsten.se> - 0.6.1-1
- Fix transparent background on some Gtk themes.

* Wed June 5 Isak Samsten <isak@samsten.se> - 0.6.0-1
- Improve logging and warn if the application is already running
- Improve error message from config-parser
- Don't trigger a workspace change event if the workspace does not change
- Add support for configuring the workspace label
- Properly terminate Niriswitcher if we can't connect to NIRI_SOCKET
- Drop the use of threads and instead schedule socket operations on the Gtk
  event loop
- Enable support for controlling niriswitcher through DBus
- Add a command `niriswitcherctl` to show niriswitcher. For example,
  `niriswitcherctl show --window` opens niriswitcher with the (second)
  most recently focused window (respecting general.separate_workspaces)
  and `niriswitcherctl show --workspace` which selects the most recently
  used application from the (second) most recently used workspace.
- Enable support for starting niriswitcher with the second most recently
  used workspace selected.
- Support sorting workspace in most recently used order instead of index
  order.
- Correctly select the most recently used application when changing
  workspace.
- Make both the show and hide animation duration configurable. Deprecate
  appearance.animation.hide in favour of appearance.animation.reveal which has
  both show_duration and hide_duration. The appearance.animation.hide
  configuration shows a warning for now but will be removed in 1.0
- Two new configuration options:
  - `workspace.mru_sort_in_workspace`: sort the workspaces in MRU when
    starting by showing the most recent window.
  - `workspace.mru_sort_across_workspace`: sort the workspaces in MRU when
    starting by showing the most recent window in the most recent
    workspace.

* Thu May 22 Isak Samsten <isak@samsten.se> - 0.5.2-1
- Fix a regression in the reveal animation

* Wed May 21 Isak Samsten <isak@samsten.se> - 0.5.1-1
- Fix a bug where system_theme=auto would not automatically switch theme

* Wed May 21 Isak Samsten <isak@samsten.se> - 0.5.0-1
- Add support for automatic color theme
- Improve default window shadow
- Make the urgency animation smoother
- Add configuration option to center on focus
- Make focus and close methods on Window
- Avoid broken pipe error messages in Niri
- Fix a bug where workspace_id could be None

* Tue May 20 2025 Isak Samsten <isak@samsten.se> - 0.4.0-1
- Update default theme
- Ensure that we don't have circular dependencies
- Support urgency hints for applications
- Ensure that window window title is centered
- Add support for window-opened events
- Add support for urgency changes
- Allow NiriswitcherApp to listen to events from the window manager
- Fix an issue where app_id would be None

* Fri May 16 2025 Isak Samsten <isak@samsten.se> - 0.3.1-1
- Fix not opening on workspaces with no windows when separate_workspaces=false

* Fri May 16 2025 Isak Samsten <isak@samsten.se> - 0.3.2-1
- Fix debug colors in default css

* Fri May 16 2025 Isak Samsten <isak@samsten.se> - 0.3.3-1
- Fix debug colors in default css (another)

* Fri May 16 2025 Isak Samsten <isak@samsten.se> - 0.3.0-1
- Change configuration format from .ini to .toml
- Add configurable easing and transitions for animations
- Add configurable animation duration
- Add configurable min_width
- Fix a division by zero bug in GenericTransition

* Thu May 15 2025 Isak Samsten <isak@samsten.se> - 0.2.0-1
- Implement workspace switching with new keybindings and UI indicators
- Redesign window and application views for multi-workspace support
- Smooth animations when showing/hiding the switcher
- Enable support for multiple monitors showing the switcher on the
currently active output.

* Tue May 13 2025 Isak Samsten <isak@samsten.se> - 0.1.2-1
- Fix a bug where the default keybindings would be incorrectly set if no keys
section is present in the configuration file

* Tue May 13 2025 Isak Samsten <isak@samsten.se> - 0.1.1-1
- Fix incorrect configuration data type gh:#5

* Mon May 12 2025 Isak Samsten <isak@samsten.se> - 0.1.0-1
- Initial release

