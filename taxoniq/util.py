import io


def byte_to_bases(x):
    c = (x >> 4) & 0xf
    f = x & 0xf
    cc = (c >> 2) & 0x3
    cf = c & 0x3
    fc = (f >> 2) & 0x3
    ff = f & 0x3
    return b''.join(twobit2ascii[i] for i in (cc, cf, fc, ff))


twobit2ascii = {0: b"A", 1: b"C", 2: b"G", 3: b"T"}
twobit2ascii_byte_lut = {x: byte_to_bases(x) for x in range(256)}


class TwoBitDecoder:
    def __init__(self, length):
        self.length = length
        self.bases_seen = 0

    def decompress(self, data: bytes) -> bytes:
        seq = io.BytesIO()
        for byte in data:
            seq.write(twobit2ascii_byte_lut[byte])
        seq = seq.getvalue()
        if len(seq) + self.bases_seen > self.length:
            seq = seq[:self.length - self.bases_seen]
        self.bases_seen += len(seq)
        return seq

    def flush(self) -> bytes:
        return b''
