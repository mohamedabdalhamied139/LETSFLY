# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk

def perform_audit():
    base_dir = Path(__file__).resolve().parent.parent
    loc_dir = base_dir / 'client' / 'locales'
    ar_file = loc_dir / 'ar.json'
    en_file = loc_dir / 'en.json'

    if not ar_file.is_file() or not en_file.is_file():
        return "خطأ: لم يتم العثور على ملفات اللغات في:\n" + str(loc_dir)

    try:
        ar_data = json.loads(ar_file.read_text(encoding='utf-8'))
        en_data = json.loads(en_file.read_text(encoding='utf-8'))
    except Exception as e:
        return f"خطأ أثناء قراءة ملفات الترجمة:\n{e}"

    ar_keys = set(ar_data.keys())
    en_keys = set(en_data.keys())

    missing_in_en = ar_keys - en_keys
    missing_in_ar = en_keys - ar_keys

    report = []
    report.append("=" * 50)
    report.append("  تقرير فحص وتدقيق ملفات الترجمة (Locale Audit)")
    report.append("=" * 50)
    report.append(f"إجمالي المفاتيح في اللغة العربية (AR): {len(ar_keys)}")
    report.append(f"إجمالي المفاتيح في اللغة الإنجليزية (EN): {len(en_keys)}")
    report.append("-" * 50)

    if not missing_in_en and not missing_in_ar:
        report.append("النتيجة: ممتاز! تطابق كامل 100% بين اللغتين بدون أي مفاتيح مفقودة.")
    else:
        report.append(f"مفاتيح موجودة في العربية ومفقودة في الإنجليزية: {len(missing_in_en)}")
        for k in sorted(missing_in_en):
            report.append(f"  - [AR -> Missing in EN]: {k}")

        report.append("")
        report.append(f"مفاتيح موجودة في الإنجليزية ومفقودة في العربية: {len(missing_in_ar)}")
        for k in sorted(missing_in_ar):
            report.append(f"  - [EN -> Missing in AR]: {k}")

    other_files = [f for f in loc_dir.glob("*.json") if f.name not in ('ar.json', 'en.json', 'patterns.json')]
    for other in other_files:
        lang_code = other.stem
        try:
            other_data = json.loads(other.read_text(encoding='utf-8'))
            if not isinstance(other_data, dict):
                continue
            other_keys = set(other_data.keys())
            missing = ar_keys - other_keys
            report.append("-" * 50)
            report.append(f"اللغة الإضافية: {other.name} (إجمالي المفاتيح: {len(other_keys)})")
            report.append(f"مفاتيح مفقودة مقارنة بالعربية: {len(missing)}")
            for k in sorted(missing):
                report.append(f"  - [Missing in {lang_code}]: {k}")
        except Exception as ex:
            report.append(f"تعذر فحص {other.name}: {ex}")

    report.append("=" * 50)
    return "\n".join(report)

def run_gui():
    root = tk.Tk()
    root.title("أداة فحص وتدقيق ملفات الترجمة - LetsFly")
    root.geometry("680x520")

    frame_top = ttk.Frame(root, padding=10)
    frame_top.pack(fill=tk.X)

    btn_scan = ttk.Button(frame_top, text="بدء الفحص (Scan)", command=lambda: on_scan())
    btn_scan.pack(side=tk.LEFT, padx=5, pady=5)

    lbl_info = ttk.Label(
        frame_top, 
        text="اضغط 'بدء الفحص' لمطابقة ملفات اللغات وعرض المفاتيح المفقودة."
    )
    lbl_info.pack(side=tk.LEFT, padx=5, pady=5)

    txt_report = tk.Text(root, wrap=tk.WORD, font=("Consolas", 10), padx=10, pady=10)
    txt_report.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    def on_scan():
        report_text = perform_audit()
        txt_report.delete("1.0", tk.END)
        txt_report.insert(tk.END, report_text)
        txt_report.focus_set()

    on_scan()
    root.mainloop()

if __name__ == '__main__':
    if '--cli' in sys.argv:
        print(perform_audit())
    else:
        run_gui()
