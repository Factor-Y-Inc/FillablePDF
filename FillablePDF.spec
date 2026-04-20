# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_all

# customtkinter bundles theme JSON + images — must be explicitly collected
customtkinter_datas = collect_data_files('customtkinter')

# PyMuPDF ships native DLLs and data files — collect everything
fitz_datas, fitz_binaries, fitz_hiddenimports = collect_all('fitz')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=fitz_binaries,
    datas=customtkinter_datas + fitz_datas,
    hiddenimports=fitz_hiddenimports + ['PIL._tkinter_finder'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FillablePDF',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FillablePDF',
)
