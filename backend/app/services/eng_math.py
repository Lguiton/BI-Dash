"""Engineering-math toolbox for the Computer Engineering Mathematician: Gray code, ASCII, binary/hex/octal/BCD, bitwise ops, parity, checksums, CRC, Hamming(7,4), endianness.
Pure functions over small integers and short strings. Reuses services/cpe_lab for base conversion, two's complement, IEEE 754, Boolean logic and architecture formulas."""
from __future__ import annotations

from app.services import cpe_lab

MAX_TEXT = 256
MAX_SEQ_BITS = 6


class EngMathError(Exception):
    pass


def _int(v, name="value", lo=None, hi=None) -> int:
    if isinstance(v, bool):
        raise EngMathError(f"{name} must be a whole number.")
    if isinstance(v, str):
        t = v.strip().lower().replace("_", "").replace(" ", "")
        try:
            v = int(t, 0) if t[:2] in ("0x", "0b", "0o") else int(t, 10) if t.lstrip("-").isdigit() else int(t, 16)
        except ValueError:
            raise EngMathError(f"'{v}' isn't a number I can read. Use 13, 0b1101 or 0xD.") from None
    if not isinstance(v, int):
        if isinstance(v, float) and v == int(v):
            v = int(v)
        else:
            raise EngMathError(f"{name} must be a whole number.")
    if lo is not None and v < lo or hi is not None and v > hi:
        raise EngMathError(f"{name} must be between {lo} and {hi}.")
    return v


def _bits(n: int, w: int) -> str:
    return format(n & ((1 << w) - 1), f"0{w}b")


def gray(value=None, direction: str = "to_gray", bits: int = 8, sequence_bits: int | None = None) -> dict:
    """Binary to Gray code (g = b XOR b>>1) and back; or list the whole n-bit Gray sequence."""
    if sequence_bits:
        n = _int(sequence_bits, "sequence_bits", 1, MAX_SEQ_BITS)
        rows = [{"n": i, "binary": _bits(i, n), "gray": _bits(i ^ (i >> 1), n)} for i in range(1 << n)]
        return {"bits": n, "sequence": rows, "lesson": "Neighbouring Gray codes differ in exactly one bit (including the wrap from the last back to the first), which is why rotary encoders use them."}
    w = _int(bits, "bits", 1, 64)
    if isinstance(value, str) and len(value.strip()) > 1 and set(value.strip()) <= {"0", "1"}:
        value = "0b" + value.strip()                      # a string of 0s and 1s is read as the bit pattern
    v = _int(value, "value", 0, (1 << w) - 1)
    if direction == "from_gray":
        b, t = v, v >> 1
        steps = [f"Gray {_bits(v, w)}: the top bit is kept; each next binary bit = previous binary bit XOR this Gray bit."]
        while t:
            b ^= t
            t >>= 1
        return {"gray": _bits(v, w), "binary": _bits(b, w), "decimal": b, "steps": steps}
    g = v ^ (v >> 1)
    return {"binary": _bits(v, w), "decimal": v, "gray": _bits(g, w), "gray_hex": hex(g)[2:].upper(), "steps": [f"gray = binary XOR (binary >> 1) = {_bits(v, w)} XOR {_bits(v >> 1, w)} = {_bits(g, w)}"]}


def ascii_tool(text: str | None = None, code=None) -> dict:
    """Text to ASCII codes (decimal, hex, binary), or one code to its character, with control-character names."""
    ctrl = {0: "NUL", 7: "BEL", 8: "BS", 9: "TAB", 10: "LF", 13: "CR", 27: "ESC", 32: "SPACE", 127: "DEL"}
    if code is not None:
        c = _int(code, "code", 0, 127)
        ch = chr(c)
        return {"decimal": c, "hex": f"{c:02X}", "binary": _bits(c, 8), "character": ch if 32 < c < 127 else ctrl.get(c, f"control character {c}"),
                "note": "Digits '0'-'9' are 48-57, 'A'-'Z' are 65-90 and 'a'-'z' are 97-122: a lowercase letter is its uppercase letter + 32 (flip bit 5)."}
    t = text or ""
    if not t or len(t) > MAX_TEXT:
        raise EngMathError(f"Give 1 to {MAX_TEXT} characters.")
    rows = []
    for ch in t:
        o = ord(ch)
        rows.append({"char": ch if o > 32 and o != 127 else ctrl.get(o, f"U+{o:04X}"), "decimal": o, "hex": f"{o:02X}" if o < 256 else f"U+{o:04X}", "binary": _bits(o, 8) if o < 256 else None})
    plain = all(ord(c) < 128 for c in t)
    return {"characters": rows, "hex_string": " ".join(r["hex"] for r in rows), "pure_ascii": plain,
            "note": "ASCII covers 0-127 only." + ("" if plain else " Characters above 127 are not ASCII; they are shown by Unicode code point.")}


def bitop(op: str, a, b=None, width: int = 8) -> dict:
    w = _int(width, "width", 1, 64)
    mask = (1 << w) - 1
    A = _int(a, "a", -(1 << (w - 1)), mask) & mask
    op = (op or "").lower()
    if op == "not":
        r, expr = ~A & mask, f"NOT {_bits(A, w)}"
    elif op in ("and", "or", "xor", "nand", "nor", "xnor"):
        B = _int(b, "b", -(1 << (w - 1)), mask) & mask
        base = {"and": A & B, "or": A | B, "xor": A ^ B, "nand": ~(A & B), "nor": ~(A | B), "xnor": ~(A ^ B)}[op]
        r, expr = base & mask, f"{_bits(A, w)} {op.upper()} {_bits(B, w)}"
    elif op in ("shl", "shr", "sar", "rol", "ror"):
        n = _int(b, "shift amount", 0, w)
        if op == "shl":
            r = (A << n) & mask
        elif op == "shr":
            r = A >> n
        elif op == "sar":
            sv = A - (1 << w) if A >> (w - 1) else A
            r = (sv >> n) & mask
        elif op == "rol":
            r = ((A << n) | (A >> (w - n))) & mask if n else A
        else:
            r = ((A >> n) | (A << (w - n))) & mask if n else A
        expr = f"{_bits(A, w)} {op.upper()} {n}"
    else:
        raise EngMathError("op must be one of and, or, xor, nand, nor, xnor, not, shl, shr, sar, rol, ror.")
    s = r - (1 << w) if r >> (w - 1) else r
    return {"expression": expr, "width": w, "result_binary": _bits(r, w), "result_hex": f"{r:0{(w + 3) // 4}X}", "unsigned": r, "signed": s,
            "note": "shl multiplies by 2^n (bits that fall off the top are lost); shr divides unsigned values; sar keeps the sign bit; rol/ror wrap bits around."}


def parity(value, bits: int = 8) -> dict:
    w = _int(bits, "bits", 1, 64)
    v = _int(value, "value", 0, (1 << w) - 1)
    ones = bin(v).count("1")
    return {"binary": _bits(v, w), "ones": ones, "even_parity_bit": ones % 2, "odd_parity_bit": 1 - ones % 2,
            "with_even_parity": _bits(v, w) + str(ones % 2), "note": "Even parity makes the total number of 1s even. One parity bit detects any single-bit error but cannot say which bit, and misses two-bit errors."}


def bcd(value=None, bcd_text: str | None = None) -> dict:
    if bcd_text is not None:
        t = bcd_text.replace(" ", "")
        if not t or len(t) % 4 or set(t) - {"0", "1"}:
            raise EngMathError("BCD needs groups of 4 bits, e.g. 0100 0010.")
        digs = [int(t[i:i + 4], 2) for i in range(0, len(t), 4)]
        if any(d > 9 for d in digs):
            raise EngMathError("A BCD group can only be 0000 to 1001 (0 to 9).")
        return {"bcd": " ".join(t[i:i + 4] for i in range(0, len(t), 4)), "decimal": int("".join(map(str, digs)))}
    v = _int(value, "value", 0, 10 ** 12)
    return {"decimal": v, "bcd": " ".join(format(int(d), "04b") for d in str(v)), "plain_binary": bin(v)[2:], "note": "BCD stores each decimal digit in 4 bits, so it needs more bits than plain binary but converts to display digits trivially."}


def checksum(data, kind: str = "sum8") -> dict:
    bs = _bytes(data)
    k = (kind or "").lower()
    if k == "sum8":
        r, w = sum(bs) & 0xFF, 8
    elif k == "xor8":
        r = 0
        for x in bs:
            r ^= x
        w = 8
    elif k == "twos8":
        r, w = (-sum(bs)) & 0xFF, 8
    elif k == "crc8":
        r, w = _crc(bs, 8, 0x07, 0x00), 8
    elif k in ("crc16", "crc16-ccitt"):
        r, w = _crc(bs, 16, 0x1021, 0xFFFF), 16
    elif k == "crc16-modbus":
        r, w = _crc_reflected(bs), 16
    else:
        raise EngMathError("kind must be sum8, xor8, twos8, crc8, crc16-ccitt or crc16-modbus.")
    return {"bytes": " ".join(f"{b:02X}" for b in bs), "kind": k, "hex": f"{r:0{w // 4}X}", "binary": _bits(r, w), "decimal": r,
            "note": "crc8 = poly 0x07 init 0; crc16-ccitt (CCITT-FALSE) = poly 0x1021 init 0xFFFF; crc16-modbus = reflected 0xA001 init 0xFFFF (low byte sent first). Check which variant your device uses."}


def _bytes(data) -> list[int]:
    if isinstance(data, list):
        out = [_int(x, "byte", 0, 255) for x in data]
    else:
        t = str(data or "").replace(",", " ").split()
        out = [_int(x if x.lower().startswith(("0x", "0b")) else "0x" + x, "byte", 0, 255) for x in t]
    if not out or len(out) > 512:
        raise EngMathError("Give 1 to 512 bytes, as hex like '31 32 33'.")
    return out


def _crc(bs, width, poly, init):
    top, mask, c = 1 << (width - 1), (1 << width) - 1, init
    for b in bs:
        c ^= b << (width - 8)
        for _ in range(8):
            c = ((c << 1) ^ poly) & mask if c & top else (c << 1) & mask
    return c


def _crc_reflected(bs):
    c = 0xFFFF
    for b in bs:
        c ^= b
        for _ in range(8):
            c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
    return c


def hamming74(data=None, received: str | None = None) -> dict:
    """Hamming(7,4): encode 4 data bits, or check/correct a received 7-bit word (positions 1..7, parity at 1, 2, 4)."""
    if received is not None:
        r = received.replace(" ", "")
        if len(r) != 7 or set(r) - {"0", "1"}:
            raise EngMathError("Give exactly 7 bits, e.g. 0110011.")
        b = [int(x) for x in r]
        s1, s2, s4 = b[0] ^ b[2] ^ b[4] ^ b[6], b[1] ^ b[2] ^ b[5] ^ b[6], b[3] ^ b[4] ^ b[5] ^ b[6]
        pos = s1 + 2 * s2 + 4 * s4
        if pos:
            b[pos - 1] ^= 1
        return {"received": r, "syndrome": f"{s4}{s2}{s1}", "error_position": pos or None, "corrected": "".join(map(str, b)), "data_bits": f"{b[2]}{b[4]}{b[5]}{b[6]}",
                "note": "The syndrome, read as a binary number, is the position of a single flipped bit (0 = no error). Two flipped bits are miscorrected; add an overall parity bit (SECDED) to detect them."}
    d = "".join(str(data)).replace(" ", "")
    if len(d) != 4 or set(d) - {"0", "1"}:
        raise EngMathError("Give exactly 4 data bits, e.g. 1011.")
    d3, d5, d6, d7 = (int(x) for x in d)
    p1, p2, p4 = d3 ^ d5 ^ d7, d3 ^ d6 ^ d7, d5 ^ d6 ^ d7
    word = f"{p1}{p2}{d3}{p4}{d5}{d6}{d7}"
    return {"data": d, "codeword": word, "layout": "p1 p2 d1 p4 d2 d3 d4", "note": "p1 covers positions 1,3,5,7; p2 covers 2,3,6,7; p4 covers 4,5,6,7. Each parity bit makes its group even."}


def endian(value, bytes_: int = 4) -> dict:
    n = _int(bytes_, "bytes", 1, 8)
    v = _int(value, "value", 0, (1 << (8 * n)) - 1)
    be = v.to_bytes(n, "big")
    return {"value_hex": f"{v:0{2 * n}X}", "big_endian_bytes": " ".join(f"{x:02X}" for x in be), "little_endian_bytes": " ".join(f"{x:02X}" for x in be[::-1]),
            "note": "Big-endian stores the most significant byte first (network order). x86 and most ARM systems are little-endian."}


def _convert(value, base=10, bits=8):
    t = str(value).strip().lower()
    neg = t.startswith("-")
    t = t.lstrip("-+")
    for pre, b in (("0x", 16), ("0b", 2), ("0o", 8)):              # a prefix sets the base, whatever `base` says
        if t.startswith(pre):
            t, base = t[2:], b
    return cpe_lab.convert(("-" if neg else "") + t, _int(base, "base", 2, 36), bits)


KINDS = {
    "convert": lambda a: _convert(a.get("value"), a.get("base", 10), a.get("bits", 8)),
    "gray": lambda a: gray(a.get("value"), a.get("direction", "to_gray"), a.get("bits", 8), a.get("sequence_bits")),
    "ascii": lambda a: ascii_tool(a.get("text"), a.get("code")),
    "bitop": lambda a: bitop(a.get("op"), a.get("a"), a.get("b"), a.get("bits", 8)),
    "parity": lambda a: parity(a.get("value"), a.get("bits", 8)),
    "bcd": lambda a: bcd(a.get("value"), a.get("bcd")),
    "checksum": lambda a: checksum(a.get("data"), a.get("checksum", "sum8")),
    "hamming": lambda a: hamming74(a.get("data"), a.get("received")),
    "endian": lambda a: endian(a.get("value"), a.get("bytes", 4)),
    "twos_add": lambda a: cpe_lab.signed_add(_int(a.get("a")), _int(a.get("b")), a.get("bits", 8), bool(a.get("subtract"))),
    "ieee754": lambda a: cpe_lab.ieee754(float(a.get("x", 0)), bool(a.get("double"))),
    "logic": lambda a: cpe_lab.logic(str(a.get("expr", ""))),
    "equivalent": lambda a: cpe_lab.equivalent(str(a.get("expr", "")), str(a.get("expr2", ""))),
}


def run(kind: str, args: dict) -> dict:
    fn = KINDS.get(kind)
    if not fn:
        raise EngMathError("kind must be one of: " + ", ".join(KINDS))
    try:
        return fn(args or {})
    except cpe_lab.CpeError as e:
        raise EngMathError(e.message) from None
    except (TypeError, ValueError, OverflowError) as e:
        raise EngMathError(f"Can't compute that: {e}") from None


TOOL_ENGMATH = {"name": "eng_math", "description": "Exact engineering-math calculator for number systems and digital logic. ALWAYS use it instead of converting by hand. kind: "
                "convert (value in `base`, to dec/bin/oct/hex and two's complement at `bits`), gray (value; direction to_gray|from_gray; bits; or sequence_bits to list a Gray sequence), "
                "ascii (text, or code 0-127), bitop (op and/or/xor/nand/nor/xnor/not/shl/shr/sar/rol/ror; a; b; bits), parity (value, bits), bcd (value, or bcd text), "
                "checksum (data as hex bytes; checksum sum8|xor8|twos8|crc8|crc16-ccitt|crc16-modbus), hamming (4 data bits, or received 7 bits), endian (value, bytes), "
                "twos_add (a, b, bits, subtract), ieee754 (x, double), logic (expr), equivalent (expr, expr2). Pass only what the kind needs; values may be 13, 0b1101 or 0xD.",
                "input_schema": {"type": "object", "properties": {"kind": {"type": "string", "enum": list(KINDS)}, "value": {}, "base": {"type": "integer"}, "bits": {"type": "integer"},
                                 "direction": {"type": "string", "enum": ["to_gray", "from_gray"]}, "sequence_bits": {"type": "integer"}, "text": {"type": "string"}, "code": {},
                                 "op": {"type": "string"}, "a": {}, "b": {}, "bcd": {"type": "string"}, "data": {}, "checksum": {"type": "string"}, "received": {"type": "string"},
                                 "bytes": {"type": "integer"}, "subtract": {"type": "boolean"}, "x": {"type": "number"}, "double": {"type": "boolean"}, "expr": {"type": "string"}, "expr2": {"type": "string"}},
                                 "required": ["kind"], "additionalProperties": False}}
