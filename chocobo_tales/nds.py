"""Reading Nintendo DS ROMs: header, file system, overlays and Nintendo LZ10/LZ11 compression."""
import struct
from dataclasses import dataclass
from functools import cached_property


@dataclass(frozen=True)
class Overlay:
    cpu: str  # "arm9" or "arm7"
    overlay_id: int
    ram_address: int
    ram_size: int
    bss_size: int
    file_id: int
    compressed: bool


class NDSRom:
    def __init__(self, source: "str | bytes"):
        if isinstance(source, (bytes, bytearray)):
            self.data = bytes(source)
        else:
            with open(source, "rb") as file:
                self.data = file.read()
        self.title = self.data[0x00:0x0C].decode("ascii", "replace").rstrip("\0")
        self.game_code = self.data[0x0C:0x10].decode("ascii", "replace")
        self.maker_code = self.data[0x10:0x12].decode("ascii", "replace")
        self.version = self.data[0x1E]
        (self.arm9_offset, self.arm9_entry, self.arm9_ram_address, self.arm9_size,
         self.arm7_offset, self.arm7_entry, self.arm7_ram_address, self.arm7_size,
         self.fnt_offset, self.fnt_size, self.fat_offset, self.fat_size,
         self.arm9_overlay_offset, self.arm9_overlay_size,
         self.arm7_overlay_offset, self.arm7_overlay_size) = struct.unpack_from("<16I", self.data, 0x20)

    def file_range(self, file_id: int) -> tuple[int, int]:
        return struct.unpack_from("<II", self.data, self.fat_offset + 8 * file_id)

    @cached_property
    def files(self) -> dict[str, int]:
        """Path -> file id, for every file in the ROM's file system."""
        result: dict[str, int] = {}

        def walk(dir_id: int, path: str) -> None:
            sub_offset, first_id, _ = struct.unpack_from("<IHH", self.data, self.fnt_offset + 8 * (dir_id & 0xFFF))
            p = self.fnt_offset + sub_offset
            file_id = first_id
            while self.data[p]:
                entry = self.data[p]
                p += 1
                name = self.data[p:p + (entry & 0x7F)].decode("latin1")
                p += entry & 0x7F
                if entry & 0x80:
                    sub_dir = struct.unpack_from("<H", self.data, p)[0]
                    p += 2
                    walk(sub_dir, f"{path}{name}/")
                else:
                    result[path + name] = file_id
                    file_id += 1

        walk(0xF000, "/")
        return result

    @cached_property
    def overlays(self) -> list[Overlay]:
        result = []
        for cpu, offset, size in (("arm9", self.arm9_overlay_offset, self.arm9_overlay_size),
                                  ("arm7", self.arm7_overlay_offset, self.arm7_overlay_size)):
            for entry in range(0, size, 32):
                overlay_id, ram_address, ram_size, bss_size, _, _, file_id, flags = \
                    struct.unpack_from("<8I", self.data, offset + entry)
                result.append(Overlay(cpu, overlay_id, ram_address, ram_size, bss_size, file_id,
                                      bool(flags >> 24 & 1)))
        return result

    def read_id(self, file_id: int) -> bytes:
        start, end = self.file_range(file_id)
        return self.data[start:end]

    def read(self, path: str, decompress: bool | None = None) -> bytes:
        """Reads a file by path. decompress=None decompresses files ending in .z that start with an LZ header."""
        data = self.read_id(self.files[path])
        if decompress is None:
            decompress = path.endswith(".z") and is_lz(data)
        return lz_decompress(data) if decompress else data

    @property
    def arm9_raw(self) -> bytes:
        return self.data[self.arm9_offset:self.arm9_offset + self.arm9_size]

    @cached_property
    def module_params(self) -> dict[str, int] | None:
        """The ARM9 SDK module params (autoload list, BSS range, compressed static end), if present."""
        raw = self.arm9_raw
        marker = raw.find(struct.pack("<II", 0xDEC00621, 0x2106C0DE))
        if marker < 28:
            return None
        names = ("autoload_list_start", "autoload_list_end", "autoload_start", "bss_start", "bss_end",
                 "compressed_static_end", "sdk_version")
        params = dict(zip(names, struct.unpack_from("<7I", raw, marker - 28)))
        params["offset"] = marker - 28
        return params

    @cached_property
    def arm9(self) -> bytes:
        """The ARM9 binary as loaded in RAM at arm9_ram_address (BLZ-decompressed when needed)."""
        raw = self.arm9_raw
        params = self.module_params
        if not params or not params["compressed_static_end"]:
            return raw
        end = params["compressed_static_end"] - self.arm9_ram_address
        data = bytearray(blz_decompress(raw[:end]) + raw[end:])
        struct.pack_into("<I", data, params["offset"] + 20, 0)  # the loader clears compressed_static_end
        return bytes(data)

    def build(self, **changes) -> bytes:
        """Rebuilds this ROM with replaced parts; see build_rom."""
        return build_rom(self, **changes)

    def overlay_data(self, overlay: Overlay) -> bytes:
        """An overlay's code as loaded in RAM at overlay.ram_address."""
        data = self.read_id(overlay.file_id)
        return blz_decompress(data) if overlay.compressed else data


NITROCODE = 0xDEC00621
ALIGNMENT = 0x200


def _banner_size(data: bytes, offset: int) -> int:
    if offset == 0:
        return 0
    version = struct.unpack_from("<H", data, offset)[0]
    return {0x0001: 0x840, 0x0002: 0x940, 0x0003: 0xA40, 0x0103: 0x23C0}.get(version, 0x840)


def crc16(data: bytes) -> int:
    """CRC-16/MODBUS, used for the NDS header checksum."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def _add_files(rom: "NDSRom", new_files: dict[str, bytes]) -> tuple[bytes, dict[int, int], dict[int, bytes]]:
    """
    Adds files to existing directories of the file name table without renumbering any file: each directory that
    gets new files is given a new id range at the end of the FAT. Its old files keep their old ids too (both ids
    share the same data), so code that opens files by id still works.
    Returns (new FNT, {new id: existing id with the same data}, {new id: new file contents}).
    """
    data = rom.data
    fnt = data[rom.fnt_offset:rom.fnt_offset + rom.fnt_size]
    dir_count = struct.unpack_from("<H", fnt, 6)[0]
    entries = [list(struct.unpack_from("<IHH", fnt, 8 * i)) for i in range(dir_count)]

    def scan(dir_index: int) -> tuple[bytes, dict[str, int], int]:
        """(subtable without its end marker, {name: sub dir index or -1 for files}, file count)"""
        start = p = entries[dir_index][0]
        names: dict[str, int] = {}
        file_count = 0
        while fnt[p]:
            length = fnt[p] & 0x7F
            name = fnt[p + 1:p + 1 + length].decode("latin1")
            if fnt[p] & 0x80:
                names[name] = struct.unpack_from("<H", fnt, p + 1 + length)[0] & 0xFFF
                p += 3 + length
            else:
                names[name] = -1
                file_count += 1
                p += 1 + length
        return fnt[start:p], names, file_count

    by_dir: dict[int, dict[str, bytes]] = {}
    for path, contents in new_files.items():
        *parts, name = path.strip("/").split("/")
        dir_index = 0
        for part in parts:
            sub = scan(dir_index)[1].get(part, -1)
            if sub < 0:
                raise ValueError(f"no directory /{'/'.join(parts)} for {path}")
            dir_index = sub
        if name in scan(dir_index)[1] or not 0 < len(name.encode("latin1")) < 0x80:
            raise ValueError(f"can't add {path}: it exists or its name is invalid")
        by_dir.setdefault(dir_index, {})[name] = contents

    subtables = [scan(i)[0] for i in range(dir_count)]
    next_id = rom.fat_size // 8
    aliases: dict[int, int] = {}
    added: dict[int, bytes] = {}
    for dir_index, dir_files in by_dir.items():
        old_first, old_count = entries[dir_index][1], scan(dir_index)[2]
        entries[dir_index][1] = next_id
        for i in range(old_count):
            aliases[next_id + i] = old_first + i
        next_id += old_count
        extra = bytearray()
        for name, contents in dir_files.items():
            encoded = name.encode("latin1")
            extra += bytes([len(encoded)]) + encoded
            added[next_id] = contents
            next_id += 1
        subtables[dir_index] += bytes(extra)

    table = bytearray()
    body = bytearray()
    for i in range(dir_count):
        entries[i][0] = 8 * dir_count + len(body)
        table += struct.pack("<IHH", *entries[i])
        body += subtables[i] + b"\0"
    return bytes(table + body), aliases, added


def build_rom(rom: "NDSRom", arm9: bytes | None = None, overlays: dict[int, bytes] | None = None,
              files: dict[int, bytes] | None = None, header_patches: dict[int, bytes] | None = None,
              new_files: dict[str, bytes] | None = None) -> bytes:
    """
    Rebuilds a ROM with replaced parts, re-laying out everything after the header in the original order.

    arm9: the ARM9 binary as it should be loaded (uncompressed: set module params' compressed_static_end to 0).
    overlays: ARM9 overlay id -> uncompressed code (the overlay table entry is marked uncompressed).
    files: file id -> new contents. header_patches: offset -> bytes written into the 0x0-0x4000 area
    (e.g. custom data in the reserved space after the 0x200-byte header).
    new_files: path -> contents of files to add to existing directories (see _add_files), stored after
    everything else.
    """
    data = rom.data
    overlays = overlays or {}
    files = dict(files or {})
    fnt = data[rom.fnt_offset:rom.fnt_offset + rom.fnt_size]
    aliases: dict[int, int] = {}
    added: dict[int, bytes] = {}
    if new_files:
        fnt, aliases, added = _add_files(rom, new_files)
    header = bytearray(data[:0x4000])
    for offset, patch in (header_patches or {}).items():
        header[offset:offset + len(patch)] = patch

    ovt9 = bytearray(data[rom.arm9_overlay_offset:rom.arm9_overlay_offset + rom.arm9_overlay_size])
    for entry in range(0, len(ovt9), 32):
        overlay_id, file_id = struct.unpack_from("<I", ovt9, entry)[0], struct.unpack_from("<I", ovt9, entry + 24)[0]
        if overlay_id in overlays:
            files[file_id] = overlays[overlay_id]
            struct.pack_into("<I", ovt9, entry + 28, 0)  # not compressed
            struct.pack_into("<I", ovt9, entry + 8, len(overlays[overlay_id]))  # RAM size

    arm9_footer = b""
    end = rom.arm9_offset + rom.arm9_size
    if struct.unpack_from("<I", data, end)[0] == NITROCODE:
        arm9_footer = data[end:end + 12]
    arm9_data = (arm9 if arm9 is not None else rom.arm9_raw)

    file_count = rom.fat_size // 8
    regions = [
        (rom.arm9_offset, "arm9", arm9_data + arm9_footer),
        (rom.arm9_overlay_offset, "ovt9", bytes(ovt9)),
        (rom.arm7_offset, "arm7", data[rom.arm7_offset:rom.arm7_offset + rom.arm7_size]),
        (rom.fnt_offset, "fnt", fnt),
        (rom.fat_offset, "fat", None),
    ]
    if rom.arm7_overlay_size:
        regions.append((rom.arm7_overlay_offset, "ovt7",
                        data[rom.arm7_overlay_offset:rom.arm7_overlay_offset + rom.arm7_overlay_size]))
    banner_offset = struct.unpack_from("<I", data, 0x68)[0]
    if banner_offset:
        regions.append((banner_offset, "banner", data[banner_offset:banner_offset + _banner_size(data, banner_offset)]))
    for file_id in range(file_count):
        start, stop = rom.file_range(file_id)
        regions.append((start, f"file {file_id}", files.get(file_id, data[start:stop])))
    regions.sort(key=lambda region: (region[0], region[1] != "arm9"))
    regions += [(len(data), f"file {file_id}", contents) for file_id, contents in added.items()]
    total_files = file_count + len(aliases) + len(added)

    out = bytearray(header)
    positions: dict[str, tuple[int, int]] = {}
    for _, name, content in regions:
        if name == "fat":
            content = bytes(8 * total_files)  # filled in below
        pad = -len(out) % ALIGNMENT
        out += b"\xFF" * pad
        positions[name] = (len(out), len(content))
        out += content

    fat = bytearray()
    for file_id in range(total_files):
        start, size = positions[f"file {aliases.get(file_id, file_id)}"]
        fat += struct.pack("<II", start, start + size)
    fat_start = positions["fat"][0]
    out[fat_start:fat_start + len(fat)] = fat

    def put(offset: int, value: int) -> None:
        struct.pack_into("<I", out, offset, value)

    put(0x20, positions["arm9"][0])
    put(0x2C, len(arm9_data))
    put(0x30, positions["arm7"][0])
    put(0x40, positions["fnt"][0])
    put(0x44, len(fnt))
    put(0x48, fat_start)
    put(0x4C, len(fat))
    put(0x50, positions["ovt9"][0])
    if "ovt7" in positions:
        put(0x58, positions["ovt7"][0])
    if "banner" in positions:
        put(0x68, positions["banner"][0])
    used = len(out)
    put(0x80, used)
    capacity = 0
    while (0x20000 << capacity) < used:
        capacity += 1
    out[0x14] = capacity
    out += b"\xFF" * (-len(out) % ALIGNMENT)
    struct.pack_into("<H", out, 0x15E, crc16(bytes(out[:0x15E])))
    return bytes(out)


def blz_decompress(data: bytes) -> bytes:
    """Nintendo's backward LZ ("BLZ"), used for ARM9 binaries and overlays. Decodes from the end towards the start."""
    footer, extra = struct.unpack_from("<II", data, len(data) - 8)
    if extra == 0:
        return data
    header_length, compressed_length = footer >> 24, footer & 0xFFFFFF
    out = bytearray(data) + bytearray(extra)
    src = len(data) - header_length
    dst = len(out)
    stop = len(data) - compressed_length
    while src > stop:
        flags = data[src - 1]
        src -= 1
        for _ in range(8):
            if src <= stop:
                break
            if flags & 0x80:
                high, low = data[src - 1], data[src - 2]
                src -= 2
                length = (high >> 4) + 3
                disp = ((high & 0xF) << 8 | low) + 3
                for _ in range(length):
                    out[dst - 1] = out[dst - 1 + disp]
                    dst -= 1
            else:
                out[dst - 1] = data[src - 1]
                src -= 1
                dst -= 1
            flags = flags << 1 & 0xFF
    return bytes(out)


def is_lz(data: bytes) -> bool:
    return len(data) >= 4 and data[0] in (0x10, 0x11)


def lz_decompress(src: bytes) -> bytes:
    """Nintendo LZ10 / LZ11 (the BIOS "LZ77" formats)."""
    kind = src[0]
    size = src[1] | src[2] << 8 | src[3] << 16
    p = 4
    if size == 0:
        size = struct.unpack_from("<I", src, 4)[0]
        p = 8
    out = bytearray()
    while len(out) < size:
        flags = src[p]
        p += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if not flags & (0x80 >> bit):
                out.append(src[p])
                p += 1
                continue
            if kind == 0x10:
                length = (src[p] >> 4) + 3
                disp = ((src[p] & 0xF) << 8 | src[p + 1]) + 1
                p += 2
            else:
                indicator = src[p] >> 4
                if indicator == 0:
                    length = ((src[p] & 0xF) << 4 | src[p + 1] >> 4) + 0x11
                    disp = ((src[p + 1] & 0xF) << 8 | src[p + 2]) + 1
                    p += 3
                elif indicator == 1:
                    length = ((src[p] & 0xF) << 12 | src[p + 1] << 4 | src[p + 2] >> 4) + 0x111
                    disp = ((src[p + 2] & 0xF) << 8 | src[p + 3]) + 1
                    p += 4
                else:
                    length = indicator + 1
                    disp = ((src[p] & 0xF) << 8 | src[p + 1]) + 1
                    p += 2
            for _ in range(length):
                out.append(out[-disp])
    return bytes(out)



def lz10_compress(data: bytes) -> bytes:
    """Nintendo LZ10 (what lz_decompress reads back; the usual .z files). Greedy matches of 3-18 bytes, 4 KB back."""
    if 0 < len(data) <= 0xFFFFFF:
        out = bytearray(struct.pack("<I", 0x10 | len(data) << 8))
    else:  # a 24-bit size of 0 means the real size follows as a u32
        out = bytearray(struct.pack("<II", 0x10, len(data)))
    positions: dict[bytes, list[int]] = {}
    i = 0
    while i < len(data):
        flag_at = len(out)
        out.append(0)
        for bit in range(8):
            if i >= len(data):
                break
            best_length, best_distance = 0, 0
            for start in reversed(positions.get(data[i:i + 3], ())):
                distance = i - start
                if distance > 0x1000:
                    break
                length = 3
                while length < 18 and i + length < len(data) and data[start + length] == data[i + length]:
                    length += 1
                if length > best_length:
                    best_length, best_distance = length, distance
                    if length == 18:
                        break
            step = best_length if best_length >= 3 else 1
            if best_length >= 3:
                out[flag_at] |= 0x80 >> bit
                value = (best_length - 3) << 12 | (best_distance - 1)
                out += bytes((value >> 8, value & 0xFF))
            else:
                out.append(data[i])
            for k in range(i, i + step):
                positions.setdefault(data[k:k + 3], []).append(k)
            i += step
    while len(out) % 4:
        out.append(0)
    return bytes(out)

def search_text(rom: NDSRom, text: str) -> list[tuple[str, int, str]]:
    """Finds text in every file (decompressing LZ files) as ASCII/UTF-8 and UTF-16LE. Returns (path, offset, encoding)."""
    needles = {"utf-8": text.encode("utf-8"), "utf-16le": text.encode("utf-16le")}
    hits = []
    for path in rom.files:
        data = rom.read(path, decompress=False)
        if is_lz(data):
            try:
                data = lz_decompress(data)
            except (IndexError, struct.error):
                pass
        for encoding, needle in needles.items():
            position = data.find(needle)
            while position >= 0:
                hits.append((path, position, encoding))
                position = data.find(needle, position + 1)
    return hits
