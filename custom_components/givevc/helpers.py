import struct

def decode_float(registers, byte_order="ABCD"):
    raw = struct.pack(">HH", registers[0], registers[1])
    if byte_order == "DCBA":
        raw = raw[::-1]
    elif byte_order == "BADC":
        raw = raw[1:2] + raw[0:1] + raw[3:4] + raw[2:3]
    elif byte_order == "CDAB":
        raw = raw[2:4] + raw[0:2]
    return struct.unpack(">f", raw)[0]

def decode_signed_16(value):
    return value if value < 0x8000 else value - 0x10000

def decode_signed_32(registers, byte_order="ABCD"):
    raw = struct.pack(">HH", registers[0], registers[1])
    if byte_order == "DCBA":
        raw = raw[::-1]
    elif byte_order == "BADC":
        raw = raw[1:2] + raw[0:1] + raw[3:4] + raw[2:3]
    elif byte_order == "CDAB":
        raw = raw[2:4] + raw[0:2]
    return struct.unpack(">i", raw)[0]