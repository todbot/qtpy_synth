# simpletouchsynth_code.py -- simple touchpad synth, touch pads more to move filter freq
# 12 Jul 2023 - @todbot / Tod Kurt
# part of https://github.com/todbot/qtpy_synth
#
# Needed libraries to install:
#  circup install asyncio neopixel adafruit_debouncer adafruit_displayio_ssd1306 adafruit_display_text
# Also install "qtpy_synth" directory in CIRCUITPY
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
import qtpy_synth.winterbloom_smolmidi as smolmidi

class SynthConfig():
    def __init__(self):
        self.filter_type = 'lpf'
        self.filter_f = 2000
        self.filter_q = 1.2
        self.filter_mod = 0

qts = Hardware()
cfg = SynthConfig()

touch_midi_notes = [40, 48, 52, 60] # can be float
notes_playing = {}  # dict of notes currently playing

# let's get the midi going
midi_usb_in = smolmidi.MidiIn(usb_midi.ports[0])
midi_uart_in = smolmidi.MidiIn(qts.midi_uart)

# set up some default synth parameters
wave_saw = np.linspace(30000,-30000, num=512, dtype=np.int16)
# default squ is too clippy, should be 3dB down or so

amp_env = synthio.Envelope(sustain_level=0.8, release_time=0.6, attack_time=0.001)
qts.synth.envelope = amp_env

# set up display with our 3 chunks of info
disp_group = displayio.Group()
qts.display.root_group = disp_group

labels_pos = ( (5,5), (50,5), (100,5), (15,50) )  #  filter_f, filter_type, filter_q,  hellotext
disp_info = displayio.Group()
for (x,y) in labels_pos:
    disp_info.append( label.Label(terminalio.FONT, text="-", x=x, y=y) )
disp_group.append(disp_info)
disp_info[3].text = "simpletouchsynth"

def map_range(s, a1, a2, b1, b2):  return  b1 + ((s - a1) * (b2 - b1) / (a2 - a1))

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

def note_on( notenum, vel=64):
    print("note_on", notenum, vel)
    cfg.filter_mod = (vel/127) * 1500
    f = synthio.midi_to_hz(notenum)
    note = synthio.Note( frequency=f, waveform=wave_saw, filter=make_filter() )
    notes_playing[notenum] = note
    qts.synth.press( note )
    qts.led.fill(0xff00ff)

def note_off( notenum, vel=0):
    print("note_off", notenum, vel)
    if note := notes_playing[notenum]:
        qts.synth.release( note )
    qts.led.fill(0)

# how to do this
def touch_hold(i,v):  # callback
    vn = min(max(0, v), 2000)  # ensure touch info stays positive
    cfg.filter_mod  =  (vn/2000) * 3000   # range 0-3000
    print("hold %d %d %d" % (i,vn, cfg.filter_mod))

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


# --------------------------------------------------------

async def display_updater():
    while True:
        print("knobs:", int(qts.knobA//255), int(qts.knobB//255),
            #qts.touchins[0].raw_value, qts.touchins[1].raw_value,
            #qts.touchins[3].raw_value, qts.touchins[2].raw_value
        )
        display_update()
        await asyncio.sleep(0.1)

async def input_handler():
    while True:
        (knobA, knobB) = qts.read_pots()

        if key := qts.check_key():
            if key.pressed:
                ftpos = (filter_types.index(cfg.filter_type)+1) % len(filter_types)
                cfg.filter_type = filter_types[ ftpos ]

        if touches := qts.check_touch():
            for touch in touches:
                if touch.pressed: note_on( touch_midi_notes[touch.key_number] )
                if touch.released: note_off( touch_midi_notes[touch.key_number] )

        qts.check_touch_hold(touch_hold)

        cfg.filter_f = map_range( knobA, 0,65535, 30, 8000)
        cfg.filter_q = map_range( knobB, 0,65535, 0.1, 3.0)

        await asyncio.sleep(0.01)

async def synth_updater():
    # for any notes playing, adjust its filter in realtime
    while True:
        for n in notes_playing.values():
            if n:
                n.filter = make_filter()
        await asyncio.sleep(0.01)

async def midi_handler():
    while True:
        while msg := midi_usb_in.receive() or midi_uart_in.receive():
            if msg.type == smolmidi.NOTE_ON:
                note_on( msg.data[0], msg.data[1] )
            elif msg.type == smolmidi.NOTE_OFF:
                note_off( msg.data[0], msg.data[1] )
        await asyncio.sleep(0.001)

print("-- qtpy_synth simpletouchsynth ready --")

async def main():
    task1 = asyncio.create_task(display_updater())
    task2 = asyncio.create_task(input_handler())
    task3 = asyncio.create_task(synth_updater())
    task4 = asyncio.create_task(midi_handler())
    await asyncio.gather(task1,task2,task3,task4)

asyncio.run(main())
