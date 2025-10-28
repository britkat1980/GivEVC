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

def decode_unsigned_32(registers, byte_order="ABCD"):
    """Decode two 16-bit Modbus registers into an unsigned 32-bit integer.
    Supports the same byte orders as the float/signed helpers: ABCD (default),
    DCBA, BADC, CDAB.
    """
    raw = struct.pack(">HH", registers[0], registers[1])
    if byte_order == "DCBA":
        raw = raw[::-1]
    elif byte_order == "BADC":
        raw = raw[1:2] + raw[0:1] + raw[3:4] + raw[2:3]
    elif byte_order == "CDAB":
        raw = raw[2:4] + raw[0:2]
    return struct.unpack(">I", raw)[0]