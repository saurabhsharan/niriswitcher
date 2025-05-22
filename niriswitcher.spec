%define version 0.5.2

Name:           niriswitcher
Version:        %{version}
Release:        1%{?dist}
Summary:        Add your description here

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
%{python3_sitelib}/niriswitcher*

%changelog
* Mon May 12 2025 Isak Samsten <isak@samsten.se> - 0.1.0-1
- Initial release

* Thu May 13 2025 Isak Samsten <isak@samsten.se> - 0.1.1-1
- Fix incorrect configuration data type gh:#5

* Tue May 13 2025 Isak Samsten <isak@samsten.se> - 0.1.2-1
- Fix a bug where the default keybindings would be incorrectly set if no keys
section is present in the configuration file

* Thu May 15 2025 Isak Samsten <isak@samsten.se> - 0.2.0-1
- Implement workspace switching with new keybindings and UI indicators
- Redesign window and application views for multi-workspace support
- Smooth animations when showing/hiding the switcher
- Enable support for multiple monitors showing the switcher on the
currently active output.

* Fri May 16 2025 Isak Samsten <isak@samsten.se> - 0.3.0-1
- Change configuration format from .ini to .toml
- Add configurable easing and transitions for animations
- Add configurable animation duration
- Add configurable min_width
- Fix a division by zero bug in GenericTransition

* Fri May 16 2025 Isak Samsten <isak@samsten.se> - 0.3.1-1
- Fix not opening on workspaces with no windows when separate_workspaces=false

* Fri May 16 2025 Isak Samsten <isak@samsten.se> - 0.3.2-1
- Fix debug colors in default css

* Fri May 16 2025 Isak Samsten <isak@samsten.se> - 0.3.3-1
- Fix debug colors in default css (another)

* Tue May 20 2025 Isak Samsten <isak@samsten.se> - 0.4.0-1
- Update default theme
- Ensure that we don't have circular dependencies
- Support urgency hints for applications
- Ensure that window window title is centered
- Add support for window-opened events
- Add support for urgency changes
- Allow NiriswitcherApp to listen to events from the window manager
- Fix an issue where app_id would be None

* Wed May 21 Isak Samsten <isak@samsten.se> - 0.5.0-1
- Add support for automatic color theme
- Improve default window shadow
- Make the urgency animation smoother
- Add configuration option to center on focus
- Make focus and close methods on Window
- Avoid broken pipe error messages in Niri
- Fix a bug where workspace_id could be None

* Wed May 21 Isak Samsten <isak@samsten.se> - 0.5.1-1
- Fix a bug where system_theme=auto would not automatically switch theme

* Thu May 22 Isak Samsten <isak@samsten.se> - 0.5.2-1
- Fix a regression in the reveal animation
