# dronesynth_code.py -- drone synth for qtpy_synth
# 25 Apr 2024 - @todbot / Tod Kurt
# part of https://github.com/todbot/qtpy_synth
#
# Needed libraries to install:
#  circup install asyncio neopixel adafruit_debouncer adafruit_displayio_ssd1306 adafruit_display_text
# Also install "qtpy_synth" directory in CIRCUITPY/lib
#
# How to use:
#
# - This synth has four pair of oscillators (8 total)
# - Each pad controls an oscillator pad
# - While holding a pad:
#   - left pot A adjusts oscillator pair center frequency
#   - right pot B adjusts oscillator frequency "spread" / "detune"
#   - middle tact button mutes/unmutes the oscillator pair
#
#

import asyncio
import time
import random
import synthio
import usb_midi

import displayio, terminalio, vectorio
from adafruit_display_text import bitmap_label as label

from qtpy_synth.hardware import Hardware

from param_scaler import ParamScaler
from my_little_droney import MyLittleDroney, get_freqs_by_knobs

#import microcontroller
#microcontroller.cpu.frequency = 250_000_000  # overclock! vrrroomm

num_pads = 2
oscs_per_pad = 2

class SynthConfig():
    def __init__(self):
        self.filter_type = 'lpf'
        self.filter_f = 2000
        self.filter_q = 0.7
        self.filter_mod = 0
        self.wave_type = 'saw'  # 'sin' or 'saw' or 'squ'

qts = Hardware()
cfg = SynthConfig()

droney = MyLittleDroney(qts.synth, cfg, num_pads, oscs_per_pad)

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

def converge_freqs(speed=0.1):
    pass

# --------------------------------------------------------

pad_num = None  # which pad is currently being touched
vals = {}  # scaled knob vals per pad, key = pad number, val = [valA,valB]
# get initial knob vals for the scalers
(knobA_val, knobB_val) = [v/256 for v in qts.read_pots()]

scalerA = ParamScaler(knobA_val, knobA_val)
scalerB = ParamScaler(knobB_val, knobB_val)

for i in range(num_pads):
    vals[i] = (knobA_val, knobB_val)

button_held = False
button_held_time = 0

while True:
    time.sleep(0.01)
    
    (knobA_val, knobB_val) = [v/256 for v in qts.read_pots()]
    
    # if we're pressing a pad
    if pad_num is not None: 
        
        valA = scalerA.update(knobA_val)
        valB = scalerB.update(knobB_val)
        
        print("knobA:%.1f knobB:%.1f  valA:%.1f  valB:%.1f" %(knobA_val,knobB_val,valA,valB))

        freqs = get_freqs_by_knobs(valA,valB)
        droney.set_voice_freqs(pad_num, freqs)

        vals[pad_num] = [valA,valB]

    if touches := qts.check_touch():
        for touch in touches:
            
            if touch.pressed:
                pad_num = touch.key_number
                # restore vals for this pad 
                lastA, lastB = vals[pad_num]  
                scalerA.reset( lastA, knobA_val)
                scalerB.reset( lastB, knobB_val)

            if touch.released:
                pad_num = None

    if key := qts.check_key():
        if key.pressed:
            print("button!")
            button_held = True
            button_held_time = time.monotonic()
            if pad_num is not None: # pressing a pad toggles voice
                droney.toggle_voice_mute(pad_num)
                pass
            
        if key.released:
            button_held = False


    button_time_delta = time.monotonic() - button_held_time
    if button_held and button_time_delta > 1:
        print("drone freqs")
        # for k,oscs in voices.items():
        #     print("%d: " % k, end='')
        #     for osc in oscs:
        #         print("%.2f, " % osc.frequency, end='')
        #     print()

        # oscf = voices[0][0].frequency
        # ff = 0.99
        # for i in range(1,num_keys):
        #     voices[i][0].frequency = ff * voices[i][0].frequency + (1-ff)*oscf
        #     voices[i][1].frequency = ff * voices[i][1].frequency + (1-ff)*oscf
        







                
