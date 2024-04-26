# dronesynth_code.py -- drone synth for qtpy_synth
# 25 Apr 2024 - @todbot / Tod Kurt
# part of https://github.com/todbot/qtpy_synth
#
# Needed libraries to install:
#  circup install asyncio neopixel adafruit_debouncer adafruit_displayio_ssd1306 adafruit_display_text
# Also install "qtpy_synth" directory in CIRCUITPY/lib
#

import asyncio
import time
import random
import synthio
import ulab.numpy as np
import usb_midi

import displayio, terminalio, vectorio
from adafruit_display_text import bitmap_label as label

from qtpy_synth.hardware import Hardware

from param_scaler import ParamScaler

import microcontroller
microcontroller.cpu.frequency = 250_000_000  # overclock

class SynthConfig():
    def __init__(self):
        self.filter_type = 'lpf'
        self.filter_f = 2000
        self.filter_q = 0.7
        self.filter_mod = 0
        self.wave_type = 'saw'  # 'sin' or 'saw' or 'squ'

qts = Hardware()
cfg = SynthConfig()

# set up some default synth parameters
wave_size = 256
wave_amp = 20000
wave_saw = np.linspace(wave_amp,-wave_amp, num=wave_size, dtype=np.int16)
wave_sin = np.array(np.sin(np.linspace(0, 2*np.pi, wave_size, endpoint=False)) * wave_amp, dtype=np.int16)
wave_squ = np.concatenate((np.ones(wave_size // 2, dtype=np.int16) * wave_amp,
                           np.ones(wave_size // 2, dtype=np.int16) * -wave_amp))
# default squ is too clippy, should be 3dB down or so?
def get_wave(wave_type):
    if wave_type=='sin': return wave_sin
    if wave_type=='squ': return wave_squ
    if wave_type=='saw': return wave_saw

filter_types = ['lpf', 'hpf', 'bpf']
def make_filter():
    freq = cfg.filter_f + cfg.filter_mod
    if cfg.filter_type == 'lpf':
        filter = qts.synth.low_pass_filter(freq, cfg.filter_q)
    elif cfg.filter_type == 'hpf':
        filter = qts.synth.high_pass_filter(freq, cfg.filter_q)
    elif cfg.filter_type == 'bpf':
        filter = qts.synth.band_pass_filter(freq, cfg.filter_q)
    else:
        print("unknown filter type", cfg.filter_type)
    return filter

# -----------------------------

# set up display with our 3 chunks of info
disp_group = displayio.Group()
qts.display.root_group = disp_group

labels_pos = ( (5,5), (50,5), (100,5), (15,50) )  #  filter_f, filter_type, filter_q,  hellotext
disp_info = displayio.Group()
for (x,y) in labels_pos:
    disp_info.append( label.Label(terminalio.FONT, text="-", x=x, y=y) )
disp_group.append(disp_info)
disp_info[3].text = "dronesynth"

def display_update():
    f_str = "%4d" % (cfg.filter_f + cfg.filter_mod)
    q_str = "%1.1f" % cfg.filter_q

    if f_str != disp_info[0].text:
        disp_info[0].text = f_str

    if cfg.filter_type != disp_info[1].text:
        disp_info[1].text = cfg.filter_type

    if q_str != disp_info[2].text:
        disp_info[2].text = q_str
        print("edit q", q_str)

def get_osc_freqs(kA,kB):
    d = 0.01 + (kB / 255) * 12
    f1 = synthio.midi_to_hz( 12 + kA/4 )
    f2 = synthio.midi_to_hz( 12 + kA/4 + d )
    return (f1, f2)
    
    
# --------------------------------------------------------

num_keys = 4
oscs_per_key = 2
voices = {}  # key = key_number, value = list of oscs

key_touched_num = None
last_knob_vals = {}
(knobA_val, knobB_val) = [v/256 for v in qts.read_pots()]

scalerA = ParamScaler(knobA_val, knobA_val)
scalerB = ParamScaler(knobB_val, knobB_val)

for i in range(num_keys):
    last_knob_vals[i] = (knobA_val, knobB_val)

    
for i in range(num_keys):
    oscs = []
    freqs = get_osc_freqs(knobA_val,knobB_val)
    wave = get_wave(cfg.wave_type)
    for j in range(oscs_per_key):
        f = freqs[j]
        osc = synthio.Note( frequency=f, waveform=wave, filter=make_filter() )
        qts.synth.press( osc )
        oscs.append(osc)
    voices[i] = oscs


kA, kB = 0,0
button_held = False
button_held_time = 0

while True:
    time.sleep(0.01)
    
    (knobA_val, knobB_val) = [v/256 for v in qts.read_pots()]
    
    # if we're pressing a pad
    if key_touched_num is not None: 

        kA = scalerA.update(knobA_val)
        kB = scalerB.update(knobB_val)
        print("knobA:%.1f knobB:%.1f  kA:%.1f  kB:%.1f" %(knobA_val,knobB_val,kA,kB))

        oscs = voices[key_touched_num]
        freqs = get_osc_freqs(kA,kB)
        for i,osc in enumerate(oscs):
            osc.frequency = freqs[i]

    if touches := qts.check_touch():
        for touch in touches:
            
            if touch.pressed:
                key_touched_num = touch.key_number
                lastA, lastB = last_knob_vals[key_touched_num]
                scalerA.reset( lastA, knobA_val)
                scalerB.reset( lastB, knobB_val)
                
            if touch.released:
                last_knob_vals[touch.key_number] = (kA, kB)
                key_touched_num = None

    if key := qts.check_key():
        if key.pressed:
            button_held = True
            button_held_time = time.monotonic()
            print("button!")
            if key_touched_num is not None: # pressing a pad toggles voice 
                for osc in voices[key_touched_num]:
                    osc.amplitude = 0 if osc.amplitude > 0 else 1
        if key.released:
            button_held = False


    button_time_delta = time.monotonic() - button_held_time
    if button_held and button_time_delta > 1:
        print("drone freqs")
        for k,oscs in voices.items():
            print("%d: " % k, end='')
            for osc in oscs:
                print("%.2f, " % osc.frequency, end='')
            print()

        oscf = voices[0][0].frequency
        ff = 0.99
        for i in range(1,num_keys):
            voices[i][0].frequency = ff * voices[i][0].frequency + (1-ff)*oscf
            voices[i][1].frequency = ff * voices[i][1].frequency + (1-ff)*oscf
        
        #button_held = False  # say we're done with button







                
