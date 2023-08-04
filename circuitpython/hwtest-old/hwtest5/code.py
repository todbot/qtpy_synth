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

qts = QTPySynth()
qts.display_setup()

patch1 = Patch()
patch2 = Patch()

patch1.filt_env_params.attack_time = 0.5
patch2.waveform = 'square'
patch2.detune=1.01
patch1.amp_env_params.attack_time = 1.5
patch2.filt_env_params.attack_time = 0.0 # turn off filter
patch2.amp_env_params.release_time = 1.0

print(patch1.amp_env_params)
print(patch2.amp_env_params)  # why is th
print("------")

#inst = Instrument(qts.synth)  # to test things out
inst = PolyTwoOsc(qts.synth, patch2)

midi_notes = [40, 48, 52, 60] # can be float

def map_range(s, a1, a2, b1, b2):  return  b1 + ((s - a1) * (b2 - b1) / (a2 - a1))

def touch_on(i):
    print("touch_on:",i)
    qts.led.fill(0xff00ff)
    midi_note = midi_notes[i]
    inst.note_on(midi_note)

def touch_off(i):
    print("touch_off:",i)
    qts.led.fill(0)
    midi_note = midi_notes[i]
    inst.note_off(midi_note)
    print( inst.voices )

def key_press():
    print("keypress")
    qts.led.fill(0xffffff)
    if inst.patch == patch1:
        inst.load_patch(patch2)
    elif inst.patch == patch2:
        inst.load_patch(patch1)

def key_release():
    print("keyrelease")
    qts.led.fill(0)

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

        inst.patch.filt_f = map_range( knobA, 0,65535, 30, 4000)
        inst.patch.filt_q = map_range( knobB, 0,65535, 0.1, 3)

        qts.cfg.filter_f = inst.patch.filt_f
        qts.cfg.filter_q = inst.patch.filt_q

        await asyncio.sleep(0.01)


print("qtpy_synth hwtest5 ready")

async def main():
    task1 = asyncio.create_task(display_updater())
    task2 = asyncio.create_task(input_handler())
    task3 = asyncio.create_task(instrument_updater())
    await asyncio.gather(task1,task2,task3)

asyncio.run(main())
