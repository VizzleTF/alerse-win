# Arcomium for Windows

Windows builds of [Arcomium](https://github.com/VizzleTF/arcomium), an Arc-style browser
on ungoogled-chromium. This repository builds the
[arcomium](https://github.com/VizzleTF/arcomium) patch series on top of
[ungoogled-chromium-windows](https://github.com/ungoogled-software/ungoogled-chromium-windows);
both are git submodules.

## Download

Installers and portable zips for x64 and arm64 are on the
[Releases](https://github.com/VizzleTF/arcomium-win/releases) page, with `SHA256SUMS`.
The builds are not code-signed, so Windows SmartScreen asks for confirmation on first run.

## How releases are built

Pushing a tag `v*` runs [release.yml](.github/workflows/release.yml) on GitHub-hosted
runners. A full Chromium build takes longer than the 6 hours a job may run, so
[build.yml](.github/workflows/build.yml) chains up to 16 jobs: each runs `build.py --ci`
until it times out and passes the build tree to the next one. The last job publishes the
packages. Running the workflow by hand builds without publishing.

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

The first build takes about 4 hours on a 2026 desktop. The browser is
`ungoogled-chromium-windows\build\src\out\Default\chrome.exe`, the installer
`mini_installer.exe` next to it.

`build.py` adds the Arcomium patches and `arcomium\flags.gn` to ungoogled-chromium-windows,
runs its build, and restores the submodule afterwards. Extra arguments go to the
upstream `build.py`.

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
