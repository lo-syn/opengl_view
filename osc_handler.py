import struct
import socket

OSC_HOST = "127.0.0.1"
OSC_PORT = 8001

def osc_string(value):
    encoded = value.encode("utf-8") + b"\0"
    return encoded + b"\0" * (-len(encoded) % 4)


def osc_float(address, value):
    return osc_string(address) + osc_string(",f") + struct.pack(">f", value)

class OscHandler:
    def __init__(self):
        self.osc_host = OSC_HOST
        self.osc_port = OSC_PORT
        
        # Setup UDP socket to send OSC messages to openFrameworks application
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
