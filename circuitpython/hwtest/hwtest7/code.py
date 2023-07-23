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

import usb_midi
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

patch1.filt_env_params.attack_time = 0.5
patch1.amp_env_params.attack_time = 0.01

patch2.filt_type = 'hp'
patch2.wave = 'square'
patch2.detune=1.01
patch2.filt_env_params.attack_time = 0.0 # turn off filter  FIXME
patch2.amp_env_params.release_time = 1.0

patch3.waveformB = 'square'  # show off wavemixing
patch3.filt_type = 'bp'

patch4.wave_type = 'wtb'
#patch4.wave = 'wav/MICROW02.WAV'
#patch4.wave = 'wav/BRAIDS04.WAV'
patch4.wave = 'wav/PLAITS02.WAV'
#patch4.detune = 0  # disable 2nd oscillator
patch4.amp_env_params.release_time = 0.5

#print(patch1.amp_env_params)
#print(patch2.amp_env_params)
print("------")

qts = QTPySynth( patch4 )

#inst = Instrument(qts.synth)  # basic instrument to test things out
inst = PolyTwoOsc(qts.synth, patch4)

midi_usb = adafruit_midi.MIDI(midi_in=usb_midi.ports[0], in_channel=0 )

midi_notes = [40, 48, 52, 55] # can be float

def map_range(s, a1, a2, b1, b2):  return  b1 + ((s - a1) * (b2 - b1) / (a2 - a1))

# fixme: put these in qtpy_synth.py
knob_mode = 0  # 0=frequency, 1=wavemix, 2=, 3=
key_held = False
key_with_touch = False
pickupA = False
pickupB = False

#  UI: key press+release == change what knobs are editing
#      key hold + touch = load patch 1,2,3,4
def touch_on(i):
    global key_with_touch
    print("touch_on:",i)
    if key_held:  # load a patch
        print("load patch",i)
        inst.load_patch(patches[i])
        qts.patch = patches[i]
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
    global key_held, knob_mode, pickupA, pickupB
    print("keyrelease")
    key_held = False
    if key_with_touch:
        pass
    else:  # or change what knobs do
        knob_mode = (knob_mode + 1) % 4
        print("knob mode:",knob_mode)
        qts.selected_disp = knob_mode
        pickupA,pickupB = False,False

async def instrument_updater():
    while True:
        inst.update()
        await asyncio.sleep(0.001)

async def display_updater():
    while True:
        qts.display_update()
        await asyncio.sleep(0.1)

async def input_handler():
    global pickupA, pickupB
    while True:
        # MIDI input
        if msg := midi_usb.receive():
            if isinstance(msg, NoteOn) and msg.velocity != 0:
                inst.note_on(msg.note)
                qts.led.fill(0xff00ff)
            elif isinstance(msg,NoteOff) or isinstance(msg,NoteOn) and msg.velocity==0:
                inst.note_off(msg.note)
                qts.led.fill(0x000000)

        # KEY & TOUCH input
        qts.check_key( key_press, key_release )
        qts.check_touch( touch_on, touch_off ) #, touch_hold )

        (knobA, knobB) = qts.read_pots()

        if knob_mode == 0:
            filt_f = map_range( knobA, 0,65535, 30, 8000)
            filt_q = map_range( knobB, 0,65535, 0.1, 3)

            if abs(inst.patch.filt_f - filt_f) <= (filt_f * 0.1):
                pickupA = True
            if abs(inst.patch.filt_q - filt_q) <= (filt_q * 0.1):
                pickupB = True

            if pickupA:
                inst.patch.filt_f = filt_f
            if pickupB:
                inst.patch.filt_q = filt_q

        elif knob_mode == 1:
            wave_mix = map_range( knobA, 0,65535, 0, 1)
            detune = map_range( knobB, 0,65535, 1, 1.5)
            if abs(inst.patch.wave_mix - wave_mix) <= 0.1 :
                pickupA = True
            if abs(inst.patch.detune - detune) <= (detune * 0.1):
                pickupB = True

            if pickupA:
                inst.patch.wave_mix = wave_mix

            if pickupB and inst.patch.detune:
                inst.patch.detune = detune
                inst.redetune()   # fixme how to do held-note detune is this it?

        elif knob_mode == 2:
            pass

        elif knob_mode == 3:
            pass

        else:
            pass

        await asyncio.sleep(0.001)


print("qtpy_synth hwtest7 ready")

async def main():
    task1 = asyncio.create_task(display_updater())
    task2 = asyncio.create_task(input_handler())
    task3 = asyncio.create_task(instrument_updater())
    await asyncio.gather(task1,task2,task3)

asyncio.run(main())
