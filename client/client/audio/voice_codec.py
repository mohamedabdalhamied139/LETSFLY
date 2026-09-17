"""Small, dependency-free IMA ADPCM codec for low-bandwidth table voice."""
from __future__ import annotations
import struct

_MAGIC = b"LFV1"
_INDEX_TABLE = (-1, -1, -1, -1, 2, 4, 6, 8)
_STEP_TABLE = (7,8,9,10,11,12,13,14,16,17,19,21,23,25,28,31,34,37,41,45,50,55,60,66,73,80,88,97,107,118,130,143,157,173,190,209,230,253,279,307,337,371,408,449,494,544,598,658,724,796,876,963,1060,1166,1282,1411,1552,1707,1878,2066,2272,2499,2749,3024,3327,3660,4026,4428,4877,5372,5894,6484,7132,7846,8630,9493,10442,11487,12635,13899,15289,16818,18500,20350,22385,24623,27086,29801,32767)

def _encode_nibble(sample: int, predictor: int, index: int) -> tuple[int, int, int]:
    step = _STEP_TABLE[index]
    diff = sample - predictor
    sign = 8 if diff < 0 else 0
    if diff < 0:
        diff = -diff
    delta = 0
    temp = step
    if diff >= temp:
        delta |= 4
        diff -= temp
    temp >>= 1
    if diff >= temp:
        delta |= 2
        diff -= temp
    temp >>= 1
    if diff >= temp:
        delta |= 1
    code = delta | sign

    diffq = step >> 3
    if delta & 4:
        diffq += step
    if delta & 2:
        diffq += step >> 1
    if delta & 1:
        diffq += step >> 2
    predictor += -diffq if sign else diffq
    predictor = max(-32768, min(32767, predictor))
    index += _INDEX_TABLE[delta]
    index = max(0, min(88, index))
    return code, predictor, index

def _decode_nibble(code: int, predictor: int, index: int) -> tuple[int, int, int]:
    step = _STEP_TABLE[index]
    diffq = step >> 3
    if code & 4:
        diffq += step
    if code & 2:
        diffq += step >> 1
    if code & 1:
        diffq += step >> 2
    predictor += -diffq if code & 8 else diffq
    predictor = max(-32768, min(32767, predictor))
    index += _INDEX_TABLE[code & 7]
    index = max(0, min(88, index))
    return predictor, predictor, index

def encode_pcm16(pcm: bytes, sample_rate: int = 16000) -> bytes:
    """Encode little-endian mono PCM16 into one self-contained ADPCM packet."""
    if not pcm:
        return b""
    sample_count = len(pcm) // 2
    if sample_count <= 0:
        return b""
    samples = struct.unpack("<%dh" % sample_count, pcm[:sample_count * 2])
    predictor = int(samples[0])
    index = 0
    out = bytearray(_MAGIC)
    out.extend(struct.pack("<hBH", predictor, index, sample_count))
    nibbles = []
    for sample in samples[1:]:
        code, predictor, index = _encode_nibble(int(sample), predictor, index)
        nibbles.append(code)
    for i in range(0, len(nibbles), 2):
        lo = nibbles[i]
        hi = nibbles[i + 1] if i + 1 < len(nibbles) else 0
        out.append(lo | (hi << 4))
    return bytes(out)

def decode_pcm16(packet: bytes) -> bytes:
    """Decode one self-contained ADPCM packet into little-endian mono PCM16."""
    if len(packet) < 9 or packet[:4] != _MAGIC:
        return b""
    predictor, index, sample_count = struct.unpack_from("<hBH", packet, 4)
    if not (1 <= sample_count <= 4096 and 0 <= index <= 88):
        return b""
    samples = [predictor]
    for byte in packet[9:]:
        for code in (byte & 0x0F, (byte >> 4) & 0x0F):
            if len(samples) >= sample_count:
                break
            predictor, _, index = _decode_nibble(code, predictor, index)
            samples.append(predictor)
    if len(samples) != sample_count:
        return b""
    return struct.pack("<%dh" % len(samples), *samples)
