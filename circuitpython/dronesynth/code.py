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
from my_little_droney import (MyLittleDroney, SynthConfig,
                              get_freqs_by_knobs, note_to_knobval, knobval_to_note)

import microcontroller
microcontroller.cpu.frequency = 250_000_000  # overclock! vrrroomm

num_pads = 4
oscs_per_pad = 2
note_offset = 12
note_range = 60
initial_vals = (note_to_knobval(36), note_to_knobval(48),
                note_to_knobval(36), note_to_knobval(60))

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
labels_pos = ( (5,5), (45,5),
               (5,18), (45,18),
               (5,30), (45,30),
               (5,42), (45,42),
               (78,5), (78,18), (78,30), (78,42),
               (115,5) # dronesynth logo vertical
              ) 
disp_info = displayio.Group()
for (x,y) in labels_pos:
    disp_info.append( label.Label(terminalio.FONT, text="--", x=x, y=y) )
disp_group.append(disp_info)
disp_info[-1].text = "dronesynth"
disp_info[-1].label_direction = "UPR"

def display_update():
    for i in range(num_pads):
        fstr = disp_info[i*2+0].text
        dstr = disp_info[i*2+1].text
        fstr_new = "%.1f" % knobval_to_note(voice_vals[i][0], note_offset, note_range)
        dstr_new = "%.1f" % voice_vals[i][1]
        if fstr_new != fstr:
            disp_info[i*2+0].text = fstr_new
        if dstr_new != dstr:
            disp_info[i*2+1].text = dstr_new
        onoff = "on" if droney.voices[i][0].amplitude else "--"
        if disp_info[8+i].text != onoff:
            disp_info[8+i].text = onoff


# --------------------------------------------------------

# get initial knob vals for the scalers
(knobA_val, knobB_val) = [v/256 for v in qts.read_pots()]

# set up the inital state of the voices
for i in range(num_pads):
    vs = [initial_vals[i], 0]
    voice_vals.append(vs)
    
    # set up default freqs in droney
    freqs = get_freqs_by_knobs(vs[0],vs[1], note_offset, note_range)
    print("freqs:", freqs)
    droney.set_voice_freqs(i, freqs)

# start with only two of the voices sounding
droney.toggle_voice_mute(2)
droney.toggle_voice_mute(3)

scalerA = ParamScaler(voice_vals[0][0], knobA_val)
scalerB = ParamScaler(voice_vals[0][1], knobB_val)

globalA_val = knobA_val
globalB_val = knobB_val

display_update()

debug = False
def dbg(*args,**kwargs):
    if debug: print(*args,**kwargs)

while True:
    time.sleep(0.001)

    #droney.update()
    
    (knobA_val, knobB_val) = [v/256 for v in qts.read_pots()]
    
    # handle held touch pad
    if pad_num is not None: 
        
        valA = scalerA.update(knobA_val) #, debug=True)
        valB = scalerB.update(knobB_val)
        
        dbg("knobA:%.1f knobB:%.1f  valA:%.1f  valB:%.1f" %
            (knobA_val, knobB_val, valA, valB))

        freqs = get_freqs_by_knobs(valA, valB, note_offset, note_range)
        droney.set_voice_freqs(pad_num, freqs)

        voice_vals[touch.key_number] = [valA,valB]
        display_update()
        
    else:
        globalA_val = scalerA.update(knobA_val)
        globalB_val = scalerB.update(knobB_val) # , debug=True)
        #dbg("global: %1.f %1.f" %(globalA_val, globalB_val))
        #droney.set_pitch_lfo_amount(knobB_val/255)
        #note_offset = (globalA_val/255) * 24
        f = 20 + (globalA_val/255) * 3000
        droney.set_filter(f,None)

    # handle pad press
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
                # restore the global vals
                scalerA.reset(globalA_val, knobA_val)
                scalerB.reset(globalB_val, knobB_val)

    # handle tact button press
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

    # handle button held 
    button_time_delta = time.monotonic() - button_held_time
    if button_held and button_time_delta > 1:
        dbg("drone freqs")
        for i,vs in enumerate(voice_vals):
            dbg("%d: " % i, end='')
            for v in vs:
               dbg("%.2f, " % v, end='')
            dbg()


        # if button is held, convert the notes to pad1 note
        converge_valA, converge_valB = voice_vals[0]
        cff = 0.05
        for i in range(1,num_pads):
            voice_vals[i][0] = cff*converge_valA + (1-cff)*voice_vals[i][0]
            freqs = get_freqs_by_knobs(voice_vals[i][0], voice_vals[i][1], note_offset, note_range)
            droney.set_voice_freqs(i, freqs)
            display_update()
            
            





                
