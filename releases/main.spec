# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []
tmp_ret = collect_all('chromadb')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('sentence_transformers')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('tree_sitter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('tree_sitter_language_pack')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('tree_sitter_c_sharp')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

hiddenimports += [
    'tree_sitter',
    'tree_sitter_language_pack',
    'tree_sitter_c_sharp',
    'src.build_database',
    'src.build_database_JSON',
    'agent.file_summary_agent',
    'agent.directory_agent',
    'agent.BR_agent',
    'agent.UT_agent',
    'agent.states.file_summary_agent_state',
    'agent.states.directory_agent_state',
    'agent.states.BR_agent_state',
    'agent.states.UT_agent_state',
    'agent.structured_output.file_summary_output',
    'agent.structured_output.directory_output',
    'agent.structured_output.BR_output',
    'agent.structured_output.UT_output',
    'utils.tree_parse',
    'utils.uml_json_to_pdf',
]

a = Analysis(
    ['..\\main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    options=[('-u', None, 'OPTION'), ('Xutf8', None, 'OPTION')],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='main',
)
