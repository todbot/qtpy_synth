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

import microcontroller
microcontroller.cpu.frequency = 250_000_000  # overclock! vrrroomm

num_pads = 4
oscs_per_pad = 2
initial_vals = (100, 100+7, 100+5, 100+12)

class SynthConfig():
    def __init__(self):
        self.filter_type = 'lpf'
        self.filter_f = 2000
        self.filter_q = 0.7
        self.filter_mod = 0
        self.wave_type = 'saw'  # 'sin' or 'saw' or 'squ'

qts = Hardware()
cfg = SynthConfig()

droney = MyLittleDroney(qts.synth, cfg, num_pads, oscs_per_pad) #, initial_notes)

pad_num = None  # which pad is currently being touched
voice_vals = []  # scaled knob vals per pad, index = pad number, val = [valA,valB]
button_held = False
button_held_time = 0

# -----------------------------

# set up display with our chunks of info
disp_group = displayio.Group()
qts.display.root_group = disp_group
labels_pos = ( (5,5), (45,5), #(95,5),
               (5,18), (45,18), #(95,18),
               (5,30), (45,30), #(95,30),
               (5,42), (45,42), #(95,42),
               (115,5) ) 
disp_info = displayio.Group()
for (x,y) in labels_pos:
    disp_info.append( label.Label(terminalio.FONT, text="123.4", x=x, y=y) )
disp_group.append(disp_info)
disp_info[-1].text = "dronesynth"
disp_info[-1].label_direction = "UPR"

def display_update():
    for i in range(num_pads):
        for j in range(oscs_per_pad):
            new_str = "%.1f" % voice_vals[i][j]
            old_str = disp_info[i*oscs_per_pad + j].text 
            if new_str != old_str: 
                disp_info[i*oscs_per_pad + j].text = new_str
    
def converge_vals(speed=0.1):
    pass

# --------------------------------------------------------

# get initial knob vals for the scalers
(knobA_val, knobB_val) = [v/256 for v in qts.read_pots()]

for i in range(num_pads):
    vs = [initial_vals[i], 0]
    voice_vals.append(vs)
    
    # set up default freqs in droney
    freqs = get_freqs_by_knobs(*vs)
    print("freqs:", freqs)
    droney.set_voice_freqs(i, freqs)

scalerA = ParamScaler(voice_vals[0][0], knobA_val)
scalerB = ParamScaler(voice_vals[0][1], knobB_val)


display_update()

while True:
    time.sleep(0.001)
    
    (knobA_val, knobB_val) = [v/256 for v in qts.read_pots()]
    
    # if we're pressing a pad
    if pad_num is not None: 
        
        valA = scalerA.update(knobA_val)
        valB = scalerB.update(knobB_val)
        
        print("knobA:%.1f knobB:%.1f  valA:%.1f  valB:%.1f" %
              (knobA_val, knobB_val, valA, valB))

        freqs = get_freqs_by_knobs(valA,valB)
        droney.set_voice_freqs(pad_num, freqs)

        voice_vals[touch.key_number] = [valA,valB]
        display_update()
        
    else:
        #droney.set_pitch_lfo_amount(knobB_val/255)
        pass


    if touches := qts.check_touch():
        for touch in touches:
            
            if touch.pressed:
                pad_num = touch.key_number
                # restore vals for this pad 
                lastA, lastB = voice_vals[pad_num]  
                scalerA.reset(lastA, knobA_val)
                scalerB.reset(lastB, knobB_val)

            if touch.released:
                pad_num = None

    if key := qts.check_key():
        if key.pressed:
            print("button!")
            button_held = True
            button_held_time = time.monotonic()
            droney.print_freqs()
            if pad_num is not None: # pressing a pad toggles voice
                droney.toggle_voice_mute(pad_num)

            
        if key.released:
            button_held = False


    button_time_delta = time.monotonic() - button_held_time
    if button_held and button_time_delta > 1:
        # print("drone freqs")
        # for i,vs in enumerate(voice_vals):
        #     print("%d: " % i, end='')
        #     for v in vs:
        #         print("%.2f, " % v, end='')
        #     print()
            
        converge_valA, converge_valB = voice_vals[0]
        cff = 0.05
        for i in range(1,num_pads):
            voice_vals[i][0] = cff*converge_valA + (1-cff)*voice_vals[i][0]
            freqs = get_freqs_by_knobs(*voice_vals[i])
            droney.set_voice_freqs(i, freqs)
            display_update()
            
            





                
