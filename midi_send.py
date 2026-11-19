import mido

MIDI_INPUT_INDEX = 1  # Default MIDI input index

class MidiHandler:
    def __init__(self, midi_input_index=MIDI_INPUT_INDEX):
        self.midi_input_index = midi_input_index
        self.midi_input = None

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

    def read_midi_messages(self):
        if self.midi_input is not None:
            return list(self.midi_input.iter_pending())
        return []