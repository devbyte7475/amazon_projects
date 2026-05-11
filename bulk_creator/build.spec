# -*- mode: python ; coding: utf-8 -*-
"""
Amazon BULK 批量生成工具 - PyInstaller打包配置
支持跨平台构建: macOS (.app) 和 Windows (.exe)
"""

block_cipher = None

a = Analysis(
    ['bulk_creator.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'customtkinter',
        'pandas',
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'datetime',
        'csv',
        'json',
        'platform',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='AmazonBULK批量生成工具',
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
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AmazonBULK批量生成工具',
)

app = BUNDLE(
    coll,
    name='AmazonBULK批量生成工具.app',
    icon=None,
    bundle_identifier='com.amazon.bulkcreator',
    info_plist={
        'CFBundleName': 'Amazon BULK 批量生成工具',
        'CFBundleDisplayName': 'Amazon BULK 批量生成工具',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.13.0',
    },
)
