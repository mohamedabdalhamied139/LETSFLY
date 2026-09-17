# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

datas = [
    ('client/assets/audio', 'assets/audio'),
    ('client/assets/nvda/nvdaControllerClient.dll', 'assets/nvda'),
    ('client/help/*.txt', 'client/help'),
    ('client/locales/*.json', 'client/locales'),
]

binaries = []
dll_path = 'client/assets/nvda/nvdaControllerClient.dll'
if os.path.exists(dll_path):
    binaries.append((dll_path, '.'))
    binaries.append((dll_path, 'assets/nvda'))

dll_path_64 = 'client/assets/nvda/nvdaControllerClient64.dll'
if os.path.exists(dll_path_64):
    binaries.append((dll_path_64, '.'))
    binaries.append((dll_path_64, 'assets/nvda'))

a = Analysis(
    ['client/main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'uvicorn',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan.on',
        'passlib.handlers.bcrypt',
        'jwt',
        'sqlite3',
        'sqlalchemy.dialects.sqlite',
        'PySide6.QtMultimedia',
        'PySide6.QtWidgets',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'websocket',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'numpy',
        'PIL',
        'Pillow',
        'matplotlib',
        'scipy',
        'pandas',
        'tkinter',
        'unittest',
        'PySide6.QtQuick',
        'PySide6.QtQml',
        'PySide6.QtPdf',
        'PySide6.QtPdfWidgets',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        'PySide6.QtSvg',
        'PySide6.QtSvgWidgets',
        'PySide6.QtDesigner',
        'PySide6.QtTest',
        'PySide6.QtPrintSupport',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LetsFly',
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
    name='LetsFly',
)
