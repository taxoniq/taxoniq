import io


def byte_to_bases(x):
    c = (x >> 4) & 0xF
    f = x & 0xF
    cc = (c >> 2) & 0x3
    cf = c & 0x3
    fc = (f >> 2) & 0x3
    ff = f & 0x3
    return b"".join(twobit2ascii[i] for i in (cc, cf, fc, ff))


twobit2ascii = {0: b"A", 1: b"C", 2: b"G", 3: b"T"}
twobit2ascii_byte_lut = {x: byte_to_bases(x) for x in range(256)}


class NcbiNa2Decoder:
    # See ncbi-blast-2.9.0+-src/c++/src/objtools/blast/seqdb_reader/sequence_files.txt
    def __init__(self, length):
        self.length = length
        self.bases_seen = 0
        self._tail = b""

    def decompress(self, data: bytes, max_length: int = -1) -> bytes:
        seq = io.BytesIO()
        for byte in data:
            seq.write(twobit2ascii_byte_lut[byte])
        seq = self._tail + seq.getvalue()
        if len(seq) + self.bases_seen > self.length:
            seq = seq[: self.length - self.bases_seen]
        if max_length >= 0 and len(seq) > max_length:
            seq, self._tail = seq[:max_length], seq[max_length:]
        else:
            self._tail = b""
        self.bases_seen += len(seq)
        return seq

    @property
    def has_unconsumed_tail(self) -> bool:
        return bool(self._tail)

    def flush(self) -> bytes:
        tail, self._tail = self._tail, b""
        return tail


class NcbistdaaDecoder:
    # See ncbi-blast-2.9.0+-src/c++/src/objtools/blast/seqdb_reader/sequence_files.txt
    pass
