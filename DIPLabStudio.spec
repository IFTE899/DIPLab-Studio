# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

# HEIC / HEIF support (pillow-heif brings its own native libraries)
heif_datas, heif_binaries, heif_hidden = collect_all('pillow_heif')


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=heif_binaries,
    datas=[('web', 'web'), ('.venv/Lib/site-packages/eel/eel.js', 'eel')] + heif_datas,
    hiddenimports=heif_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='DIPLabStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
)
