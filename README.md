# Arcomium for Windows

Windows builds of [Arcomium](https://github.com/VizzleTF/arcomium), an Arc-style browser
on ungoogled-chromium. This repository builds the
[arcomium](https://github.com/VizzleTF/arcomium) patch series on top of
[ungoogled-chromium-windows](https://github.com/ungoogled-software/ungoogled-chromium-windows);
both are git submodules.

![Arcomium on Windows](https://raw.githubusercontent.com/VizzleTF/arcomium/main/docs/images/sidebar.png)

## Download

Open the [latest release](https://github.com/VizzleTF/arcomium-win/releases/latest) and
download, under **Assets**, the file for your PC:

| File | What it is |
|---|---|
| `arcomium_<tag>_installer_x64.exe` | Installer, Intel and AMD PCs |
| `arcomium_<tag>_windows_x64.zip` | Portable: unpack anywhere and run `chrome.exe` |
| `arcomium_<tag>_installer_arm64.exe`, `arcomium_<tag>_windows_arm64.zip` | The same for Windows on Arm |
| `SHA256SUMS` | SHA-256 of every file in the release |

A release appears as soon as its first architecture is built, usually x64, and the other
one's files are added to it when they are ready, about a day apart; `SHA256SUMS` is
rewritten each time. To check a download in PowerShell:

```powershell
(Get-FileHash .rcomium_v0.1.1_installer_x64.exe).Hash  # compare with SHA256SUMS
```

The builds are not code-signed, so Windows SmartScreen asks for confirmation on first run
(**More info**, then **Run anyway**).

## How releases are built

Pushing a tag runs [release.yml](.github/workflows/release.yml) on GitHub-hosted
runners. A full Chromium build takes longer than the 6 hours a job may run, so
[build.yml](.github/workflows/build.yml) chains up to 16 jobs per architecture: each runs
`build.py --ci` until its time is nearly up and passes the build tree to the next one.
The job that finishes the build uploads the packages, the jobs after it do not start, and
[publish.yml](.github/workflows/publish.yml) adds them to the release right away, one
architecture at a time. If one architecture fails, the other is still published; re-run
the failed jobs to add it. Running the workflow by hand builds without publishing.

Releases are built with profile-guided optimization (PGO), as Chrome is: `build.py`
downloads the profile Chromium names in `chrome/build/win64.pgo.txt` (`win-arm64.pgo.txt`
for arm64) and the build stops before compiling if the profile is missing or `args.gn`
does not end with `chrome_pgo_phase=2`.

### Versions and tags

Tags are `vMAJOR.MINOR.PATCH`, and only patch releases are tagged here. `arcomium/VERSION`
is the version of the core the submodule is on: a tag must have its `MAJOR.MINOR` and a
`PATCH` no lower than its, so with `VERSION` 0.1.0 the tags `v0.1.0`, `v0.1.1` and so on
are accepted and `v0.2.0` is not until the core moves to 0.2. The release workflow checks
this first and fails before building.

[dependabot](.github/dependabot.yml) proposes updates of the actions and submodules, and
[upstream.yml](.github/workflows/upstream.yml) opens an issue every time
ungoogled-chromium-windows releases a newer Chromium.

## Build from source

### Requirements

- Visual Studio 2026 (18.0), workload "Desktop development with C++", component "MFC/ATL"
- Windows SDK 10.0.28000 with "Debugging Tools for Windows"
- 7-Zip in `C:\Program Files\7-Zip`
- Python 3.11+ with `pip install clang`. The first Python directory on `PATH` must contain
  a `python3.exe` (a copy of `python.exe`): the WindowsApps `python3` alias breaks the build.
- Git, about 120 GB of free disk space

### Build

In "Developer Command Prompt for VS 2026", run as administrator (the build creates symlinks):

```cmd
git clone --recurse-submodules https://github.com/VizzleTF/arcomium-win.git
cd arcomium-win
python build.py
```

The first build takes about 4 hours on a 2026 desktop. It downloads the PGO profile
(about 110 MB) on the way; `python build.py --no-pgo` builds without PGO. The browser is
`ungoogled-chromium-windows\build\src\out\Default\chrome.exe`, the installer
`mini_installer.exe` next to it.

`build.py` adds the Arcomium patches and `arcomium\flags.gn` to ungoogled-chromium-windows,
runs its build, and restores the submodule byte for byte afterwards. Extra arguments go
to the upstream `build.py`. `python build.py --pgo-check` checks that an existing tree is
configured with PGO and has its profile.

### Resume or rebuild

| Situation | Command |
|---|---|
| The build failed after unpacking and patching | `python build.py --ci` (skips finished stages; stops after 3.5 h, run it again to continue) |
| Rebuild after changing a patch in the working tree | `ninja` below; no administrator rights needed |

```cmd
set PATH=%CD%\ungoogled-chromium-windows\build\src\out\Default;%PATH%
cd ungoogled-chromium-windows\build\src
third_party\ninja\ninja.exe -C out\Default chrome chromedriver mini_installer
```

`out\Default` goes first on `PATH` because V8's build looks up `gn.exe` there.

## Common build errors

| Error | Cause | Fix |
|---|---|---|
| `python3 resolves to ...WindowsApps...` | The Windows Store alias for `python3` | Copy `python.exe` to `python3.exe` in your Python directory; put it first on `PATH` |
| `Python clang bindings not found` | V8 needs libclang bindings | `pip install clang`, delete `out\Default`, run `python build.py --ci` |
| `[metagen] gn not found` | `gn.exe` is not on `PATH` | Add `out\Default` to `PATH` as above |
| Creating symlinks fails while unpacking | Symlinks need administrator rights or Developer Mode | Run the first build as administrator |

## Change the patches

Patches live in the `arcomium` submodule; see
[Writing and refreshing patches](https://github.com/VizzleTF/arcomium/blob/main/docs/patching.md).

## License

BSD-3-Clause.
