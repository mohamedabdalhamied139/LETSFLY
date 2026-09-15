"""Official NVDA Controller Client integration for TableVerse.

This module intentionally does not use SAPI, pywin32, or any third-party TTS.
The only speech backend is the official NV Access NVDA Controller Client DLL.
"""
import ctypes
import os
import struct
from client.localization import tr


class NVDAController:
    SUCCESS = 0
    ERROR_RPC_UNKNOWN_IF = 1717

    def __init__(self, diagnostic=None):
        self._diagnostic = diagnostic
        self._pending = []
        self.dll = None
        self.path = None
        self.architecture = None
        self.last_error = ""
        self.last_speech_time = 0.0
        self._load()

    def set_diagnostic(self, callback):
        self._diagnostic = callback
        for msg in self._pending:
            self._emit(msg)
        self._pending.clear()

    def _emit(self, message):
        if self._diagnostic:
            try:
                self._diagnostic(f"[{tr('النطق')}] {tr(message)}")
                return
            except Exception:
                pass
        self._pending.append(message)
        if len(self._pending) > 100:
            self._pending.pop(0)

    @staticmethod
    def _pe_machine(path):
        with open(path, "rb") as f:
            f.seek(0x3C)
            pe_offset = struct.unpack("<I", f.read(4))[0]
            f.seek(pe_offset + 4)
            return struct.unpack("<H", f.read(2))[0]

    @staticmethod
    def _expected_machine():
        # Official x64 Controller Client is required for a 64-bit Python process.
        return 0x8664 if struct.calcsize("P") == 8 else 0x014C

    @staticmethod
    def _machine_name(machine):
        return {
            0x8664: "AMD64/x64",
            0x014C: "x86",
            0xAA64: "ARM64",
        }.get(machine, f"Unknown(0x{machine:04X})")

    def _candidate_paths(self):
        client_root = os.path.dirname(os.path.dirname(__file__))
        project_root = os.path.dirname(client_root)
        names = (
            "nvdaControllerClient64.dll",
            "nvdaControllerClient.dll",
        )
        roots = [
            os.path.join(client_root, "assets", "nvda"),
            os.path.join(client_root, "assets"),
            os.path.join(project_root, "nvda"),
            os.getcwd(),
        ]
        result = []
        for root in roots:
            for name in names:
                p = os.path.join(root, name)
                if p not in result:
                    result.append(p)
        return result

    def _configure(self, dll):
        required = "nvdaController_testIfRunning", "nvdaController_speakText"
        for name in required:
            if not hasattr(dll, name):
                raise RuntimeError(f"Missing official API function: {name}")

        dll.nvdaController_testIfRunning.argtypes = []
        dll.nvdaController_testIfRunning.restype = ctypes.c_long

        dll.nvdaController_speakText.argtypes = [ctypes.c_wchar_p]
        dll.nvdaController_speakText.restype = ctypes.c_long

        if hasattr(dll, "nvdaController_cancelSpeech"):
            dll.nvdaController_cancelSpeech.argtypes = []
            dll.nvdaController_cancelSpeech.restype = ctypes.c_long

        if hasattr(dll, "nvdaController_brailleMessage"):
            dll.nvdaController_brailleMessage.argtypes = [ctypes.c_wchar_p]
            dll.nvdaController_brailleMessage.restype = ctypes.c_long

        if hasattr(dll, "nvdaController_getProcessId"):
            dll.nvdaController_getProcessId.argtypes = []
            dll.nvdaController_getProcessId.restype = ctypes.c_ulong

        if hasattr(dll, "nvdaController_speakSsml"):
            # The exact SSML API signature is intentionally not used yet.
            # Plain speakText is the baseline compatibility path.
            pass

    def _load(self):
        expected = self._expected_machine()
        self._emit(
            f"بدء تحميل NVDA Controller الرسمي. المعمارية المطلوبة: "
            f"{self._machine_name(expected)}."
        )

        found = False
        for path in self._candidate_paths():
            if not os.path.isfile(path):
                continue

            found = True
            try:
                machine = self._pe_machine(path)
                self._emit(
                    f"تم العثور على DLL: {path} | "
                    f"المعمارية: {self._machine_name(machine)}."
                )

                if machine != expected:
                    self._emit("تم رفض DLL لأنها لا تطابق معمارية Python.")
                    continue

                dll = ctypes.WinDLL(path)
                self._configure(dll)

                running = dll.nvdaController_testIfRunning()
                self._emit(f"nvdaController_testIfRunning → return={running}.")

                if running != self.SUCCESS:
                    self._emit(
                        "NVDA Controller DLL محملة، لكن NVDA لم يستجب للاختبار."
                    )
                    self.last_error = f"testIfRunning returned {running}"
                    continue

                self.dll = dll
                self.path = path
                self.architecture = self._machine_name(machine)
                self._emit("تم الاتصال بـ NVDA Controller الرسمي بنجاح.")

                if hasattr(dll, "nvdaController_getProcessId"):
                    try:
                        pid = dll.nvdaController_getProcessId()
                        self._emit(f"NVDA Process ID: {pid}.")
                    except Exception as exc:
                        self._emit(f"تعذر قراءة NVDA Process ID: {exc}")
                return
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                self._emit(f"فشل تحميل/تهيئة DLL: {self.last_error}.")

        if not found:
            self.last_error = "Official NVDA Controller DLL was not found."
            self._emit(
                "لم يتم العثور على DLL الرسمية. يجب وضع ملف "
                "nvdaControllerClient.dll من مجلد x64 للحزمة الرسمية."
            )
        else:
            self._emit("لم يتم العثور على DLL رسمية متوافقة وقابلة للاتصال بـNVDA.")

    @property
    def available(self):
        return self.dll is not None

    def speak(self, text, interrupt=False, allow_duplicate=False):
        text = tr(text)
        if not self.dll:
            self._emit("speakText لم يُنفذ: NVDA Controller غير متصل.")
            return False

        text = str(text)
        try:
            if interrupt and hasattr(self.dll, "nvdaController_cancelSpeech"):
                result = self.dll.nvdaController_cancelSpeech()
                self._emit(f"cancelSpeech → return={result}.")
                if result != self.SUCCESS:
                    self._emit("cancelSpeech فشل؛ سيتم إرسال النص على أي حال.")

            import time
            now = time.monotonic()
            if not allow_duplicate and hasattr(self, "_last_spoken_text") and self._last_spoken_text == text and (now - getattr(self, "_last_spoken_at", 0.0)) < 1.8:
                return True

            result = self.dll.nvdaController_speakText(text)
            self._emit(f"speakText({text!r}) → return={result}.")
            if result == self.SUCCESS:
                self.last_speech_time = now
                self._last_spoken_text = text
                self._last_spoken_at = now
                return True

            self.last_error = f"speakText returned {result}"
            return False
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self._emit(f"استثناء في speakText: {self.last_error}.")
            return False

    def braille(self, text):
        if not self.dll or not hasattr(self.dll, "nvdaController_brailleMessage"):
            return False
        try:
            result = self.dll.nvdaController_brailleMessage(str(tr(text)))
            self._emit(f"brailleMessage → return={result}.")
            return result == self.SUCCESS
        except Exception as exc:
            self._emit(f"brailleMessage exception: {exc}.")
            return False


class ScreenReader:
    def __init__(self):
        self.controller = NVDAController()
        self._muted = False

    def set_diagnostic_callback(self, callback):
        self.controller.set_diagnostic(callback)

    def set_muted(self, muted: bool):
        self._muted = bool(muted)

    def is_muted(self) -> bool:
        return self._muted

    @property
    def nvda_available(self):
        return self.controller.available

    def speak(self, text: str, interrupt: bool = True, allow_duplicate: bool = False):
        if self._muted:
            return False
        return self.controller.speak(tr(text), interrupt=interrupt, allow_duplicate=allow_duplicate)

    def braille(self, text: str):
        return self.controller.braille(tr(text))


reader = ScreenReader()
