# -*- mode: python ; coding: utf-8 -*-
import sys

block_cipher = None

a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'pandas',
        'numpy',
        'openpyxl',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch', 'tensorflow', 'keras', 'sklearn', 'scipy',
        'matplotlib', 'PIL', 'cv2', 'opencv',
        'nltk', 'spacy', 'transformers',
        'jupyter', 'ipython', 'notebook',
        'pytest', 'sphinx',
        'boto3', 'botocore',
        'google', 'googleapiclient',
        'requests', 'urllib3',
        'flask', 'django', 'fastapi',
        'sqlalchemy', 'pymysql', 'psycopg2',
        'tkinter', 'tkinter.ttk',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if sys.platform == 'darwin':
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='bulk_processor',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=True,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='bulk_processor',
    )
    app = BUNDLE(
        coll,
        name='bulk_processor.app',
        bundle_identifier='com.bulkprocessor.app',
        version='1.5.0',
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='bulk_processor',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=True,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='bulk_processor',
    )
