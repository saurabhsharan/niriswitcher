Name:           niriswitcher
Version:        0.1.0
Release:        1%{?dist}
Summary:        Add your description here

License:        MIT
URL:            https://github.com/isaksamsten/niriswitcher
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-gobject
BuildRequires:  python3-hatchling
Requires:       python3-gobject
Requires:       niri
Requires:       gtk4-layer-shell
Requires:       gtk4

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
