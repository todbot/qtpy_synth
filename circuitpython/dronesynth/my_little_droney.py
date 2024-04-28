# SPDX-FileCopyrightText: Copyright (c) 2024 Tod Kurt
# SPDX-License-Identifier: MIT
"""
`my_little_droney`
================================================================================

`MyLittleDroney` is a multi-voice drone synth with multiple oscillators per voice.

Part of qtpy_synth.

"""

import math
import random
import synthio
import ulab.numpy as np


# set up some default synth parameters
wave_size = 256
wave_amp = 20000
wave_saw = np.linspace(wave_amp,-wave_amp, num=wave_size, dtype=np.int16)
wave_sin = np.array(np.sin(np.linspace(0, 2*np.pi, wave_size, endpoint=False)) * wave_amp, dtype=np.int16)
wave_squ = np.concatenate((np.ones(wave_size // 2, dtype=np.int16) * wave_amp,
                           np.ones(wave_size // 2, dtype=np.int16) * -wave_amp))
# default squ is too clippy, should be 3dB down or so?

def hz_to_midi(f):
    """ Convert Hz to MIDI note number float, synthio doesn't provide this """
    return 12 * (math.log(f,2) - math.log(440,2)) + 69

def note_to_knobval(n, note_offset=12, note_range=60):
    """ Turn a midi note number into a 'knobval' (0-255 float) """
    return (n-note_offset) * 255 / note_range

def knobval_to_note(v, note_offset=12, note_range=60):
    """ Turn a 'knobval' (0-255 float) into a float MIDI note number """
    return ((v/255) * note_range) + note_offset
   
def get_freqs_by_knobs(valA,valB, note_offset=12, note_range=60):
    """ Create a list of frequencies based on two 0-255 inputs """
    n = knobval_to_note(valA, note_offset, note_range)
    d = 0.0001 + (valB / 255) * 2
    f1 = synthio.midi_to_hz( n )
    f2 = synthio.midi_to_hz( n + d )
    return (f1, f2)

def get_wave(wave_type):
    if wave_type=='sin': return wave_sin
    if wave_type=='squ': return wave_squ
    if wave_type=='saw': return wave_saw

filter_types = ['lpf', 'hpf', 'bpf']

def make_filter(synth,cfg):
    freq = cfg.filter_f + cfg.filter_fmod
    if cfg.filter_type == 'lpf':
        filter = synth.low_pass_filter(freq, cfg.filter_q)
    elif cfg.filter_type == 'hpf':
        filter = synth.high_pass_filter(freq, cfg.filter_q)
    elif cfg.filter_type == 'bpf':
        filter = synth.band_pass_filter(freq, cfg.filter_q)
    else:
        print("unknown filter type", cfg.filter_type)
    return filter

class SynthConfig():
    def __init__(self):
        self.filter_type = 'lpf'
        self.filter_f = 2000
        self.filter_q = 1.1
        self.filter_fmod = 500
        self.wave_type = 'saw'  # 'sin' or 'saw' or 'squ'
        self.pitch_mod_rate = 0.1
        self.pitch_mod_scale = 0.01

class MyLittleDroney():
    """
    Drone Synth
    """
    def __init__(self, synth, synth_config, num_voices, oscs_per_voice):
        self.voices = []
        self.synth = synth
        self.cfg = synth_config
        for i in range(num_voices):
            oscs = []
            freqs = get_freqs_by_knobs(127,0)  # fake values
            wave = get_wave(self.cfg.wave_type)
            
            for j in range(oscs_per_voice):
                f = freqs[j]
                pitch_lfo = synthio.LFO(rate=0.1, scale=0.01, phase_offset=random.uniform(0,1))
                osc = synthio.Note(frequency=f, waveform=wave,
                                   bend=pitch_lfo,
                                   filter = make_filter(self.synth,self.cfg))
                synth.press(osc)
                oscs.append(osc)
            self.voices.append(oscs)

    # def update(self):
    #     for voice in self.voices:
    #         for osc in voice:
    #             osc.filter = make_filter(self.synth,self.cfg)
                
    def set_voice_freqs(self,n,freqs):
        for i,osc in enumerate(self.voices[n]):
            osc.frequency = freqs[i]

    def set_voice_notes(self,n,notes):
        freqs = [synthio.midi_to_hz(n) for n in notes]
        for i,osc in enumerate(self.voices[n]):
            osc.frequency = freqs[i]
        
    def set_voice_level(self,n,level):
        for osc in self.voices[n]:
            osc.amplitude = level

    def toggle_voice_mute(self,n):
        # fixme: what about other levels than 0,1
        for osc in self.voices[n]:
            osc.amplitude = 0 if osc.amplitude > 0 else 1

    def print_freqs(self):
        for i in range(len(self.voices)):
            print("%d: " % i, end='')
            oscs = self.voices[i]
            for osc in oscs:
                print("%.2f, " % osc.frequency, end='')
            print()
            
    def set_pitch_lfo_amount(self,n):
        for voice in self.voices:
            for osc in voice:
                osc.bend.scale = n
        
    def set_filter(self,f,q):
        self.cfg.filter_f = f
        self.cfg.filter_q = q if q else self.cfg.filter_q
        for voice in self.voices:
            for osc in voice:
                osc.filter = make_filter(self.synth, self.cfg)

        
