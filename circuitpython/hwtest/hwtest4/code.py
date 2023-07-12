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

# class SynthioPatch():
#     def __init__(self):
#         pass
#     def update(self):
#         pass

import random
import asyncio
import synthio
import ulab.numpy as np
import time

import adafruit_midi
from adafruit_midi.note_on import NoteOn
from adafruit_midi.note_off import NoteOff

from qtpy_synth import QTPySynth

qts = QTPySynth()
qts.display_setup()

wave_saw = np.linspace(30000,-30000, num=512, dtype=np.int16)  # default squ is too clippy
amp_env = synthio.Envelope(sustain_level=1.0, release_time=0.4, attack_time=0.001)
qts.synth.envelope = amp_env

midi_notes = [40, 48, 52, 60] # can be float
touch_notes = [None] * 4

# # this display stuff will all go in a class soon
# import vectorio, displayio
# note_group = displayio.Group()
# wave_group = displayio.Group()
# nx,ny,nw,nh = 10,30,3,5
# wx,wy,ww,wh = 10,60,3,5
# dw,dh = qts.display.width, qts.display.height

# def make_display():
#     step_pal = displayio.Palette(2)
#     step_pal[0] = 0xffffff  # the only color we got
#     #step_pal[1] = 0x808080
#     reticules = displayio.Group()
#     reticules.append( vectorio.Rectangle(pixel_shader=step_pal, width=dw, height=1, x=0, y=dh//2) )
#     qts.disp_group.append(reticules)

#     for i in range(8):
#         note_group.append(vectorio.Rectangle(pixel_shader=step_pal, width=nw, height=nh, x=nx+i*10, y=ny))
#         wave_group.append(vectorio.Rectangle(pixel_shader=step_pal, width=ww, height=wh, x=wx+i*10, y=wy))
#     qts.disp_group.append(note_group)
#     qts.disp_group.append(wave_group)

# def update_display(steps):
#     for i in range(8):
#         note_group[i].y = ny - random.randint(30,60) // 4 #steps[i].notenum // 5
#         wave_group[i].y = wy - random.randint(0,8) * 4 #steps[i].waveid * 4
#         #if i==0: print( note_group[i].height )

# make_display()
# update_display(None)

def map_range(s, a1, a2, b1, b2):  return  b1 + ((s - a1) * (b2 - b1) / (a2 - a1))

f_orig = 0

def touch_on(i):
    global f_orig
    print("touch press",i)
    f = synthio.midi_to_hz(midi_notes[i])
    n = synthio.Note( frequency=f, waveform=wave_saw, filter=qts.make_filter() )
    qts.synth.press( n )
    touch_notes[i] = n
    qts.led.fill(0xff00ff)
    f_orig = qts.cfg.filter_f

def touch_off(i):
    global f_orig
    #print("touch release", i)
    if touch_notes[i]:
        qts.synth.release( touch_notes[i] )
    qts.led.fill(0)
    qts.cfg.filter_f = f_orig
    f_orig=0

def touch_hold(i,v):
    vn = min(max(0, v),2000)
    qts.cfg.filter_f  = f_orig * (1 + vn/500)
    print("hold %d %d %d" % (i,vn, qts.cfg.filter_f))

async def printer():
    while True:
        print(
            #qts.knobA.value//255, qts.knobB.value//255,
            qts.touchins[0].raw_value, qts.touchins[1].raw_value,
            qts.touchins[3].raw_value, qts.touchins[2].raw_value)
        qts.display_update()
        await asyncio.sleep(0.1)

async def input_handler():
    while True:
        qts.check_key()
        qts.check_touch( touch_on, touch_off, touch_hold )

        (knobA, knobB) = qts.read_pots()
        if f_orig==0:  # HACK
            qts.cfg.filter_f = map_range( knobA, 0,65535, 30, 4000)
        qts.cfg.filter_q = map_range( knobB, 0,65535, 0.1, 2)

        await asyncio.sleep(0.01)

async def filter_tweaker():
    while True:
        for n in touch_notes:
            if n:
                n.filter = qts.make_filter()
        await asyncio.sleep(0.01)

print("qtpy_synth hwtest4 ready")

async def main():
    task1 = asyncio.create_task(printer())
    task2 = asyncio.create_task(input_handler())
    task3 = asyncio.create_task(filter_tweaker())
    await asyncio.gather(task1,task2,task3)

asyncio.run(main())



# note = synthio.Note(frequency=0)
# while True:
#     #check_touch()
#     if key := keys.events.get():
#         if key.released:
#             synth.release( note )
#         if key.pressed:
#             #print("knobs", knobA.value, knobB.value)
#             note = synthio.Note(frequency=synthio.midi_to_hz(random.randint(32,48)), waveform=wave_saw)
#             synth.press(note)
#             print("key:", key, i2c.frequency)

#     #text1.text = time.monotonic()
