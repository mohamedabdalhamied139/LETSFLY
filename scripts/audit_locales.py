# -*- coding: utf-8 -*-
import json
import re
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

            # Check for English copy-paste placeholders
            identical_to_en = []
            for k in ar_keys.intersection(other_keys):
                en_val = en_data.get(k)
                oth_val = other_data.get(k)
                ar_val = ar_data.get(k)
                if oth_val and en_val and oth_val == en_val and oth_val != ar_val:
                    # Ignore short symbols / numbers
                    if len(oth_val) > 1 and not oth_val.isdigit():
                        identical_to_en.append((k, en_val))

            report.append(f"Untranslated (Identical to English placeholders): {len(identical_to_en)}")
            if identical_to_en:
                for k, v in identical_to_en[:20]:
                    report.append(f"  - [Placeholder in {lang_code}]: '{k}' -> '{v}'")
                if len(identical_to_en) > 20:
                    report.append(f"  ... and {len(identical_to_en) - 20} more untranslated placeholders.")
            else:
                report.append(f"RESULT: 100% genuine translations in {lang_code}! Zero English placeholders.")

        except Exception as ex:
            report.append(f"Could not audit {other.name}: {ex}")

    # Check pattern templates localization
    patterns_file = loc_dir / 'patterns.json'
    if patterns_file.is_file():
        try:
            p_data = json.loads(patterns_file.read_text(encoding='utf-8'))
            all_templates = {p.get('template') for p in p_data if p.get('template')}
            report.append("-" * 60)
            report.append(f"Pattern Templates Audit (Total unique templates: {len(all_templates)})")
            for other in other_files:
                lang_code = other.stem
                other_data = json.loads(other.read_text(encoding='utf-8'))
                missing_tmpl = [t for t in all_templates if t not in other_data]
                report.append(f"Templates missing in {lang_code}.json: {len(missing_tmpl)} / {len(all_templates)}")
                if missing_tmpl:
                    for t in sorted(missing_tmpl)[:10]:
                        report.append(f"  - [Missing pattern template in {lang_code}]: {t}")
                    if len(missing_tmpl) > 10:
                        report.append(f"  ... and {len(missing_tmpl) - 10} more.")
        except Exception as ex:
            report.append(f"Could not audit patterns: {ex}")

    # 2. Check for hardcoded / uncataloged Arabic strings in client python code
    import ast
    arabic_re = re.compile(r'[\u0600-\u06FF]')
    client_dir = project_root / 'client'
    uncataloged_code_strings = []

    for py_file in client_dir.rglob('*.py'):
        if 'locales' in str(py_file):
            continue
        try:
            content = py_file.read_text(encoding='utf-8')
            tree = ast.parse(content, filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    val = node.value.strip()
                    if arabic_re.search(val) and len(val) > 1 and not val.startswith(('?', '^', '(?', '[')):
                        if '\n' not in val and val not in ar_keys and val != "إعدادات غير":
                            uncataloged_code_strings.append((py_file.name, getattr(node, 'lineno', 0), val))
        except Exception:
            pass

    report.append("-" * 60)
    report.append(f"Hardcoded Uncataloged Arabic strings in Client Code: {len(uncataloged_code_strings)}")
    if not uncataloged_code_strings:
        report.append("RESULT: Clean! No uncataloged hardcoded Arabic strings found in code.")
    else:
        for fname, line_num, s in uncataloged_code_strings[:25]:
            report.append(f"  - [{fname}:{line_num}]: {s}")
        if len(uncataloged_code_strings) > 25:
            report.append(f"  ... and {len(uncataloged_code_strings) - 25} more.")

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
    if sys.stdout.encoding != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    if '--cli' in sys.argv:
        print(perform_audit())
    else:
        run_gui()
