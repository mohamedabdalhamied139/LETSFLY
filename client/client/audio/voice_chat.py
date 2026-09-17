"""Real-time, table-scoped voice chat using Qt Multimedia and the existing room WebSocket."""
from __future__ import annotations

import logging
import queue
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QAudioSink, QMediaDevices

import math
import struct
from client.audio.voice_codec import encode_pcm16, decode_pcm16

logger = logging.getLogger("tableverse.voice")

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_BYTES = 2
FRAME_SAMPLES = 320
FRAME_BYTES = FRAME_SAMPLES * SAMPLE_BYTES
_MAX_PCM_QUEUE = 4
_MAX_PACKET_QUEUE = 12
_VOICE_MAGIC = b"LFS1"
_VAD_ENERGY_THRESHOLD = 320.0
_VAD_RELEASE_FRAMES = 12

class VoiceChatManager(QObject):
    stateChanged = Signal(str)
    _outputRequested = Signal()

    def __init__(self, ws_client, parent=None):
        super().__init__(parent)
        self.ws = ws_client
        self.room_id = None
        self._voice_session_active = False
        self.enabled = False
        self.muted = True
        self._source = None
        self._source_device = None
        self._sink = None
        self._sink_device = None
        self._play_queue: queue.Queue[bytes] = queue.Queue(maxsize=_MAX_PCM_QUEUE)
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="TableVerse-Voice")
        self._encode_slots = threading.BoundedSemaphore(_MAX_PACKET_QUEUE)
        self._decode_slots = threading.BoundedSemaphore(_MAX_PACKET_QUEUE)
        self._closed = False
        self._generation = 0
        self._send_busy = False
        self._voice_join_pending = False
        self._capture_pcm_buffer = bytearray()
        self._capture_lock = threading.Lock()
        self._playback_history = deque(maxlen=25)  # holds recent incoming frames for echo subtraction
        self._last_playback_time = 0.0
        self._playback_lock = threading.Lock()
        self._vad_active_countdown = 0
        self._user_volumes: dict[int, float] = {}
        self._user_mutes: set[int] = set()
        self._active_speakers: dict[int, float] = {}
        self._speakers_lock = threading.Lock()
        self._load_user_audio_preferences()
        self._play_timer = QTimer(self)
        self._play_timer.setInterval(10)
        self._play_timer.timeout.connect(self._drain_playback)
        self._outputRequested.connect(self._ensure_output)


    def _load_user_audio_preferences(self):
        try:
            from client import settings_store
            s = settings_store.load_settings().get("audio", {})
            raw_vols = s.get("voice_user_volumes", {})
            for uid_str, vol in raw_vols.items():
                try:
                    self._user_volumes[int(uid_str)] = max(0.0, min(2.0, float(vol)))
                except Exception:
                    pass
        except Exception:
            pass

    def save_user_volume(self, user_id: int, volume_scale: float):
        uid = int(user_id)
        scale = max(0.0, min(2.0, float(volume_scale)))
        self._user_volumes[uid] = scale
        try:
            from client import settings_store
            s = settings_store.load_settings()
            audio = s.setdefault("audio", {})
            vols = audio.setdefault("voice_user_volumes", {})
            vols[str(uid)] = scale
            settings_store.save_settings(s)
        except Exception:
            pass

    def get_user_volume(self, user_id: int) -> float:
        return self._user_volumes.get(int(user_id), 1.0)

    def is_user_locally_muted(self, user_id: int) -> bool:
        return int(user_id) in self._user_mutes or self.get_user_volume(user_id) <= 0.001

    def set_user_locally_muted(self, user_id: int, muted: bool):
        uid = int(user_id)
        if muted:
            self._user_mutes.add(uid)
        else:
            self._user_mutes.discard(uid)

    def get_active_speaker_ids(self) -> list[int]:
        now = time.monotonic()
        with self._speakers_lock:
            return [uid for uid, t in self._active_speakers.items() if (now - t) < 1.5]

    @staticmethod
    def _calculate_rms(pcm_bytes: bytes) -> float:
        count = len(pcm_bytes) // 2
        if count <= 0:
            return 0.0
        samples = struct.unpack("<%dh" % count, pcm_bytes[:count * 2])
        sum_squares = sum(s * s for s in samples)
        return math.sqrt(sum_squares / count)

    @staticmethod
    def _apply_volume(pcm_bytes: bytes, scale: float) -> bytes:
        if abs(scale - 1.0) < 0.01:
            return pcm_bytes
        if scale <= 0.001:
            return bytes(len(pcm_bytes))
        count = len(pcm_bytes) // 2
        if count <= 0:
            return b""
        samples = struct.unpack("<%dh" % count, pcm_bytes[:count * 2])
        scaled = [max(-32768, min(32767, int(s * scale))) for s in samples]
        return struct.pack("<%dh" % count, *scaled)

    def _is_stereo_mix_source(self) -> bool:
        """Detect if the current microphone is Stereo Mix, What U Hear, or a loopback device."""
        if not self._source_device or self._source_device.isNull():
            return False
        name = (self._source_device.description() or "").lower()
        stereo_mix_keywords = ["stereo mix", "what u hear", "wave out", "waveout", "loopback", "مزيج ستيريو", "ستيريو ميكس"]
        return any(kw in name for kw in stereo_mix_keywords)

    @staticmethod
    def _format() -> QAudioFormat:
        fmt = QAudioFormat()
        fmt.setSampleRate(SAMPLE_RATE)
        fmt.setChannelCount(CHANNELS)
        try:
            fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        except AttributeError:
            fmt.setSampleFormat(QAudioFormat.Int16)
        return fmt

    @staticmethod
    def _device_supports_voice(device) -> bool:
        try:
            return bool(device and not device.isNull() and device.isFormatSupported(VoiceChatManager._format()))
        except Exception:
            return False

    def join_room(self, room_id: str):
        if self._closed:
            return
        room_id = str(room_id or "")
        if not room_id:
            self.leave_room()
            return
        if self.room_id == room_id:
            # Reconnects explicitly suspend the session before rebinding. Do not
            # clear an active voice session merely because a room snapshot arrived.
            return
        self.leave_room()
        self._generation += 1
        self.room_id = room_id
        self._voice_session_active = False
        self._announce("voice_connection_restored" if self.enabled else "voice_ready")

    def suspend_for_reconnect(self):
        if self.room_id and self._voice_session_active:
            self.ws.send_json({"type": "voice_leave"})
        self._voice_session_active = False
        self.stop_microphone(silent=True)

    @property
    def in_voice_chat(self) -> bool:
        """Whether the player has explicitly joined the table voice conversation."""
        return bool(self._voice_session_active and self.room_id)

    def toggle_voice_session(self) -> bool:
        """Enter/leave voice chat without affecting the normal table connection."""
        if self._closed or not self.room_id:
            self._announce("voice_connection_unavailable")
            return False
        if self._voice_session_active:
            self.leave_voice_session()
            return False
        if self._voice_join_pending:
            return True
        if not self._request_voice_join():
            self._announce("voice_connection_unavailable")
            return False
        return True

    def leave_voice_session(self):
        if self.room_id and self._voice_session_active:
            self.ws.send_json({"type": "voice_leave"})
        was_active = self._voice_session_active or self._voice_join_pending
        self._voice_session_active = False
        self._generation += 1
        self._voice_join_pending = False
        self.stop_microphone(silent=True)
        self._capture_pcm_buffer.clear()
        self._play_timer.stop()
        if was_active:
            self._announce("voice_exited")
        self._clear_playback()
        self.muted = False

    def _request_voice_join(self):
        if self._closed or not self.room_id or self._voice_session_active or self._voice_join_pending:
            return False
        if not self.ws.send_json({"type": "voice_join"}):
            return False
        self._voice_join_pending = True
        return True

    def handle_server_event(self, event: dict):
        if not isinstance(event, dict):
            return
        if event.get("type") != "voice_joined":
            return
        room_id = str(event.get("room_id") or "")
        if not self.room_id or room_id != str(self.room_id) or not self._voice_join_pending:
            return
        self._voice_join_pending = False
        self._voice_session_active = True
        self._ensure_output()
        # Joining voice chat never opens the microphone automatically.
        # The user must explicitly unmute with M.
        self.stop_microphone(silent=True)
        self.muted = True
        from client.audio.sound_engine import sound_engine
        sound_engine.play_event("VOICE_JOINED")
        self._announce("voice_entered_muted")

    def activate_voice_session(self, start_microphone: bool = False):
        if self._closed or not self.room_id or self._voice_session_active:
            return False
        if not self._request_voice_join():
            return False
        # The server acknowledgement is authoritative. For callers that do not
        # request microphone capture, the session still becomes active on ack.
        # start_microphone is intentionally handled there to avoid sending audio
        # before the server has registered voice membership.
        return True

    def leave_room(self):
        self.leave_voice_session()
        self.room_id = None

    def toggle_mute(self) -> bool:
        if not self.room_id or not self._voice_session_active:
            return False
        from client.audio.sound_engine import sound_engine
        if self.muted:
            self.muted = False
            if not self.start_microphone():
                self.muted = True
                return True
            sound_engine.play_event("MIC_ON")
            self._announce("microphone_unmuted")
        else:
            self.muted = True
            self.stop_microphone(silent=True)
            sound_engine.play_event("MIC_OFF")
            self._announce("microphone_muted")
        return self.muted

    def start_microphone(self, announce: bool = True) -> bool:
        if self._closed or not self.room_id:
            self._announce("voice_connection_unavailable")
            return False
        if self._source is not None:
            return True
        try:
            device = QMediaDevices.defaultAudioInput()
            if device.isNull():
                self._announce("microphone_unavailable")
                return False
            fmt = self._select_input_format(device)
            if fmt is None:
                self._announce("microphone_unavailable")
                logger.warning("No supported microphone format is available")
                return False
            self._input_format = fmt
            self._capture_pcm_buffer.clear()
            self._source_device = device
            self._source = QAudioSource(device, fmt, self)
            self._source.setBufferSize(FRAME_BYTES * 4)
            io = self._source.start()
            if io is None:
                self._source.deleteLater()
                self._source = None
                self._announce("microphone_unavailable")
                return False
            io.readyRead.connect(lambda io=io: self._capture_ready(io))
            self.enabled = True
            if announce:
                self._announce("microphone_enabled")
            return True
        except Exception:
            logger.exception("Microphone initialization failed")
            self._source = None
            self._announce("microphone_unavailable")
            return False

    def stop_microphone(self, silent: bool = False):
        src = self._source
        self._source = None
        self._source_device = None
        if src is not None:
            try:
                src.stop()
            except Exception:
                logger.debug("Audio source stop failed", exc_info=True)
            try:
                src.deleteLater()
            except Exception:
                pass
        was_enabled = self.enabled
        self.enabled = False
        if was_enabled and not silent:
            self._announce("microphone_disabled")

    def _capture_ready(self, io):
        if self._closed or self.muted or not self.room_id:
            return
        try:
            available = int(io.bytesAvailable())
            if available <= 0:
                return
            # Read a bounded native-device chunk, then normalize it off the Qt UI path.
            read_size = min(available, FRAME_BYTES * 8)
            data = bytes(io.read(read_size))
            if not data:
                return
            if not self._encode_slots.acquire(blocking=False):
                return
            fmt = self._input_format
            future = self._executor.submit(self._prepare_and_send, data, fmt, self._generation)
            future.add_done_callback(lambda _f: self._encode_slots.release())
        except Exception:
            logger.exception("Microphone capture failed")


    @staticmethod
    def _select_input_format(device):
        target = VoiceChatManager._format()
        try:
            if device.isFormatSupported(target):
                return target
            preferred = device.preferredFormat()
            if preferred.isValid() and preferred.sampleFormat() in (
                QAudioFormat.SampleFormat.Int16,
                QAudioFormat.SampleFormat.Int32,
                QAudioFormat.SampleFormat.Float,
                QAudioFormat.SampleFormat.UInt8,
            ):
                return preferred
        except Exception:
            logger.debug("Failed to negotiate microphone format", exc_info=True)
        return None

    @staticmethod
    def _native_pcm16(data: bytes, fmt: QAudioFormat) -> bytes:
        import struct
        rate = int(fmt.sampleRate())
        channels = max(1, int(fmt.channelCount()))
        sample_format = fmt.sampleFormat()
        if sample_format == QAudioFormat.SampleFormat.Int16:
            raw = data[:len(data) - (len(data) % 2)]
            if channels == 1 and rate == SAMPLE_RATE:
                return raw
            vals = list(struct.unpack("<%dh" % (len(raw)//2), raw))
        elif sample_format == QAudioFormat.SampleFormat.Int32:
            raw = data[:len(data) - (len(data) % 4)]
            vals32 = struct.unpack("<%di" % (len(raw)//4), raw)
            vals = [max(-32768, min(32767, int(v >> 16))) for v in vals32]
        elif sample_format == QAudioFormat.SampleFormat.Float:
            raw = data[:len(data) - (len(data) % 4)]
            valsf = struct.unpack("<%df" % (len(raw)//4), raw)
            vals = [max(-32768, min(32767, int(float(v) * 32767.0))) for v in valsf]
        elif sample_format == QAudioFormat.SampleFormat.UInt8:
            vals = [(int(v) - 128) << 8 for v in data]
        else:
            return b""
        if channels > 1:
            frames = len(vals) // channels
            vals = [sum(vals[i*channels:(i+1)*channels]) // channels for i in range(frames)]
        if rate == SAMPLE_RATE:
            return struct.pack("<%dh" % len(vals), *vals) if vals else b""
        if not vals:
            return b""
        out_count = max(1, round(len(vals) * SAMPLE_RATE / rate))
        out = []
        scale = (len(vals) - 1) / max(1, out_count - 1)
        for i in range(out_count):
            pos = i * scale
            left = int(pos)
            right = min(left + 1, len(vals) - 1)
            frac = pos - left
            value = int(vals[left] + (vals[right] - vals[left]) * frac)
            out.append(max(-32768, min(32767, value)))
        return struct.pack("<%dh" % len(out), *out)

    def _filter_echo_from_frame(self, frame: bytes) -> bytes:
        """Suppress speaker audio and screen reader speech from leaking into microphone."""
        now = time.monotonic()
        # 1. Screen reader speech ducking: if NVDA just spoke within 0.35s, duck input
        try:
            from client.accessibility.reader import reader
            ctrl = getattr(reader, "_controller", None)
            if ctrl and hasattr(ctrl, "last_speech_time"):
                if (now - ctrl.last_speech_time) < 0.35:
                    return bytes(len(frame))
        except Exception:
            pass

        # 2. Stereo Mix / Loopback suppression
        if self._is_stereo_mix_source():
            with self._playback_lock:
                time_since_playback = now - self._last_playback_time
                if time_since_playback < 0.45:
                    return bytes(len(frame))
        return frame

    def _prepare_and_send(self, data: bytes, fmt, generation: int):
        if self._closed or self.muted or not self.room_id or not self._voice_session_active:
            return
        try:
            pcm = self._native_pcm16(data, fmt)
            if not pcm:
                return
            # QAudioSource.readyRead does not guarantee frame-sized chunks.
            # Keep normalized PCM between callbacks so common Windows devices
            # (48 kHz/stereo, etc.) cannot produce only sub-frame chunks that are
            # silently discarded.
            with self._capture_lock:
                self._capture_pcm_buffer.extend(pcm)
                while len(self._capture_pcm_buffer) >= FRAME_BYTES:
                    frame = bytes(self._capture_pcm_buffer[:FRAME_BYTES])
                    del self._capture_pcm_buffer[:FRAME_BYTES]
                    frame = self._filter_echo_from_frame(frame)
                    # Voice Activity Detection (VAD) / Noise Gate
                    rms = self._calculate_rms(frame)
                    if rms >= _VAD_ENERGY_THRESHOLD:
                        self._vad_active_countdown = _VAD_RELEASE_FRAMES
                    elif self._vad_active_countdown > 0:
                        self._vad_active_countdown -= 1
                    else:
                        # Below noise floor and release window elapsed; suppress packet to save network and prevent background hiss
                        continue

                    packet = encode_pcm16(frame, SAMPLE_RATE)
                    if packet and generation == self._generation and not self._closed and not self.muted and self.room_id and self._voice_session_active:
                        if not self.ws.send_bytes(packet):
                            logger.debug("Voice packet send returned false")
        except Exception:
            logger.exception("Microphone normalization/send failed")

    def _encode_and_send(self, pcm: bytes):
        if self._closed or self.muted or not self.room_id:
            return
        try:
            packet = encode_pcm16(pcm, SAMPLE_RATE)
            if packet:
                self.ws.send_bytes(packet)
        except Exception:
            logger.debug("Voice send failed", exc_info=True)

    def receive_packet(self, data: bytes):
        if self._closed or not self.room_id:
            return
        # Server frame: LFS1 + sender_user_id(uint32) + LFV1 + ADPCM packet.
        if not isinstance(data, (bytes, bytearray)) or len(data) < 17 or bytes(data[:4]) != _VOICE_MAGIC:
            return
        sender_id = struct.unpack_from(">I", data, 4)[0]
        if self.is_user_locally_muted(sender_id):
            return

        payload = bytes(data[8:])
        if len(payload) > 4096 or len(payload) < 9 or payload[:4] != b"LFV1" or not self._decode_slots.acquire(blocking=False):
            return
        future = self._executor.submit(self._decode_and_queue, payload, sender_id, self._generation)
        future.add_done_callback(lambda _f: self._decode_slots.release())

    def _decode_and_queue(self, payload: bytes, sender_id: int, generation: int):
        if self._closed:
            return
        try:
            pcm = decode_pcm16(payload)
            if generation != self._generation or not pcm:
                return

            # Apply per-user volume scaling
            user_vol = self.get_user_volume(sender_id)
            if abs(user_vol - 1.0) >= 0.01:
                pcm = self._apply_volume(pcm, user_vol)
            if not pcm:
                return

            # Track active speaker
            with self._speakers_lock:
                self._active_speakers[sender_id] = time.monotonic()

            output_fmt = getattr(self, "_output_format", None)
            if output_fmt is not None:
                pcm = self._pcm16_for_output(pcm, output_fmt)
            if not pcm:
                return

            # Drop-oldest queue policy to strictly prevent audio latency accumulation
            try:
                self._play_queue.put_nowait(pcm)
            except queue.Full:
                try:
                    self._play_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._play_queue.put_nowait(pcm)
                except queue.Full:
                    return
            self._outputRequested.emit()
        except Exception:
            logger.debug("Voice decode failed", exc_info=True)

    @staticmethod
    def _select_output_format(device):
        target = VoiceChatManager._format()
        try:
            if device.isFormatSupported(target):
                return target
            preferred = device.preferredFormat()
            if preferred.isValid() and preferred.sampleFormat() in (
                QAudioFormat.SampleFormat.Int16,
                QAudioFormat.SampleFormat.Int32,
                QAudioFormat.SampleFormat.Float,
                QAudioFormat.SampleFormat.UInt8,
            ):
                return preferred
        except Exception:
            logger.debug("Failed to negotiate speaker format", exc_info=True)
        return None

    @staticmethod
    def _resample_pcm16(pcm: bytes, source_rate: int, target_rate: int) -> bytes:
        import struct
        if source_rate == target_rate or not pcm:
            return pcm
        count = len(pcm) // 2
        if count <= 0:
            return b""
        samples = struct.unpack("<%dh" % count, pcm[:count * 2])
        out_count = max(1, round(count * target_rate / source_rate))
        if out_count == 1:
            return struct.pack("<h", samples[0])
        scale = (count - 1) / (out_count - 1)
        out = []
        for i in range(out_count):
            pos = i * scale
            left = int(pos)
            right = min(left + 1, count - 1)
            frac = pos - left
            value = int(samples[left] + (samples[right] - samples[left]) * frac)
            out.append(max(-32768, min(32767, value)))
        return struct.pack("<%dh" % len(out), *out)

    @staticmethod
    def _pcm16_for_output(pcm: bytes, fmt: QAudioFormat) -> bytes:
        import struct
        rate = max(1, int(fmt.sampleRate()))
        channels = max(1, int(fmt.channelCount()))
        pcm = VoiceChatManager._resample_pcm16(pcm, SAMPLE_RATE, rate)
        count = len(pcm) // 2
        if count <= 0:
            return b""
        samples = struct.unpack("<%dh" % count, pcm[:count * 2])
        sample_format = fmt.sampleFormat()
        if channels > 1:
            expanded = []
            for sample in samples:
                expanded.extend([sample] * channels)
            samples = expanded
        if sample_format == QAudioFormat.SampleFormat.Int16:
            return struct.pack("<%dh" % len(samples), *samples)
        if sample_format == QAudioFormat.SampleFormat.Int32:
            return struct.pack("<%di" % len(samples), *(int(v) << 16 for v in samples))
        if sample_format == QAudioFormat.SampleFormat.Float:
            return struct.pack("<%df" % len(samples), *(float(v) / 32768.0 for v in samples))
        if sample_format == QAudioFormat.SampleFormat.UInt8:
            return bytes(max(0, min(255, (int(v) >> 8) + 128)) for v in samples)
        return b""

    def _ensure_output(self):
        if self._closed or not self.room_id or self._sink is not None:
            return
        try:
            device = QMediaDevices.defaultAudioOutput()
            if device.isNull():
                self._announce("voice_connection_unavailable")
                return
            fmt = self._select_output_format(device)
            if fmt is None:
                self._announce("voice_connection_unavailable")
                logger.warning("No supported speaker format is available")
                return
            self._output_format = fmt
            self._sink_device = device
            self._sink = QAudioSink(device, fmt, self)
            self._sink.setBufferSize(FRAME_BYTES * 8)
            self._sink_device_io = self._sink.start()
            if self._sink_device_io is None:
                self._sink = None
                self._announce("voice_connection_unavailable")
                return
            self._play_timer.start()
        except Exception:
            logger.exception("Voice output initialization failed")
            self._sink = None
            self._announce("voice_connection_unavailable")

    def _drain_playback(self):
        if self._closed or self._sink is None:
            self._play_timer.stop()
            return
        io = getattr(self, "_sink_device_io", None)
        if io is None:
            return
        # Keep the playback buffer bounded. QAudioSink reports how much room is available.
        try:
            free = max(0, int(self._sink.bytesFree()))
        except Exception:
            free = FRAME_BYTES
        if free <= 0:
            return
        budget = min(free, FRAME_BYTES * 2)
        while budget > 0:
            try:
                pcm = self._play_queue.get_nowait()
            except queue.Empty:
                break
            chunk = pcm[:budget]
            try:
                written = int(io.write(chunk))
                if written > 0:
                    with self._playback_lock:
                        self._last_playback_time = time.monotonic()
            except Exception:
                logger.debug("Voice playback write failed", exc_info=True)
                return
            if written < len(pcm):
                remainder = pcm[max(0, written):]
                try:
                    self._play_queue.put_nowait(remainder)
                except queue.Full:
                    pass
                break
            budget -= max(1, written)

    def _clear_playback(self):
        while True:
            try:
                self._play_queue.get_nowait()
            except queue.Empty:
                break
        sink = self._sink
        self._sink = None
        self._sink_device = None
        self._sink_device_io = None
        if sink is not None:
            try:
                sink.stop()
            except Exception:
                logger.debug("Audio sink stop failed", exc_info=True)
            try:
                sink.deleteLater()
            except Exception:
                pass

    def _announce(self, state: str):
        from client.localization import tr
        messages = {
            "microphone_enabled": "الميكروفون مفتوح.",
            "microphone_disabled": "الميكروفون مقفول.",
            "microphone_unavailable": "الميكروفون غير متاح.",
            "voice_connection_unavailable": "الاتصال الصوتي غير متاح.",
            "voice_connection_restored": "الاتصال الصوتي عاد.",
            "voice_ready": "الصوت متاح على الطاولة.",
            "voice_entered": "تم الدخول إلى المحادثة الصوتية.",
            "voice_entered_muted": "تم الدخول إلى المحادثة الصوتية، والميكروفون مقفول.",
            "voice_entered_no_microphone": "تم الدخول إلى المحادثة الصوتية، لكن الميكروفون غير متاح.",
            "voice_exited": "تم الخروج من المحادثة الصوتية.",
            "microphone_muted": "تم كتم الميكروفون.",
            "microphone_unmuted": "تم إلغاء كتم الميكروفون.",
        }
        text = messages.get(state)
        if text:
            self.stateChanged.emit(tr(text))

    def shutdown(self):
        if self._closed:
            return
        self._closed = True
        self.stop_microphone(silent=True)
        self.leave_room()
        self._executor.shutdown(wait=False, cancel_futures=True)
