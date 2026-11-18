# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:/Users/moroa/Code/Sim-Sequence-Utility/studio_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('D:/Users/moroa/Code/Sim-Sequence-Utility/resources/Logo-COMAU.png', 'resources'),
        ('D:/Users/moroa/Code/Sim-Sequence-Utility/inputs/sample_weld_sequence.cseq', 'inputs'),
    ],
    hiddenimports=['PyQt6.sip', 'networkx.algorithms', 'networkx.classes', 'networkx.generators', 'yaml'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'numpy', 'IPython'],
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
    name='SimSequenceStudio',
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
    icon=['D:/Users/moroa/Code/Sim-Sequence-Utility/resources/Logo-COMAU.ico'],
)
