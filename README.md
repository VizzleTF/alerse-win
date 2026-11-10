<p align="center">
  <img src="https://raw.githubusercontent.com/VizzleTF/alerse/main/artwork/alerse_256.png" width="120" alt="The Alerse icon">
</p>

<h1 align="center">Alerse for Windows</h1>

<p align="center">The Windows build of Alerse, a sidebar browser for people moving from Arc.</p>

[Alerse](https://github.com/VizzleTF/alerse) is built on
ungoogled-chromium. This repository builds the
[alerse](https://github.com/VizzleTF/alerse) patch series on top of
[ungoogled-chromium-windows](https://github.com/ungoogled-software/ungoogled-chromium-windows);
both are git submodules.

![Alerse on Windows: the Personal Space with pinned items, a Reading folder and favorites](https://raw.githubusercontent.com/VizzleTF/alerse/main/docs/images/windows.png)

## Features

The sidebar with Spaces that keep separate logins, pinned items in folders, favorites,
a command bar with Arc's actions, Split View, end-to-end encrypted sync to your own
server and import from Arc and other browsers: see
[Features](https://github.com/VizzleTF/alerse#features) and
[Differences from Arc](https://github.com/VizzleTF/alerse#differences-from-arc).

On Windows Alerse looks like Arc for macOS everywhere but the top of the window, which
keeps Arc for Windows' top bar with the window controls and the address, and the logo
menu in place of macOS' menu bar.

## Download

Open the [latest release](https://github.com/VizzleTF/alerse-win/releases/latest) and
download, under **Assets**, the file for your PC:

| File | What it is |
|---|---|
| `alerse_<tag>_installer_x64.exe` | Installer, Intel and AMD PCs |
| `alerse_<tag>_windows_x64.zip` | Portable: unpack anywhere and run `chrome.exe` |
| `alerse_<tag>_installer_arm64.exe`, `alerse_<tag>_windows_arm64.zip` | The same for Windows on Arm |
| `SHA256SUMS` | SHA-256 of every file in the release |

A release appears as soon as its first architecture is built, usually x64, and the other
one's files are added to it when they are ready, about a day apart; `SHA256SUMS` is
rewritten each time. To check a download in PowerShell:

```powershell
(Get-FileHash .\alerse_v0.1.8_installer_x64.exe).Hash  # compare with SHA256SUMS
```

The builds are not code-signed, so Windows SmartScreen asks for confirmation on first run
(**More info**, then **Run anyway**).

The installer puts Alerse in `%LOCALAPPDATA%\Alerse\Application` and its profile in
`%LOCALAPPDATA%\Alerse\User Data`, apart from any Chromium. An installation of a
release before 0.1.8 is taken over on the first start: its profile moves to Alerse's, and
a minute later its own uninstaller removes it, keeping your data; then pick Alerse as the
default browser in Windows' settings. See
[Name](https://github.com/VizzleTF/alerse/blob/main/docs/design.md#name).

Alerse does not update itself. When a newer release is out, the menu of the sidebar's
logo shows "Update to Alerse X.Y.Z", which opens the release; its installer installs
over a running Alerse, which takes the update on its next start.

## How releases are built

Pushing a tag runs [release.yml](.github/workflows/release.yml) on GitHub-hosted
runners. A full Chromium build takes longer than the 6 hours a job may run, so
[build.yml](.github/workflows/build.yml) chains up to 16 jobs per architecture: each runs
`build.py --ci -j 3` (4-core runners) until ninja's deadline, 280 minutes after the job
started, and passes the build tree to the next one; that leaves time to pack and upload
it within the job's 6 hours. A full build takes about 36 hours for x64 and 43 for arm64.
The job that finishes the build uploads the packages, the jobs after it do not start, and
[publish.yml](.github/workflows/publish.yml) adds them to the release right away, one
architecture at a time. If one architecture fails, the other is still published; re-run
the failed jobs to add it. Running the workflow by hand builds without publishing.

Releases are built with profile-guided optimization (PGO), as Chrome is: `build.py`
downloads the profile Chromium names in `chrome/build/win64.pgo.txt` (`win-arm64.pgo.txt`
for arm64) and checks it against the MD5 Google's storage gives; the build stops before
compiling if the profile is missing or `args.gn` does not end with `chrome_pgo_phase=2`,
and CI checks the finished build again before uploading it. Upstream turns PGO off
(`chrome_pgo_phase=0`); `build.py` turns it back on, with V8's builtins optimization. The
arm64 profile is Chromium's newest, not one for this exact version.

### Versions and tags

A release is tagged `v` + `alerse/VERSION`, the version of the core the submodule is
on: the build compiles that version into the browser and into its Chromium version number
(see [versioning](https://github.com/VizzleTF/alerse/blob/main/docs/versioning.md)), so a
release of this repository alone raises the core's `VERSION` too. That number must also be
above the latest release's: on the same Chromium the patch number keeps counting (0.1.7 is
followed by 0.2.8, not 0.2.0). The release workflow checks both first and fails before
building.

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
git clone --recurse-submodules https://github.com/VizzleTF/alerse-win.git
cd alerse-win
python build.py
```

The first build takes about 4 hours on a 2026 desktop. It downloads the PGO profile
(about 110 MB) on the way; `python build.py --no-pgo` builds without PGO. The browser is
`ungoogled-chromium-windows\build\src\out\Default\chrome.exe`, the installer
`mini_installer.exe` next to it.

`build.py` adds the Alerse patches and `alerse\flags.gn` to ungoogled-chromium-windows,
runs its build, and restores the submodule byte for byte afterwards. It does not build
chromedriver, which no package ships. Extra arguments go to the upstream `build.py`. `python build.py --pgo-check` checks that an existing tree is
configured with PGO and has its profile.

### Resume or rebuild

| Situation | Command |
|---|---|
| The build failed after unpacking and patching | `python build.py --ci` (skips finished stages; stops after 3.5 h, run it again to continue) |
| Rebuild after changing a patch in the working tree | `ninja` below; no administrator rights needed |

```cmd
set PATH=%CD%\ungoogled-chromium-windows\build\src\out\Default;%PATH%
cd ungoogled-chromium-windows\build\src
third_party\ninja\ninja.exe -C out\Default chrome mini_installer
```

`out\Default` goes first on `PATH` because V8's build looks up `gn.exe` there.

## Common build errors

| Error | Cause | Fix |
|---|---|---|
| `python3 resolves to ...WindowsApps...` | The Windows Store alias for `python3` | Copy `python.exe` to `python3.exe` in your Python directory; put it first on `PATH` |
| `Python clang bindings not found` | V8 needs libclang bindings | `pip install clang`, delete `out\Default`, run `python build.py --ci` |
| `[metagen] gn not found` | `gn.exe` is not on `PATH` | Add `out\Default` to `PATH` as above |
| Creating symlinks fails while unpacking | Symlinks need administrator rights or Developer Mode | Run the first build as administrator |
| `AssertionError` in `midl.py` after a version change | Empty `.tlb` files left in `third_party\win_build_output\midl` | Delete the empty `.tlb` files there and run ninja again |
| DevTools opens blank | The tree was built through a junction or another path spelling | Build from the tree's real path; see [patching](https://github.com/VizzleTF/alerse/blob/main/docs/patching.md#building-through-a-junction) |

## Change the patches

Patches live in the `alerse` submodule; see
[Writing and refreshing patches](https://github.com/VizzleTF/alerse/blob/main/docs/patching.md).

## License

BSD-3-Clause.
