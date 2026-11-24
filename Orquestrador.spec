# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['orquestrador.py'],
    pathex=[],
    binaries=[],
    datas=[('perfil.json', '.')],
    hiddenimports=['src', 'src.core', 'src.config', 'src.server', 'src.readers', 'src.rules', 'src.logging', 'src.dashboard', 'src.actions', 'docx', 'pypdf', 'openpyxl', 'xlrd', 'pptx', 'PIL'],
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
    name='Orquestrador',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
