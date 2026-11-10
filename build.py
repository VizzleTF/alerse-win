#!/usr/bin/env python3
"""Build Alerse for Windows: ungoogled-chromium-windows + Alerse patches.

Injects the patches of the alerse submodule into ungoogled-chromium-windows'
patch series, alerse/flags.gn into its GN flags and a step that copies
alerse/src and alerse/branding over the source tree after patching, runs the upstream
build.py, then restores the submodule byte for byte. Extra arguments go to the
upstream build.py.

The build is profile-guided (PGO), as Chrome's is: upstream turns PGO off for a
tarball build, since the tarball has no Windows profile, so this script turns it
back on and downloads the profile chrome/build/<target>.pgo.txt names.
`--no-pgo` builds without it.

    python build.py [--no-pgo] [upstream build.py arguments]
    python build.py --pgo-check [--arm|--x86]   # check an existing tree
"""

import base64
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UPSTREAM = ROOT / 'ungoogled-chromium-windows'
SOURCE_TREE = UPSTREAM / 'build' / 'src'
CORE = ROOT / 'alerse'
OUR_PATCHES = CORE / 'patches'
OUR_FLAGS = CORE / 'flags.gn'
OUR_BRANDING = CORE / 'branding'
OUR_SOURCES = CORE / 'src'

OUR_RENAME = CORE / 'tools' / 'rename_product.py'

# Inserted into the upstream build.py after its patches: Alerse's own source
# files and binary branding files are copied over the tree, not patched in, and
# renaming the product in the strings moves hundreds of translations, which a
# script does better than a patch. The script also numbers the release in
# chrome/VERSION from alerse/VERSION.
BRANDING_ANCHOR = '        # Substitute domains\n'
BRANDING_STEP = ('        shutil.copytree({sources!r}, source_tree, dirs_exist_ok=True)\n'
                 '        shutil.copytree({branding!r}, source_tree, dirs_exist_ok=True)\n'
                 '        subprocess.run([sys.executable, {rename!r}, str(source_tree)], check=True)\n'
                 '        get_logger().info("Copied Alerse sources and branding, renamed the product")\n')

# Upstream turns PGO off for tarball builds; Alerse keeps it on, together with
# V8's builtins PGO, whose profiles are in the tarball.
PGO_OFF = "        if args.tarball:\n            windows_flags += '\\nchrome_pgo_phase=0\\n'\n"
PGO_ON = ("        if args.tarball:\n"
          "            windows_flags += '\\nchrome_pgo_phase=2\\nv8_enable_builtins_optimization=true\\n'\n")
# After args.gn is written: download the profile and check args.gn, before gn gen.
ARGS_GN_ANCHOR = "        (source_tree / 'out/Default/args.gn').write_text(gn_flags, encoding=ENCODING)\n"
PGO_STEP = ("        subprocess.run([sys.executable, {script!r}, '--pgo-check']"
            " + (['--arm'] if args.arm else ['--x86'] if args.x86 else []), check=True)\n")

# CI: ninja stops at the deadline the stage sets in ALERSE_CI_DEADLINE (Unix
# time), so a stage builds as long as its 6 hours allow, whatever came before
# ninja; upstream's fixed 3.5 hours remain without it.
NINJA_TIMEOUT = 'timeout=3.5*60*60)'
NINJA_DEADLINE = ("timeout=(max(600.0, float(os.environ['ALERSE_CI_DEADLINE']) - time.time())"
                  " if os.environ.get('ALERSE_CI_DEADLINE') else 3.5*60*60))")
# No package ships chromedriver; building it costs a ThinLTO link per release.
CHROMEDRIVER = "    ninja_commandline.append('chromedriver')\n"

PGO_BUCKET = 'https://storage.googleapis.com/chromium-optimization-profiles/pgo_profiles/'
# The first bytes of an indexed LLVM profile (IndexedInstrProf::Magic, little-endian).
PROFDATA_MAGIC = b'\xfflprofi\x81'


def read_series(path):
    lines = path.read_text(encoding='utf-8').splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith('#')]


def text_of(raw):
    """The text of a file as bytes, with LF line ends whatever the checkout has."""
    return raw.decode('utf-8').replace('\r\n', '\n')


def write_lf(path, text):
    path.write_bytes(text.encode('utf-8'))


def replace_once(text, old, new, what):
    if text.count(old) != 1:
        sys.exit(f'upstream build.py changed: cannot add the {what}')
    return text.replace(old, new, 1)


def check_clean(upstream, paths):
    """Fails if an earlier run that was killed left its changes in `paths`.

    They would be taken for the upstream files and the patches added twice."""
    relative = [str(p.relative_to(upstream)) for p in paths]
    changed = subprocess.run(['git', '-C', str(upstream), 'status', '--porcelain', '--', *relative],
                             check=True, capture_output=True, text=True).stdout.strip()
    if changed:
        sys.exit(f'{upstream.name} has changes an interrupted build left:\n{changed}\n'
                 f'Restore them: git -C {upstream} checkout -- {" ".join(relative)}')


def check_python3():
    # GN resolves `python3` from PATH and bakes that path into every ninja rule.
    # The Windows Store / Python install manager alias breaks every script step.
    found = shutil.which('python3')
    if not found or 'WindowsApps' in found:
        sys.exit(f'python3 resolves to {found!r}. Put a real Python 3 directory '
                 'containing python3.exe (a copy of python.exe) first in PATH.')


def pgo_target(argv):
    return 'win-arm64' if '--arm' in argv else 'win32' if '--x86' in argv else 'win64'


def pgo_profile(source_tree, target):
    name = (source_tree / 'chrome' / 'build' / f'{target}.pgo.txt').read_text(
        encoding='utf-8').strip()
    return source_tree / 'chrome' / 'build' / 'pgo_profiles' / name


def is_profdata(path):
    if not path.is_file():
        return False
    with path.open('rb') as f:
        return f.read(len(PROFDATA_MAGIC)) == PROFDATA_MAGIC


def download_profile(url, dest):
    """Downloads a gzip-stored GCS object to dest, checked against its MD5."""
    part = dest.with_name(dest.name + '.part')
    # GCS stores the profiles gzip-compressed; take the stored bytes, which the
    # x-goog-hash MD5 covers, and unpack them here.
    request = urllib.request.Request(url, headers={'Accept-Encoding': 'gzip',
                                                   'User-Agent': 'alerse-build'})
    with urllib.request.urlopen(request, timeout=120) as response:
        hashes = ','.join(response.headers.get_all('x-goog-hash') or [])
        md5 = next((h.strip()[4:] for h in hashes.split(',') if h.strip().startswith('md5=')),
                   None)
        gzipped = response.headers.get('Content-Encoding', '') == 'gzip'
        inflate = zlib.decompressobj(zlib.MAX_WBITS | 16) if gzipped else None
        digest = hashlib.md5()
        with part.open('wb') as out:
            while chunk := response.read(1 << 20):
                digest.update(chunk)
                out.write(inflate.decompress(chunk) if inflate else chunk)
            if inflate:
                out.write(inflate.flush())
                if not inflate.eof:
                    raise OSError('the download ended inside the gzip stream')
    if md5 is None:
        print(f'warning: no MD5 for {url}; checking only the profile header', flush=True)
    elif base64.b64encode(digest.digest()).decode() != md5:
        part.unlink()
        raise OSError(f'MD5 mismatch for {url}')
    if not is_profdata(part):
        part.unlink()
        raise OSError(f'{url} is not an LLVM profile')
    os.replace(part, dest)


def fetch_pgo_profile(source_tree, target):
    profile = pgo_profile(source_tree, target)
    if not is_profdata(profile):
        profile.parent.mkdir(parents=True, exist_ok=True)
        url = PGO_BUCKET + profile.name
        for attempt in range(1, 6):
            print(f'Downloading the {target} PGO profile {profile.name} '
                  f'(attempt {attempt})', flush=True)
            try:
                download_profile(url, profile)
                break
            except OSError as e:
                print(f'PGO profile download failed: {e}', flush=True)
                time.sleep(30 * attempt)
        else:
            sys.exit(f'Could not download the PGO profile {url}. '
                     'Run build.py with --no-pgo to build without PGO.')
    # The tarball's Linux profile (330 MB) is no use here; dropping it keeps
    # it out of every CI stage's build-tree archive.
    for other in profile.parent.iterdir():
        if other.name not in (profile.name, profile.name + '.lock'):
            other.unlink()
    return profile


def pgo_check(source_tree, target, strict=True):
    """Fails unless args.gn ends up with chrome_pgo_phase=2 and has its profile.

    Downloads a missing profile. Not strict, it only warns about a tree that
    was configured without PGO."""
    args_gn = source_tree / 'out' / 'Default' / 'args.gn'
    phases = re.findall(r'^\s*chrome_pgo_phase\s*=\s*(\d+)', args_gn.read_text(encoding='utf-8'),
                        re.MULTILINE)
    phase = phases[-1] if phases else 'unset'
    if phase != '2':
        message = (f'{args_gn} sets chrome_pgo_phase={phase}, not 2: this tree builds '
                   'without PGO. Delete out\\Default to configure it again with PGO.')
        if strict:
            sys.exit(message)
        print(f'warning: {message}', flush=True)
        return
    profile = fetch_pgo_profile(source_tree, target)
    print(f'PGO: chrome_pgo_phase=2, profile {profile.name} '
          f'({profile.stat().st_size // 2**20} MB)', flush=True)


def main():
    argv = sys.argv[1:]
    if '--pgo-check' in argv:
        pgo_check(SOURCE_TREE, pgo_target(argv))
        return 0
    pgo = '--no-pgo' not in argv
    argv = [a for a in argv if a != '--no-pgo']

    check_python3()
    series = UPSTREAM / 'patches' / 'series'
    flags = UPSTREAM / 'flags.windows.gn'
    upstream_build = UPSTREAM / 'build.py'
    injected = UPSTREAM / 'patches' / 'alerse'
    check_clean(UPSTREAM, (series, flags, upstream_build))
    # Kept byte for byte: rewriting them as text would turn LF into CRLF here.
    originals = {p: p.read_bytes() for p in (series, flags, upstream_build)}

    try:
        if injected.exists():
            shutil.rmtree(injected)
        shutil.copytree(OUR_PATCHES, injected)
        ours = ['alerse/' + p for p in read_series(OUR_PATCHES / 'series')]
        write_lf(series, text_of(originals[series]).rstrip('\n') + '\n' + '\n'.join(ours) + '\n')
        if OUR_FLAGS.exists():
            write_lf(flags, text_of(originals[flags]).rstrip('\n') + '\n' +
                     text_of(OUR_FLAGS.read_bytes()))

        text = text_of(originals[upstream_build])
        if OUR_BRANDING.exists():
            if 'import shutil' not in text or 'import subprocess' not in text:
                sys.exit('upstream build.py changed: cannot add the branding step')
            step = BRANDING_STEP.format(sources=str(OUR_SOURCES), branding=str(OUR_BRANDING),
                                        rename=str(OUR_RENAME))
            text = replace_once(text, BRANDING_ANCHOR, step + BRANDING_ANCHOR, 'branding step')
        if pgo:
            text = replace_once(text, PGO_OFF, PGO_ON, 'PGO flags')
            text = replace_once(text, ARGS_GN_ANCHOR,
                                ARGS_GN_ANCHOR + PGO_STEP.format(script=str(Path(__file__).resolve())),
                                'PGO step')
        text = replace_once(text, NINJA_TIMEOUT, NINJA_DEADLINE, 'CI deadline')
        text = replace_once(text, CHROMEDRIVER, '', 'ninja targets')
        write_lf(upstream_build, text)

        # A tree configured by an earlier stage or run: check it before ninja.
        if pgo and (SOURCE_TREE / 'out' / 'Default' / 'args.gn').exists():
            pgo_check(SOURCE_TREE, pgo_target(argv), strict=bool(os.environ.get('GITHUB_ACTIONS')))

        cmd = [sys.executable, 'build.py', '--tarball', *argv]
        # V8's metagen (Chromium 157) runs gn, which it looks for in buildtools
        # or on PATH; the tarball has no buildtools gn, the build bootstraps one
        # into out\Default.
        env = dict(os.environ)
        env['PATH'] = str(SOURCE_TREE / 'out' / 'Default') + os.pathsep + env.get('PATH', '')
        return subprocess.run(cmd, cwd=UPSTREAM, check=False, env=env).returncode
    finally:
        for path, raw in originals.items():
            path.write_bytes(raw)
        shutil.rmtree(injected, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
