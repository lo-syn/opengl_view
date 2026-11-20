import mido

from osc_handler import OscHandler


MIDI_INPUT_INDEX = 1  # Default MIDI input index
MIDI_CC_TO_OSC = {
    120: "/u_x0",
    121: "/u_x1",
    122: "/u_x2",
    123: "/u_x3"
}
MIDI_AUDIO_GAIN_CC_TO_OSC = {
    16: MIDI_CC_TO_OSC[120],
    17: MIDI_CC_TO_OSC[121],
    18: MIDI_CC_TO_OSC[122],
    19: MIDI_CC_TO_OSC[123],
}

class MidiHandler:
    def __init__(self, osc_handler: OscHandler):
        self.midi_input_index = MIDI_INPUT_INDEX
        self.midi_input = None
        self.osc_handler = osc_handler

    def open_midi_input(self):
        if self.midi_input is not None:
            self.midi_input.close()
        midi_ports = mido.get_input_names()
        if 0 <= self.midi_input_index < len(midi_ports):
            self.midi_input = mido.open_input(midi_ports[self.midi_input_index])
        else:
            raise ValueError(f"Invalid MIDI input index: {self.midi_input_index}")

    def close_midi_input(self):
        if self.midi_input is not None:
            self.midi_input.close()
            self.midi_input = None

    def read_midi(self):
        for message in self.midi_input.iter_pending():
            if message.type != "control_change":
                continue
            value = message.value / 127.0
            address = MIDI_CC_TO_OSC.get(message.control)
            if address is not None:
                self.osc_handler.set_level(address, "midi", value)
                continue
            address = MIDI_AUDIO_GAIN_CC_TO_OSC.get(message.control)
            if address is not None:
                self.osc_handler.set_audio_gain(address, value)

    def read_midi_messages(self):
        if self.midi_input is not None:
            return list(self.midi_input.iter_pending())
        return []