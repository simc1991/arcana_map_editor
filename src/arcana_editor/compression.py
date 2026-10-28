from __future__ import annotations

from collections import defaultdict


def _header(command: int, length: int) -> bytes:
    if not 1 <= length <= 1024:
        raise ValueError(length)
    value = length - 1
    if length <= 32:
        return bytes((command | value,))
    return bytes((0xE0 | (command >> 3) | ((value >> 8) & 0x03), value & 0xFF))


def compress_hal(data: bytes) -> bytes:
    output = bytearray()
    literals = bytearray()
    positions: dict[bytes, list[int]] = defaultdict(list)

    def flush() -> None:
        while literals:
            chunk = literals[:1024]
            del literals[:len(chunk)]
            output.extend(_header(0x00, len(chunk)))
            output.extend(chunk)

    index = 0
    while index < len(data):
        remaining = len(data) - index
        byte_run = 1
        while byte_run < min(1024, remaining) and data[index + byte_run] == data[index]:
            byte_run += 1
        increment_run = 1
        while increment_run < min(1024, remaining) and data[index + increment_run] == (data[index] + increment_run) & 0xFF:
            increment_run += 1
        word_run = 1
        if remaining >= 4:
            word = data[index:index + 2]
            while word_run < min(1024, remaining // 2) and data[index + word_run * 2:index + word_run * 2 + 2] == word:
                word_run += 1
        copy_length = 0
        copy_position = 0
        if remaining >= 3:
            key = data[index:index + 3]
            for candidate in reversed(positions.get(key, [])[-96:]):
                length = 3
                while length < min(1024, remaining) and data[candidate + length] == data[index + length]:
                    length += 1
                if length > copy_length:
                    copy_length = length
                    copy_position = candidate
        choices = []
        if byte_run >= 3:
            choices.append((byte_run - len(_header(0x20, byte_run)) - 1, "byte", byte_run))
        if increment_run >= 4:
            choices.append((increment_run - len(_header(0x60, increment_run)) - 1, "increment", increment_run))
        if word_run >= 2:
            produced = word_run * 2
            choices.append((produced - len(_header(0x40, word_run)) - 2, "word", word_run))
        if copy_length >= 4:
            choices.append((copy_length - len(_header(0x80, copy_length)) - 2, "copy", copy_length))
        best = max(choices, default=(0, "literal", 1), key=lambda choice: choice[0])
        if best[0] <= 0:
            literals.append(data[index])
            if index + 3 <= len(data):
                positions[data[index:index + 3]].append(index)
            index += 1
            if len(literals) == 1024:
                flush()
            continue
        flush()
        mode, length = best[1], best[2]
        if mode == "byte":
            output.extend(_header(0x20, length))
            output.append(data[index])
            consumed = length
        elif mode == "increment":
            output.extend(_header(0x60, length))
            output.append(data[index])
            consumed = length
        elif mode == "word":
            output.extend(_header(0x40, length))
            output.extend(data[index:index + 2])
            consumed = length * 2
        else:
            output.extend(_header(0x80, length))
            output.extend((copy_position >> 8, copy_position & 0xFF))
            consumed = length
        for position in range(index, min(index + consumed, len(data) - 2)):
            positions[data[position:position + 3]].append(position)
        index += consumed
    flush()
    output.append(0xFF)
    return bytes(output)
