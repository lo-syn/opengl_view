import struct

def osc_string(value):
    encoded = value.encode("utf-8") + b"\0"
    return encoded + b"\0" * (-len(encoded) % 4)


def osc_float(address, value):
    return osc_string(address) + osc_string(",f") + struct.pack(">f", value)