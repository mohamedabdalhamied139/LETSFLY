# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

# Add project root to sys.path so client modules can be loaded
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def perform_audit():
    loc_dir = project_root / 'client' / 'locales'
    ar_file = loc_dir / 'ar.json'
    en_file = loc_dir / 'en.json'

    if not ar_file.is_file() or not en_file.is_file():
        return f"Error: Missing localization files in:\n{loc_dir}"

    try:
        ar_data = json.loads(ar_file.read_text(encoding='utf-8'))
        en_data = json.loads(en_file.read_text(encoding='utf-8'))
    except Exception as e:
        return f"Error reading locale JSON files:\n{e}"

    ar_keys = set(ar_data.keys())
    en_keys = set(en_data.keys())

    missing_in_en = ar_keys - en_keys
    missing_in_ar = en_keys - ar_keys

    report = []
    report.append("=" * 60)
    report.append("            LOCALE PARITY AUDIT REPORT")
    report.append("=" * 60)
    report.append(f"Total Arabic (AR) keys   : {len(ar_keys)}")
    report.append(f"Total English (EN) keys  : {len(en_keys)}")
    report.append("-" * 60)

    if not missing_in_en and not missing_in_ar:
        report.append("RESULT: Excellent! 100% complete parity. Zero missing keys.")
    else:
        report.append(f"Keys present in Arabic but missing in English: {len(missing_in_en)}")
        for k in sorted(missing_in_en):
            report.append(f"  - [AR -> Missing in EN]: {k}")

        report.append("")
        report.append(f"Keys present in English but missing in Arabic: {len(missing_in_ar)}")
        for k in sorted(missing_in_ar):
            report.append(f"  - [EN -> Missing in AR]: {k}")

    # Check other languages if added in the future
    other_files = [f for f in loc_dir.glob("*.json") if f.name not in ('ar.json', 'en.json', 'patterns.json')]
    for other in other_files:
        lang_code = other.stem
        try:
            other_data = json.loads(other.read_text(encoding='utf-8'))
            if not isinstance(other_data, dict):
                continue
            other_keys = set(other_data.keys())
            missing = ar_keys - other_keys
            report.append("-" * 60)
            report.append(f"Additional Locale: {other.name} (Total keys: {len(other_keys)})")
            report.append(f"Missing keys compared to Arabic: {len(missing)}")
            for k in sorted(missing):
                report.append(f"  - [Missing in {lang_code}]: {k}")
        except Exception as ex:
            report.append(f"Could not audit {other.name}: {ex}")

    report.append("=" * 60)
    return "\n".join(report)

def run_gui():
    from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QPlainTextEdit
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QTextCursor

    try:
        from client.accessibility.reader import reader
    except Exception:
        reader = None

    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("Localization Audit Tool - LetsFly")
    window.resize(750, 520)

    central = QWidget(window)
    window.setCentralWidget(central)
    layout = QVBoxLayout(central)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(10)

    top_layout = QHBoxLayout()
    btn_scan = QPushButton("Scan Locales")
    btn_scan.setAccessibleName("Scan Locales button")
    btn_scan.setAccessibleDescription("Click to scan and audit all locale files for parity and missing keys")
    top_layout.addWidget(btn_scan)
    top_layout.addStretch()
    layout.addLayout(top_layout)

    txt_report = QPlainTextEdit()
    txt_report.setReadOnly(True)
    txt_report.setAccessibleName("Audit Report")
    txt_report.setAccessibleDescription("Displays locale audit results and missing keys")
    txt_report.setTextInteractionFlags(Qt.TextSelectableByKeyboard | Qt.TextSelectableByMouse)
    layout.addWidget(txt_report)

    def do_scan():
        res = perform_audit()
        txt_report.setPlainText(res)
        txt_report.moveCursor(QTextCursor.Start)
        txt_report.setFocus()
        if reader and reader.nvda_available:
            first_summary = "Scan completed. "
            if "100% complete parity" in res:
                first_summary += "100 percent complete parity between Arabic and English."
            else:
                first_summary += "Issues found. Check report."
            reader.speak(first_summary, interrupt=True)

    btn_scan.clicked.connect(do_scan)

    window.show()
    do_scan()
    sys.exit(app.exec())

if __name__ == '__main__':
    if '--cli' in sys.argv:
        print(perform_audit())
    else:
        run_gui()
