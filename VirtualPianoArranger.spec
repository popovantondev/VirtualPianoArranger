# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/offline_piano', 'assets/offline_piano'),
           *[(name, 'recognition_app') for name in
             ('homr_runner.py', 'omr_layout.py', 'omr_quality.py', 'omr_duration.py',
              'omr_timing.py', 'omr_heads.py', 'omr_notation.py', 'omr_meter.py')],
           ('assets/icons', 'assets/icons'),
           *[(f'docs/design/{name}', 'docs/design') for name in
             ('dark.html', 'dark.css', 'dark.js', 'document-ui.js', 'recording-ui.js')]],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # QWidget/WebEngineWidgets/PDF app: no QML frontend. Do not collect the
    # entire QML plugin tree (which includes unused GPL-only add-ons).
    # Native Qt6Qml/Qt6Quick dependencies remain resolved by PyInstaller.
    excludes=['PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets',
              'PySide6.QtQuickControls2', 'PySide6.QtWebEngineQuick',
              'PySide6.QtPdfQuick', 'PySide6.QtCharts',
              'PySide6.QtDataVisualization', 'PySide6.QtVirtualKeyboard'],
    noarchive=False,
    optimize=0,
)
# Qt6Core on Windows links against the Windows ICU API. PyInstaller may pick up
# an unrelated icuuc.dll from the build machine; that DLL lacks the exports Qt
# expects and makes the packaged app fail before its window opens.
a.binaries = [
    entry for entry in a.binaries
    if entry[0].replace('\\', '/').rsplit('/', 1)[-1].lower()
    not in {'icuuc.dll', 'icudt78.dll',
            # QtGui hook collects all platform-input-context plugins. This
            # QML virtual keyboard is unused; PE inventory confirms its only
            # importer is this excluded plugin, not WebEngine/PDF/Widgets.
            'qtvirtualkeyboardplugin.dll', 'qt6virtualkeyboard.dll'}
]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VirtualPianoArranger',
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
    icon='assets/icons/vpa.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VirtualPianoArranger',
)
