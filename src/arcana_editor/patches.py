from __future__ import annotations

IPS_HEADER = b"PATCH"
IPS_FOOTER = b"EOF"
RLE_THRESHOLD = 3


def _run_length(data: bytes, start: int, end: int) -> int:
    value = data[start]
    count = 1
    while start + count < end and data[start + count] == value:
        count += 1
    return count


def build_ips_patch(original: bytes, modified: bytes) -> bytes:
    if len(modified) != len(original):
        raise ValueError("Les deux ROM doivent avoir la même taille")
    if len(modified) > 0xFFFFFF:
        raise ValueError("ROM trop grande pour le format IPS")
    records = bytearray()
    index = 0
    while index < len(modified):
        if modified[index] == original[index]:
            index += 1
            continue
        start = index
        while index < len(modified) and modified[index] != original[index]:
            index += 1
        cursor = start
        while cursor < index:
            offset = cursor
            run = _run_length(modified, cursor, index)
            if run >= RLE_THRESHOLD:
                while run:
                    piece = min(run, 0xFFFF)
                    records += offset.to_bytes(3, "big")
                    records += (0).to_bytes(2, "big")
                    records += piece.to_bytes(2, "big")
                    records.append(modified[cursor])
                    offset += piece
                    cursor += piece
                    run -= piece
                continue
            literal_end = cursor
            while literal_end < index and literal_end - cursor < 0xFFFF:
                run = _run_length(modified, literal_end, index)
                if run >= RLE_THRESHOLD:
                    break
                literal_end += run if run else 1
            records += offset.to_bytes(3, "big")
            records += (literal_end - cursor).to_bytes(2, "big")
            records += modified[cursor:literal_end]
            cursor = literal_end
    return IPS_HEADER + bytes(records) + IPS_FOOTER
