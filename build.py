#!/usr/bin/env python3
"""Build Arcomium for Windows: ungoogled-chromium-windows + Arcomium patches.

Injects the patches of the arcomium submodule into ungoogled-chromium-windows'
patch series, arcomium/flags.gn into its GN flags and a step that copies
arcomium/src and arcomium/branding over the source tree after patching, runs the upstream
build.py, then restores the submodule. Extra arguments go to the upstream
build.py.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UPSTREAM = ROOT / 'ungoogled-chromium-windows'
CORE = ROOT / 'arcomium'
OUR_PATCHES = CORE / 'patches'
OUR_FLAGS = CORE / 'flags.gn'
OUR_BRANDING = CORE / 'branding'
OUR_SOURCES = CORE / 'src'

OUR_RENAME = CORE / 'tools' / 'rename_product.py'

# Inserted into the upstream build.py after its patches: Arcomium's own source
# files and binary branding files are copied over the tree, not patched in, and
# renaming the product in the strings moves hundreds of translations, which a
# script does better than a patch.
BRANDING_ANCHOR = '        # Substitute domains\n'
BRANDING_STEP = ('        shutil.copytree({sources!r}, source_tree, dirs_exist_ok=True)\n'
                 '        shutil.copytree({branding!r}, source_tree, dirs_exist_ok=True)\n'
                 '        subprocess.run([sys.executable, {rename!r}, str(source_tree)], check=True)\n'
                 '        get_logger().info("Copied Arcomium sources and branding, renamed the product")\n')


def read_series(path):
    lines = path.read_text(encoding='utf-8').splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith('#')]


def check_python3():
    # GN resolves `python3` from PATH and bakes that path into every ninja rule.
    # The Windows Store / Python install manager alias breaks every script step.
    found = shutil.which('python3')
    if not found or 'WindowsApps' in found:
        sys.exit(f'python3 resolves to {found!r}. Put a real Python 3 directory '
                 'containing python3.exe (a copy of python.exe) first in PATH.')


def main():
    check_python3()
    series = UPSTREAM / 'patches' / 'series'
    flags = UPSTREAM / 'flags.windows.gn'
    upstream_build = UPSTREAM / 'build.py'
    injected = UPSTREAM / 'patches' / 'arcomium'
    originals = {p: p.read_text(encoding='utf-8')
                 for p in (series, flags, upstream_build)}

    try:
        if injected.exists():
            shutil.rmtree(injected)
        shutil.copytree(OUR_PATCHES, injected)
        ours = ['arcomium/' + p for p in read_series(OUR_PATCHES / 'series')]
        series.write_text(originals[series].rstrip('\n') + '\n' + '\n'.join(ours) + '\n',
                          encoding='utf-8')
        if OUR_FLAGS.exists():
            flags.write_text(originals[flags].rstrip('\n') + '\n' +
                             OUR_FLAGS.read_text(encoding='utf-8'), encoding='utf-8')
        if OUR_BRANDING.exists():
            text = originals[upstream_build]
            if (BRANDING_ANCHOR not in text or 'import shutil' not in text
                    or 'import subprocess' not in text):
                sys.exit('upstream build.py changed: cannot add the branding step')
            step = BRANDING_STEP.format(sources=str(OUR_SOURCES), branding=str(OUR_BRANDING),
                                        rename=str(OUR_RENAME))
            upstream_build.write_text(text.replace(BRANDING_ANCHOR, step + BRANDING_ANCHOR, 1),
                                      encoding='utf-8')

        cmd = [sys.executable, 'build.py', '--tarball', *sys.argv[1:]]
        return subprocess.run(cmd, cwd=UPSTREAM, check=False).returncode
    finally:
        for path, text in originals.items():
            path.write_text(text, encoding='utf-8')
        shutil.rmtree(injected, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
