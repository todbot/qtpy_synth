#
#
# UI Ideas:
#  - touch buttons
#    - press to trigger note
#    - hold to enable setting of button params, edit with potA, potB, sw
#      - what about holding multiple  (maybe do not allow)
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

class SynthioPatch():
    def __init__(self):
        pass
    def update(self):
        pass

import asyncio
import synthio
import ulab.numpy as np
import time

import adafruit_midi
from adafruit_midi.note_on import NoteOn
from adafruit_midi.note_off import NoteOff

import displayio
displayio.release_displays() # can we put this in sequencer_hardware?

from qtpy_synth import QTPySynth

qts = QTPySynth()

wave_saw = np.linspace(30000,-30000, num=512, dtype=np.int16)  # default squ is too clippy
amp_env = synthio.Envelope(sustain_level=1.0, release_time=0.4, attack_time=0.001)
qts.synth.envelope = amp_env

midi_notes = [40, 48, 60, 52] # can be float
touch_notes = [None] * 4


def touch_on(i):
    print("touch press",i)
    f = synthio.midi_to_hz(midi_notes[i])
    n = synthio.Note( frequency=f, waveform=wave_saw )
    qts.synth.press( n )
    touch_notes[i] = n
    qts.led.fill(0xff00ff)

def touch_off(i):
    #print("touch release", i)
    qts.synth.release( touch_notes[i] )
    qts.led.fill(0)

async def printer():
    while True:
        #print("%3d %3d" % (knobA.value//255, knobB.value//255))
        print(qts.knobA.value//255, qts.knobB.value//255, qts.touchins[2].raw_value, qts.touchins[3].raw_value)
        await asyncio.sleep(0.3)

async def key_handler():
    while True:
        qts.check_key()
        qts.check_touch( touch_on, touch_off )
        await asyncio.sleep(0.01)


# main coroutine
async def main():  # Don't forget the async!
    task1 = asyncio.create_task(printer())
    task2 = asyncio.create_task(key_handler())
    await asyncio.gather(task1,task2)

asyncio.run(main())



note = synthio.Note(frequency=0)
print("qtpy_synth test2 ready")
while True:
    #check_touch()
    if key := keys.events.get():
        if key.released:
            synth.release( note )
        if key.pressed:
            #print("knobs", knobA.value, knobB.value)
            note = synthio.Note(frequency=synthio.midi_to_hz(random.randint(32,48)), waveform=wave_saw)
            synth.press(note)
            print("key:", key, i2c.frequency)

    #text1.text = time.monotonic()
