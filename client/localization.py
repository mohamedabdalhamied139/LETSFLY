# -*- coding: utf-8 -*-
"""Runtime localization and language system for TableVerse.

Provides a centralized, production-ready TranslationManager supporting Arabic
and English. Automatically detects operating system language on startup, supports
manual override with persistent settings, and executes live UI and NVDA speech
updates without restarting the application.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import re._parser as sre_parse
except ImportError:
    try:
        import sre_parse
    except ImportError:
        sre_parse = None

from client import settings_store

TranslationCallback = Callable[[str], None]
logger = logging.getLogger("tableverse.localization")


class TranslationManager:
    """Centralized translation and localization manager for TableVerse."""

    _instance: Optional[TranslationManager] = None

    def __new__(cls) -> TranslationManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._callbacks: List[TranslationCallback] = []
        self._catalogs: Dict[str, Dict[str, str]] = {}
        self._ar_catalog: Dict[str, str] = {}
        self._en_catalog: Dict[str, str] = {}
        self._en_to_ar_reverse: Dict[str, str] = {}
        self._patterns: List[Tuple[re.Pattern, str, List[str]]] = []
        self._load_catalogs()
        self._load_patterns()

    def _locales_dir(self) -> Path:
        candidates = [
            Path(__file__).resolve().parent / "locales",
            Path(getattr(sys, "_MEIPASS", "")) / "client" / "locales",
            Path(getattr(sys, "_MEIPASS", "")) / "locales",
        ]
        for c in candidates:
            if c.is_dir():
                return c
        return Path(__file__).resolve().parent / "locales"

    def _load_catalogs(self) -> None:
        loc_dir = self._locales_dir()
        self._catalogs = {}
        if loc_dir.is_dir():
            for p in loc_dir.glob("*.json"):
                if p.stem.lower() == "patterns":
                    continue
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        self._catalogs[p.stem.lower()] = json.load(f)
                except Exception:
                    logger.exception("Failed to load catalog from %s", p)

        self._ar_catalog = self._catalogs.get("ar", {})
        self._en_catalog = self._catalogs.get("en", {})

        self._en_to_ar_reverse = {}
        self._val_to_canonical: Dict[str, str] = {}
        for cat_lang, cat_dict in self._catalogs.items():
            if not isinstance(cat_dict, dict):
                continue
            for ar_key, tr_val in cat_dict.items():
                if not tr_val or not ar_key:
                    continue
                tr_val_str = str(tr_val)
                ar_key_str = str(ar_key)
                if tr_val_str not in self._val_to_canonical:
                    self._val_to_canonical[tr_val_str] = ar_key_str
                if cat_lang == "en":
                    if tr_val_str not in self._en_to_ar_reverse:
                        self._en_to_ar_reverse[tr_val_str] = ar_key_str
                    else:
                        prev = self._en_to_ar_reverse[tr_val_str]
                        if (prev.endswith(".") or prev.endswith("!")) and not (ar_key_str.endswith(".") or ar_key_str.endswith("!")):
                            self._en_to_ar_reverse[tr_val_str] = ar_key_str

    def _load_patterns(self) -> None:
        loc_dir = self._locales_dir()
        pat_file = loc_dir / "patterns.json"
        if not pat_file.is_file():
            return

        try:
            with open(pat_file, "r", encoding="utf-8") as f:
                raw_patterns = json.load(f)

            def _pat_priority(p: dict) -> int:
                """Prefer patterns with more fixed literal text over generic catch-alls."""
                pat_str = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), p.get("pattern", ""))
                try:
                    parsed = sre_parse.parse(pat_str)
                    literal_count = 0
                    group_penalty = 0

                    def walk(tokens):
                        nonlocal literal_count, group_penalty
                        for op, arg in tokens:
                            if op is sre_parse.LITERAL:
                                literal_count += 1
                            elif op in (sre_parse.MAX_REPEAT, sre_parse.MIN_REPEAT):
                                literal_count += 0.5
                                walk(arg[2])
                            elif op is sre_parse.IN:
                                # Character classes are less specific than fixed text.
                                literal_count += 0.25
                            elif op is sre_parse.SUBPATTERN:
                                group_penalty += 1
                                walk(arg[-1])
                            elif op in (sre_parse.BRANCH,):
                                branches = arg[1]
                                group_penalty += 0.5
                                for branch in branches:
                                    walk(branch)
                            elif hasattr(arg, 'data'):
                                walk(arg)

                    walk(parsed)
                    # Long fixed phrases should dominate broad patterns even if both
                    # contain capture groups. A small branch penalty discourages overly
                    # generic alternations from outranking a specific sentence.
                    return int(literal_count * 100 - group_penalty)
                except Exception:
                    # Fallback heuristic if regex parsing ever changes in a future Python.
                    lit = re.sub(r"\([^\)]+\)", "", pat_str)
                    lit = re.sub(r"\\[a-zA-Z]", "", lit)
                    lit = re.sub(r"[\^\$\+\*\?]", "", lit)
                    return len(lit.strip())

            sorted_patterns = sorted(raw_patterns, key=_pat_priority, reverse=True)
            self._patterns = [
                (re.compile(item["pattern"], re.UNICODE), item["template"], item.get("roles", []))
                for item in sorted_patterns
            ]
        except Exception:
            logger.exception("Failed to load localization patterns from %s", pat_file)
            self._patterns = []

    def system_language(self) -> str:
        """Detect operating system UI language reliably on Windows."""
        try:
            import ctypes
            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            primary_lang = lang_id & 0x3FF
            if primary_lang == 0x01:  # LANG_ARABIC
                return "ar"
            return "en"
        except Exception:
            pass

        try:
            from PySide6.QtCore import QLocale
            lang = QLocale.system().language()
            arabic_enum = getattr(QLocale.Language, "Arabic", getattr(QLocale, "Arabic", None))
            if lang == arabic_enum:
                return "ar"
            return "en"
        except Exception:
            pass

        try:
            import locale
            loc_str = (locale.getlocale()[0] or "").lower()
            if loc_str.startswith("ar"):
                return "ar"
        except Exception:
            pass

        return "en"

    def language(self) -> str:
        """Return effective active language code ('ar', 'en', 'fr', etc.)."""
        try:
            settings = settings_store.load_settings()
            pref = str(settings.get("general", {}).get("language", "system") or "system").lower().strip()
        except Exception:
            pref = "system"

        if pref == "system":
            sys_lang = self.system_language()
            return sys_lang if sys_lang in self._catalogs or sys_lang == "ar" else "en"
        if pref in self._catalogs:
            return pref
        if pref.startswith("ar"):
            return "ar"
        return "en"

    def is_rtl(self) -> bool:
        """Return True if active language is Right-to-Left (Arabic)."""
        return self.language() == "ar"

    def set_language(self, value: str) -> str:
        """Change language preference and update the UI immediately without restart."""
        val = str(value or "system").lower().strip()
        if val != "system" and val not in self._catalogs:
            val = "system"

        settings = settings_store.load_settings()
        settings.setdefault("general", {})["language"] = val
        settings_store.save_settings(settings)

        active = self.language()

        try:
            from PySide6.QtWidgets import QApplication
            from PySide6.QtCore import Qt
            app = QApplication.instance()
            if app:
                app.setLayoutDirection(Qt.RightToLeft if active == "ar" else Qt.LeftToRight)
        except Exception:
            pass

        for cb in list(self._callbacks):
            try:
                cb(active)
            except Exception:
                logger.exception("Localization callback failed during language switch")

        # The callbacks update subscribed views immediately. Refresh any windows
        # that are not subscribed (including transient dialogs) as a final sweep.
        self.refresh_all_windows()
        return active

    def subscribe(self, callback: TranslationCallback) -> None:
        """Register a callback to be called whenever active language changes."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def unsubscribe(self, callback: TranslationCallback) -> None:
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def tr(self, _text: Any = None, *args: Any, **kwargs: Any) -> Any:
        """Translate text at runtime using centralized catalog with safe fallback and parameter interpolation."""
        if _text is None:
            return _text
        s = str(_text)
        if not s or not s.strip():
            return s

        translated = self._tr_base(s)
        if args or kwargs:
            try:
                # Formatting arguments are runtime data (names, numbers, server values,
                # etc.). Never translate them implicitly; only the surrounding template
                # belongs to localization. Explicitly localized categories should be
                # translated before being passed as arguments by the caller/pattern role.
                if args and kwargs:
                    return translated.format(*args, **kwargs)
                elif args:
                    return translated.format(*args)
                else:
                    return translated.format(**kwargs)
            except Exception:
                logger.exception("Localization formatting failed for %r", s)
        return translated

    def translate(self, key: str, *args: Any, **kwargs: Any) -> str:
        """Structured parametric translation with explicit key and parameters."""
        return str(self.tr(key, *args, **kwargs))

    def _tr_base(self, s: str) -> str:
        """Translate string literal or template."""

        active = self.language()

        # Arabic mode
        if active == "ar":
            # Prefer a direct Arabic catalog entry. This is essential for English
            # canonical keys that have explicit Arabic values; the reverse map is
            # only a compatibility fallback for legacy Arabic-source keys.
            if s in self._ar_catalog:
                return self._ar_catalog[s]
            if s in self._en_to_ar_reverse:
                return self._en_to_ar_reverse[s]
            if s in self._val_to_canonical:
                canonical = self._val_to_canonical[s]
                return self._ar_catalog.get(canonical, canonical)

            stripped = s.strip()
            if stripped in self._ar_catalog:
                trans = self._ar_catalog[stripped]
                leading = s[:len(s) - len(s.lstrip())]
                trailing = s[len(s.rstrip()):]
                return f"{leading}{trans}{trailing}"

            # Translate known localized list members without touching arbitrary
            # runtime text such as player names. This covers card/suit lists in
            # game announcements that are joined with Arabic or English commas.
            for sep in ("، ", ", ", " و ", " و", " and "):
                if sep in s:
                    parts = s.split(sep)
                    translated_parts = [self._ar_catalog.get(part, self._en_to_ar_reverse.get(part, part)) for part in parts]
                    if all(tp != part for tp, part in zip(translated_parts, parts)):
                        return sep.join(translated_parts)

            # Strip trailing punctuation for catalog and reverse lookup
            for punct in ("...", ".", "!", "?", "؟", ":", ","):
                if stripped.endswith(punct):
                    core = stripped[:-len(punct)].rstrip()
                    trans_core = self._ar_catalog.get(core, self._en_to_ar_reverse.get(core))
                    if trans_core:
                        ar_punct = "؟" if punct in ("?", "؟") else punct
                        leading = s[:len(s) - len(s.lstrip())]
                        return f"{leading}{trans_core}{ar_punct}"
            return s

        # Target language catalog (English, French, etc.)
        catalog = self._catalogs.get(active, self._en_catalog)

        # 1. Exact catalog match
        if s in catalog:
            return catalog[s]

        # Stripped match (preserving whitespace)
        stripped = s.strip()
        if stripped in catalog:
            translated = catalog[stripped]
            leading = s[:len(s) - len(s.lstrip())]
            trailing = s[len(s.rstrip()):]
            return f"{leading}{translated}{trailing}"

        # Cross-language translation fallback (e.g. French -> English or English -> French)
        canonical = self._val_to_canonical.get(s) or self._val_to_canonical.get(stripped)
        if canonical and canonical != s and canonical != stripped:
            trans = catalog.get(canonical)
            if trans:
                leading = s[:len(s) - len(s.lstrip())]
                trailing = s[len(s.rstrip()):]
                return f"{leading}{trans}{trailing}"

        # Trailing punctuation handling:
        for punct in ("...", ".", "!", "؟", "?", ":", "،", ","):
            if stripped.endswith(punct):
                core = stripped[:-len(punct)].rstrip()
                if core in catalog:
                    translated_core = catalog[core]
                    leading = s[:len(s) - len(s.lstrip())]
                    trailing_punct = "." if punct == "." else ("?" if punct == "؟" else punct)
                    return f"{leading}{translated_core}{trailing_punct}"

        # If catalog has entry with a period, but stripped doesn't have it:
        if f"{stripped}." in catalog:
            trans = catalog[f"{stripped}."]
            if trans.endswith("."):
                trans = trans[:-1]
            leading = s[:len(s) - len(s.lstrip())]
            trailing = s[len(s.rstrip()):]
            return f"{leading}{trans}{trailing}"


        # Translate a list only when every member is an exact catalog key.
        # This prevents accidental translation of usernames or free-form text.
        for sep in ("، ", ", ", " و ", " و", " and "):
            if sep in stripped:
                parts = stripped.split(sep)
                translated_parts = [catalog.get(part, part) for part in parts]
                if all(tp != part for tp, part in zip(translated_parts, parts)):
                    leading = s[:len(s) - len(s.lstrip())]
                    trailing = s[len(s.rstrip()):]
                    if sep in (" و ", " و"):
                        join_sep = " et " if active == "fr" else " and "
                    else:
                        join_sep = sep
                    return f"{leading}{join_sep.join(translated_parts)}{trailing}"

        # 2. Compound Arabic-comma or em-dash clauses.
        # Some game summaries contain several independently localizable events
        # in one sentence. Try clause-level localization before broad regex
        # patterns; only commit when every clause is actually translated. This
        # avoids allowing a greedy pattern to consume an entire summary and
        # leave later clauses in Arabic. Card lists use " و " and are therefore
        # unaffected.
        if "، " in stripped and not re.search(r"[.!?؟]\s", stripped):
            parts = [p.strip() for p in stripped.split("، ") if p.strip()]
            if len(parts) > 1:
                translated_parts = [self.tr(part) for part in parts]
                if all(tp != part for tp, part in zip(translated_parts, parts)):
                    leading = s[:len(s) - len(s.lstrip())]
                    trailing = s[len(s.rstrip()):]
                    return f"{leading}{', '.join(translated_parts)}{trailing}"

        if " — " in stripped:
            parts = [p.strip() for p in stripped.split(" — ") if p.strip()]
            if len(parts) > 1:
                translated_parts = [self.tr(part) for part in parts]
                if all(tp != part for tp, part in zip(translated_parts, parts)):
                    leading = s[:len(s) - len(s.lstrip())]
                    trailing = s[len(s.rstrip()):]
                    return f"{leading}{' — '.join(translated_parts)}{trailing}"

        # 3. Dynamic regex template pattern matching on whole string
        for pattern, template, roles in self._patterns:
            m = pattern.match(stripped)
            if not m and stripped.endswith("."):
                m = pattern.match(stripped[:-1].rstrip())
            if m:
                groups = list(m.groups())
                translated_args = []
                for idx, val in enumerate(groups):
                    if isinstance(roles, dict):
                        role = roles.get(idx, roles.get(str(idx), "text"))
                    elif isinstance(roles, (list, tuple)):
                        role = roles[idx] if idx < len(roles) else "text"
                    else:
                        role = "text"
                    if role == "pts":
                        if active == "fr":
                            translated_args.append("points" if val.startswith("\u0646") else "unités")
                        else:
                            translated_args.append("points" if val.startswith("\u0646") else "units")
                    elif role == "score_list":
                        score_unit = "points" if active in ("en", "fr") else "نقاط"
                        rounds_unit = "tours" if active == "fr" else ("rounds" if active == "en" else "جولات")
                        comma = ", " if active in ("en", "fr") else "، "
                        res = re.sub(r"(?<!\w)نقاط(?!\w)", score_unit, val)
                        res = re.sub(r"(?<!\w)جولات(?!\w)", rounds_unit, res)
                        translated_args.append(res.replace("، ", comma))
                    elif role == "set_list":
                        comma = ", " if active in ("en", "fr") else "، "
                        translated_args.append(val.replace("، ", comma))
                    elif role in {"game", "title", "rules", "color", "combo", "tile", "side", "card", "card_list", "status", "sub", "ordinal", "floor", "actor"}:
                        # These roles are explicitly user-facing/localizable categories.
                        translated = self.tr(val)
                        if role == "card_list":
                            if active == "en":
                                translated = translated.replace(" و ", " and ")
                            elif active == "fr":
                                translated = translated.replace(" و ", " et ")
                        translated_args.append(translated)
                    else:
                        # user/num/text/dice are runtime data and must remain untouched.
                        translated_args.append(val)
                try:
                    # Resolve pattern template against active catalog if available (e.g. for French or other non-English locales)
                    target_template = catalog.get(template, template)
                    out = target_template.format(*translated_args)
                    leading = s[:len(s) - len(s.lstrip())]
                    trailing = s[len(s.rstrip()):]
                    return f"{leading}{out}{trailing}"
                except Exception:
                    continue

        # 4. Multi-sentence splitting: If the text consists of multiple sentences (. ! ؟ ?),
        # try translating each sentence independently when full match was not found.
        if any(sep in stripped for sep in (". ", "! ", "؟ ", "? ")):
            parts = [p.strip() for p in re.split(r"(?<=[.!?؟])\s+", stripped) if p.strip()]
            if len(parts) > 1:
                translated_parts = [self.tr(part) for part in parts]
                if all(tp != part for tp, part in zip(translated_parts, parts)):
                    leading = s[:len(s) - len(s.lstrip())]
                    trailing = s[len(s.rstrip()):]
                    return f"{leading}{' '.join(translated_parts)}{trailing}"

        # 4. Multi-sentence splitting (fallback for concatenated statements)
        if any(sep in stripped for sep in (". ", "! ", "؟ ", "? ")):
            parts = [p for p in re.split(r"(?<=[.!?؟])\s+", stripped) if p]
            translated_parts = []
            changed = False
            for p in parts:
                p_clean = p.strip()
                t = self.tr(p_clean)
                if t != p_clean:
                    changed = True
                    translated_parts.append(t)
                else:
                    # Try with period if not already ending in punct
                    p_test = p_clean + "." if not p_clean.endswith((".", "!", "؟", "?")) else p_clean
                    t2 = self.tr(p_test)
                    if t2 != p_test:
                        changed = True
                        translated_parts.append(t2)
                    else:
                        translated_parts.append(p)
                    
            if changed:
                leading = s[:len(s) - len(s.lstrip())]
                trailing = s[len(s.rstrip()):]
                out_joined = " ".join(translated_parts)
                return f"{leading}{out_joined}{trailing}"

        # 5. Compound comma-separated list
        if "، " in stripped:
            parts = stripped.split("، ")
            trans_parts = [self.tr(p) for p in parts]
            leading = s[:len(s) - len(s.lstrip())]
            trailing = s[len(s.rstrip()):]
            return f"{leading}{', '.join(trans_parts)}{trailing}"

        # 6. Known compound phrases (fallback)
        if s.startswith("\u0625\u0639\u062f\u0627\u062f\u0627\u062a ") and not s.startswith("\u0625\u0639\u062f\u0627\u062f\u0627\u062a \u063a\u064a\u0631"):
            remainder = s[len("\u0625\u0639\u062f\u0627\u062f\u0627\u062a "):]
            settings_word = self.tr("\u0625\u0639\u062f\u0627\u062f\u0627\u062a")
            return f"{self.tr(remainder)} {settings_word}"
        if s.startswith("\u0625\u062c\u0631\u0627\u0621\u0627\u062a "):
            remainder = s[len("\u0625\u062c\u0631\u0627\u0621\u0627\u062a "):]
            actions_word = self.tr("\u0625\u062c\u0631\u0627\u0621\u0627\u062a")
            return f"{self.tr(remainder)} {actions_word}"
        if s.startswith("\u0634\u0631\u062d "):
            remainder = s[len("\u0634\u0631\u062d "):]
            guide_word = self.tr("Guide") if "Guide" in catalog else ("Guide" if active == "en" else "Guide")
            return f"{self.tr(remainder)} {guide_word}"
        if s.startswith("\u0627خ\u062a\u0635\u0627\u0631\u0627\u062a "):
            remainder = s[len("\u0627خ\u062a\u0635\u0627\u0631\u0627\u062a "):]
            shortcuts_word = self.tr("\u0627خ\u062a\u0635\u0627\u0631\u0627\u062a")
            return f"{self.tr(remainder)} {shortcuts_word}"

        # 6. Safe fallback: return original text
        return s

    def tr_multiline(self, text: Any) -> Any:
        """Translate multi-line text preserving line breaks."""
        if text is None:
            return text
        lines = str(text).splitlines()
        return "\n".join(self.tr(line) for line in lines)

    def _update_widget_text(self, widget: Any, getter: Callable, setter: Callable) -> None:
        try:
            current = getter()
            original = widget.property("_lf_orig_text")
            last_tr = widget.property("_lf_last_tr_text")
            if original is None or current != last_tr:
                original = current
                widget.setProperty("_lf_orig_text", original)
            out = self.tr(original)
            if current != out:
                setter(out)
            widget.setProperty("_lf_last_tr_text", out)
        except Exception:
            logger.exception("Failed to update widget localization state")

    def localize_widget_tree(self, root: Any) -> None:
        """Recursively update text, titles, tooltips, accessible names, and layout."""
        if root is None:
            return
        try:
            from PySide6.QtCore import Qt
            from PySide6.QtWidgets import (
                QCheckBox,
                QComboBox,
                QDialog,
                QGroupBox,
                QLabel,
                QLineEdit,
                QListWidget,
                QPushButton,
                QRadioButton,
                QTabWidget,
            )

            is_arabic = self.is_rtl()
            target_direction = Qt.RightToLeft if is_arabic else Qt.LeftToRight

            widgets = [root]
            if hasattr(root, "findChildren"):
                widgets.extend(root.findChildren(object))

            for w in widgets:
                try:
                    # Generic accessibility and tooltip translation for ANY widget
                    if hasattr(w, "accessibleName") and callable(w.accessibleName) and w.accessibleName():
                        orig_acc = w.property("_lf_orig_acc_name")
                        last_acc = w.property("_lf_last_acc_name")
                        cur_acc = w.accessibleName()
                        if orig_acc is None or cur_acc != last_acc:
                            orig_acc = cur_acc
                            w.setProperty("_lf_orig_acc_name", orig_acc)
                        out_acc = self.tr(orig_acc)
                        w.setAccessibleName(out_acc)
                        w.setProperty("_lf_last_acc_name", out_acc)

                    if hasattr(w, "accessibleDescription") and callable(w.accessibleDescription) and w.accessibleDescription():
                        orig_desc = w.property("_lf_orig_acc_desc")
                        last_desc = w.property("_lf_last_acc_desc")
                        cur_desc = w.accessibleDescription()
                        if orig_desc is None or cur_desc != last_desc:
                            orig_desc = cur_desc
                            w.setProperty("_lf_orig_acc_desc", orig_desc)
                        out_desc = self.tr(orig_desc)
                        w.setAccessibleDescription(out_desc)
                        w.setProperty("_lf_last_acc_desc", out_desc)

                    if hasattr(w, "toolTip") and callable(w.toolTip) and w.toolTip():
                        orig_tip = w.property("_lf_orig_tooltip")
                        last_tip = w.property("_lf_last_tooltip")
                        cur_tip = w.toolTip()
                        if orig_tip is None or cur_tip != last_tip:
                            orig_tip = cur_tip
                            w.setProperty("_lf_orig_tooltip", orig_tip)
                        out_tip = self.tr(orig_tip)
                        w.setToolTip(out_tip)
                        w.setProperty("_lf_last_tooltip", out_tip)

                    if hasattr(w, "windowTitle") and callable(w.windowTitle) and w.windowTitle():
                        orig_wt = w.property("_lf_orig_window_title")
                        last_wt = w.property("_lf_last_window_title")
                        cur_wt = w.windowTitle()
                        if orig_wt is None or cur_wt != last_wt:
                            orig_wt = cur_wt
                            w.setProperty("_lf_orig_window_title", orig_wt)
                        out_wt = self.tr(orig_wt)
                        w.setWindowTitle(out_wt)
                        w.setProperty("_lf_last_window_title", out_wt)

                    if isinstance(w, (QLabel, QPushButton, QCheckBox, QRadioButton, QGroupBox)):
                        self._update_widget_text(w, w.text, w.setText)

                    elif isinstance(w, QComboBox):
                        for i in range(w.count()):
                            cur_item = w.itemText(i)
                            orig_item = w.itemData(i, Qt.UserRole + 1100)
                            last_item = w.property(f"_lf_combo_last_{i}")
                            if orig_item is None or cur_item != last_item:
                                orig_item = cur_item
                                w.setItemData(i, orig_item, Qt.UserRole + 1100)
                            out_item = self.tr(orig_item)
                            w.setItemText(i, out_item)
                            w.setProperty(f"_lf_combo_last_{i}", out_item)
                        if w.placeholderText():
                            w.setPlaceholderText(self.tr(w.placeholderText()))

                    elif isinstance(w, QListWidget):
                        for i in range(w.count()):
                            item = w.item(i)
                            if not item:
                                continue
                            cur_t = item.text()
                            orig_t = item.data(Qt.UserRole + 1101)
                            last_t = item.data(Qt.UserRole + 1102)
                            if orig_t is None or cur_t != last_t:
                                orig_t = cur_t
                                item.setData(Qt.UserRole + 1101, orig_t)
                            out_t = self.tr(orig_t)
                            item.setText(out_t)
                            item.setData(Qt.UserRole + 1102, out_t)
                            if item.toolTip():
                                item.setToolTip(self.tr(item.toolTip()))

                    elif isinstance(w, QLineEdit):
                        if w.placeholderText():
                            orig_ph = w.property("_lf_orig_placeholder")
                            cur_ph = w.placeholderText()
                            if orig_ph is None or cur_ph != w.property("_lf_last_placeholder"):
                                orig_ph = cur_ph
                                w.setProperty("_lf_orig_placeholder", orig_ph)
                            out_ph = self.tr(orig_ph)
                            w.setPlaceholderText(out_ph)
                            w.setProperty("_lf_last_placeholder", out_ph)

                    elif isinstance(w, QTabWidget):
                        for i in range(w.count()):
                            cur_tab = w.tabText(i)
                            orig_tab = w.property(f"_lf_orig_tab_{i}")
                            last_tab = w.property(f"_lf_last_tab_{i}")
                            if orig_tab is None or cur_tab != last_tab:
                                orig_tab = cur_tab
                                w.setProperty(f"_lf_orig_tab_{i}", orig_tab)
                            out_tab = self.tr(orig_tab)
                            if cur_tab != out_tab:
                                w.setTabText(i, out_tab)
                            w.setProperty(f"_lf_last_tab_{i}", out_tab)
                            cur_tip = w.tabToolTip(i)
                            if cur_tip:
                                orig_tt = w.property(f"_lf_orig_tab_tt_{i}")
                                if orig_tt is None or cur_tip != w.property(f"_lf_last_tab_tt_{i}"):
                                    orig_tt = cur_tip
                                    w.setProperty(f"_lf_orig_tab_tt_{i}", orig_tt)
                                out_tt = self.tr(orig_tt)
                                if cur_tip != out_tt:
                                    w.setTabToolTip(i, out_tt)
                                w.setProperty(f"_lf_last_tab_tt_{i}", out_tt)

                    if hasattr(w, "actions") and callable(w.actions):
                        for act in w.actions():
                            cur_t = act.text()
                            if cur_t:
                                orig_t = act.property("_lf_orig_act_text")
                                last_t = act.property("_lf_last_act_text")
                                if orig_t is None or cur_t != last_t:
                                    orig_t = cur_t
                                    act.setProperty("_lf_orig_act_text", orig_t)
                                out_t = self.tr(orig_t)
                                if cur_t != out_t:
                                    act.setText(out_t)
                                act.setProperty("_lf_last_act_text", out_t)

                    if hasattr(w, "setLayoutDirection"):
                        w.setLayoutDirection(target_direction)

                except Exception:
                    continue

            if hasattr(root, "setLayoutDirection"):
                root.setLayoutDirection(target_direction)

        except Exception:
            logger.exception("Failed to localize widget tree")

    def refresh_all_windows(self) -> None:
        """Update widget trees of all active top-level Qt windows."""
        try:
            from PySide6.QtWidgets import QApplication
            from PySide6.QtCore import Qt

            app = QApplication.instance()
            if not app:
                return

            app.setLayoutDirection(Qt.RightToLeft if self.is_rtl() else Qt.LeftToRight)

            for top in app.topLevelWidgets():
                try:
                    self.localize_widget_tree(top)
                except Exception:
                    continue
        except Exception:
            pass

    def install(self, app: Any) -> None:
        """Install global event filter and refresh timer on QApplication."""
        try:
            from PySide6.QtCore import QEvent, QObject, QTimer, Qt

            class _LocalizationEventFilter(QObject):
                def __init__(self, manager: TranslationManager):
                    super().__init__()
                    self.manager = manager

                def eventFilter(self, obj: Any, event: Any) -> bool:
                    if event.type() == QEvent.Show:
                        self.manager.localize_widget_tree(obj)
                    return False

            filt = _LocalizationEventFilter(self)
            app._lf_loc_filter = filt
            app.installEventFilter(filt)

            timer = QTimer(app)
            timer.setInterval(1000)
            timer.timeout.connect(self.refresh_all_windows)
            timer.start()
            app._lf_loc_timer = timer

            app.setLayoutDirection(Qt.RightToLeft if self.is_rtl() else Qt.LeftToRight)
            self.localize_widget_tree(app)
        except Exception:
            pass


translation_manager = TranslationManager()
loc = translation_manager

def tr(_text: Any = None, *args: Any, **kwargs: Any) -> Any:
    return translation_manager.tr(_text, *args, **kwargs)

def translate(key: Any, *args: Any, **kwargs: Any) -> Any:
    return translation_manager.translate(str(key), *args, **kwargs)

def tr_multiline(text: Any) -> Any:
    return translation_manager.tr_multiline(text)

def language() -> str:
    return translation_manager.language()

get_language = language

def system_language() -> str:
    return translation_manager.system_language()

def set_language(value: str) -> str:
    return translation_manager.set_language(value)

def subscribe(callback: TranslationCallback) -> None:
    translation_manager.subscribe(callback)

def unsubscribe(callback: TranslationCallback) -> None:
    translation_manager.unsubscribe(callback)

def install(app: Any) -> None:
    translation_manager.install(app)

def refresh_all_windows() -> None:
    translation_manager.refresh_all_windows()

def localize_widget_tree(root: Any) -> None:
    translation_manager.localize_widget_tree(root)
