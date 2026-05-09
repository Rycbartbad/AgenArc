# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for AgenArc standalone executable."""

import sys
from pathlib import Path

_root = Path(__file__).parent

a = Analysis(
    ['agenarc/cli/__main__.py'],
    pathex=[str(_root)],
    binaries=[],
    datas=[
        # Visualization static files
        ('agenarc/visualization/static/*', 'agenarc/visualization/static'),
        # Example agents (for agenarc init)
        ('examples/my_first_agent.agrc', 'examples/my_first_agent.agrc'),
    ],
    hiddenimports=[
        'agenarc.engine.executor',
        'agenarc.engine.state',
        'agenarc.engine.evaluator',
        'agenarc.engine.template_resolver',
        'agenarc.engine.trace',
        'agenarc.operators.builtin',
        'agenarc.operators.llm',
        'agenarc.operators.router',
        'agenarc.operators.join',
        'agenarc.operators.evolution',
        'agenarc.operators.prompt_builder',
        'agenarc.operators.operator',
        'agenarc.protocol.loader',
        'agenarc.protocol.schema',
        'agenarc.graph.traversal',
        'agenarc.vfs.filesystem',
        'agenarc.plugins.manager',
        'agenarc.plugins.hot_loader',
        'agenarc.plugins.event_plugin',
        'agenarc.plugins.loaders.python',
        'agenarc.plugins.loaders.cpp',
        'agenarc.plugins.loaders.external',
        'agenarc.visualization.server',
        'agenarc.visualization.events',
        'agenarc.visualization.state',
        'agenarc.cli.commands.run',
        'agenarc.cli.commands.shell',
        'agenarc.cli.commands.serve',
        'agenarc.cli.commands.validate',
        'agenarc.cli.commands.info',
        'agenarc.cli.commands.pack',
        'agenarc.cli.commands.visualize',
        'agenarc.cli.commands.init',
        'agenarc.cli.commands.__init__',
        'agenarc.config',
        # External deps that might be missed
        'openai',
        'yaml',
        'jsonschema',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'PIL',
        'scipy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AgenArc',
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
    icon=None,
)
