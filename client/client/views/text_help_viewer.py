"""Accessible In-Game Notepad-style Text Help Viewer for TableVerse."""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QPlainTextEdit
from PySide6.QtGui import QTextCursor
from PySide6.QtCore import Qt
from client.accessibility.reader import reader
from client.localization import tr, tr_multiline, language, subscribe


class TextHelpViewerDialog(QDialog):
    """Accessible Read-Only Text Viewer providing native Notepad-like navigation for screen readers.
    
    Supports:
    - Character-by-character reading (Left / Right)
    - Word-by-word reading (Ctrl + Left / Right)
    - Line-by-line reading (Up / Down)
    - Document navigation (Home / End, Ctrl + Home / End, PageUp / PageDown)
    - Text selection (Shift + Arrows)
    - Clipboard copying (Ctrl + C / Ctrl + A)
    - Instant exit (Escape)
    """

    def __init__(self, parent=None, title: str = "شرح وقواعد اللعبة", text_content: str = "", text_sources: dict[str, str] | None = None):
        super().__init__(parent)
        self._source_title = title
        self.setWindowTitle(tr(title))
        self.setAccessibleName(tr(title))
        self.resize(780, 560)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.setStyleSheet("""
            QDialog {
                background-color: #1e293b;
                color: #f8fafc;
            }
            QPlainTextEdit {
                background-color: #ffffff;
                color: #0f172a;
                border: 2px solid #3b82f6;
                border-radius: 8px;
                padding: 12px;
                font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
                font-size: 16px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)

        self.text_edit = QPlainTextEdit(self)
        self.text_edit.setReadOnly(True)
        self.text_edit.setTextInteractionFlags(Qt.TextSelectableByKeyboard | Qt.TextSelectableByMouse)
        self.text_edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        sources = dict(text_sources or {})
        if not sources:
            sources["ar"] = text_content
            sources["en"] = text_content
        self._source_texts = {
            lang_code: "\n".join(line.strip() for line in str(content or "").splitlines() if line.strip())
            for lang_code, content in sources.items()
        }
        self._source_text = self._source_texts.get(language()) or next(iter(self._source_texts.values()), "")
        self.text_edit.setPlainText(self._source_text)
        self.text_edit.setLayoutDirection(Qt.LeftToRight if language() == "en" else Qt.RightToLeft)
        subscribe(self._on_language_changed)
        layout.addWidget(self.text_edit)

    def showEvent(self, event):
        super().showEvent(event)
        self.text_edit.moveCursor(QTextCursor.Start)
        self.text_edit.setFocus(Qt.OtherFocusReason)
        reader.speak(f"{self.windowTitle()}. {tr('اضغط إسكيب للرجوع.')}", interrupt=True)

    def _on_language_changed(self, _value):
        self.setWindowTitle(tr(self._source_title))
        self.setAccessibleName(tr(self._source_title))
        lang_code = language()
        self._source_text = self._source_texts.get(lang_code) or self._source_texts.get("en") or self._source_texts.get("ar") or ""
        self.text_edit.setPlainText(self._source_text)
        self.text_edit.setLayoutDirection(Qt.LeftToRight if lang_code == "en" else Qt.RightToLeft)

    def closeEvent(self, event):
        try:
            from client.localization import unsubscribe
            unsubscribe(self._on_language_changed)
        except Exception:
            pass
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.accept()
            return
        super().keyPressEvent(event)
