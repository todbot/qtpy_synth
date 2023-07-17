#
#
# UI Ideas:
#  - touch buttons
#    - press to trigger note
#    - hold to enable setting of button params, edit with potA, potB, sw
#      - what about holding multiple  (maybe do not allow)
#    - press hard for filter mod?
#  - pots
#    - if no button press, changes global param, like filter, res
#
#  - sw
#    - toggles currently changeable pot params
#      - param set 1: freq & resonance
#      - param set 2: freq type (LP,HP,BP,BN) & osc detune spread
#      - param set 3: attack & release times
#      - param set 4: LFO1 rate & depth
#
# Arpeggiator?
# How to do patches?
#
# - some patches require usercode timing (filter env)
# -
#

import asyncio
import time
import random
import synthio
import ulab.numpy as np

import adafruit_midi
from adafruit_midi.note_on import NoteOn
from adafruit_midi.note_off import NoteOff

from qtpy_synth import QTPySynth

from synthio_instrument import PolyTwoOsc, Patch, Instrument

patch1 = Patch()
patch2 = Patch()
patch3 = Patch()
patch4 = Patch()
patches = (patch1, patch2, patch3, patch4)
#patch_i = 2

patch1.filt_env_params.attack_time = 0.5
patch1.amp_env_params.attack_time = 0.01

patch2.filt_type = 'hp'
patch2.waveform = 'square'
patch2.detune=1.01
patch2.filt_env_params.attack_time = 0.0 # turn off filter  FIXME
patch2.amp_env_params.release_time = 1.0

patch3.waveformB = 'square'  # show off wavemixing

print(patch1.amp_env_params)
print(patch2.amp_env_params)
print("------")

qts = QTPySynth(patch3)
qts.display_setup()

#inst = Instrument(qts.synth)  # basic instrument to test things out
inst = PolyTwoOsc(qts.synth, patch3)

midi_notes = [40, 48, 52, 60] # can be float

def map_range(s, a1, a2, b1, b2):  return  b1 + ((s - a1) * (b2 - b1) / (a2 - a1))

# fixme: put these in qtpy_synth.py
knob_mode = 1  # 0=frequency, 1=wavemix
key_held = False
key_with_touch = False

#  UI: key press+release == change what knobs are editing
#      key hold + touch = load patch 1,2,3,4
def touch_on(i):
    global key_with_touch
    print("touch_on:",i)
    if key_held:  # load a patch
        inst.load_patch(patches[i])
        qts.cfg = patches[i]
        qts.display_update()
        key_with_touch = True
    else:  # trigger a note
        qts.led.fill(0xff00ff)
        midi_note = midi_notes[i]
        inst.note_on(midi_note)

def touch_off(i):
    global key_with_touch
    print("touch_off:",i)
    if key_with_touch:
        key_with_touch = False
    else:
        qts.led.fill(0)
        midi_note = midi_notes[i]
        inst.note_off(midi_note)
        #print( inst.voices )

def key_press():
    global key_held
    print("keypress")
    key_held = True
    #qts.led.fill(0xffffff)

def key_release():
    global key_held, knob_mode
    print("keyrelease")
    key_held = False
    if key_with_touch:
        pass
    else:  # or change what knobs do
        knob_mode = (knob_mode + 1) % 2
        print("knob mode:",knob_mode)



async def instrument_updater():
    while True:
        inst.update()
        await asyncio.sleep(0.01)

async def display_updater():
    while True:
        #print(
        #    #qts.knobA.value//255, qts.knobB.value//255,
        #    qts.touchins[0].raw_value, qts.touchins[1].raw_value,
        #    qts.touchins[3].raw_value, qts.touchins[2].raw_value)
        qts.display_update()
        await asyncio.sleep(0.1)

async def input_handler():

    while True:
        qts.check_key( key_press, key_release )
        qts.check_touch( touch_on, touch_off ) #, touch_hold )

        (knobA, knobB) = qts.read_pots()

        if knob_mode == 0:
            inst.patch.filt_f = map_range( knobA, 0,65535, 30, 4000)
            inst.patch.filt_q = map_range( knobB, 0,65535, 0.1, 3)

            #qts.cfg.filt_f = inst.patch.filt_f
            #qts.cfg.filt_q = inst.patch.filt_q

        elif knob_mode == 1:
            inst.patch.wave_mix = map_range( knobA, 0,65535, 0,1)
            #qts.cfg.wave_mix = inst.patch.wave_mix*10  # FIXME YO

        else:
            print("wat")

        await asyncio.sleep(0.01)


print("qtpy_synth hwtest5 ready")

async def main():
    task1 = asyncio.create_task(display_updater())
    task2 = asyncio.create_task(input_handler())
    task3 = asyncio.create_task(instrument_updater())
    await asyncio.gather(task1,task2,task3)

asyncio.run(main())
