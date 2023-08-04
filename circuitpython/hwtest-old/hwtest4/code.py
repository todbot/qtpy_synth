# simpletouchsynth_code.py -- simple touchpad synth, touch pads more to move filter freq
# 12 Jul 2023 - @todbot / Tod Kurt
# part of https://github.com/todbot/qtpy_synth
#

import time
import random
import asyncio
import synthio
import ulab.numpy as np

import displayio, terminalio, vectorio
from adafruit_display_text import bitmap_label as label

from qtpy_synth import QTPySynth

class SynthConfig():
    def __init__(self):
        self.filter_type = 'lpf'
        self.filter_f = 2000
        self.filter_q = 1.2

qts = QTPySynth()
cfg = SynthConfig()
f_orig = 0

touch_midi_notes = [40, 48, 52, 60] # can be float
touch_notes = [None] * 4

wave_saw = np.linspace(30000,-30000, num=512, dtype=np.int16)  # default squ is too clippy
amp_env = synthio.Envelope(sustain_level=0.8, release_time=0.4, attack_time=0.001)
qts.synth.envelope = amp_env

# set up display with our 3 bits of info
disp_group = displayio.Group()
qts.display.root_group = disp_group

label_pos = ( (5,5), (30,5), (60,5) )  # filter_type, filter_f, filter_q
disp_info = displayio.Group()
for (x,y) in label_pos:
    disp_info.append( label.Label(terminalio.FONT, text="-", x=x, y=y) )
disp_group.append(disp_info)



def map_range(s, a1, a2, b1, b2):  return  b1 + ((s - a1) * (b2 - b1) / (a2 - a1))

def display_update():
    f_str = "%4d" % cfg.filter_f
    q_str = "%1.1f" % cfg.filter_q

    if cfg.filter_type != disp_info[0].text:
        disp_info[0].text = cfg.filter_type

    if f_str != disp_info[1].text:
        disp_info[1].text = f_str

    if q_str != disp_info[2].text:
        disp_info[2].text = q_str
        print("edit q", q_str)

def touch_on(i):
    global f_orig
    print("touch press",i)
    f = synthio.midi_to_hz(touch_midi_notes[i])
    n = synthio.Note( frequency=f, waveform=wave_saw, filter=make_filter() )
    qts.synth.press( n )
    touch_notes[i] = n
    qts.led.fill(0xff00ff)
    f_orig = cfg.filter_f

def touch_off(i):
    global f_orig
    #print("touch release", i)
    if touch_notes[i]:
        qts.synth.release( touch_notes[i] )
    qts.led.fill(0)
    cfg.filter_f = f_orig
    f_orig=0

def touch_hold(i,v):
    vn = min(max(0, v),2000)
    cfg.filter_f  = min(f_orig * (1 + vn/1000), 8000)
    print("hold %d %d %d" % (i,vn, cfg.filter_f))

filter_types = ['lpf', 'hpf', 'bpf']

def make_filter():
    if cfg.filter_type == 'lpf':
        filter = qts.synth.low_pass_filter(cfg.filter_f, cfg.filter_q)
    elif cfg.filter_type == 'hpf':
        filter = qts.synth.high_pass_filter(cfg.filter_f, cfg.filter_q)
    elif cfg.filter_type == 'bpf':
        filter = qts.synth.band_pass_filter(cfg.filter_f, cfg.filter_q)
    else:
        print("unknown filter type", cfg.filter_type)
    return filter

def update_filter_cfg(filter_type, filter_f, filter_q):
    cfg.filter_type = filter_type
    cfg.filter_f = filter_f
    cfg.filter_q = filter_q

# --------------------------------------------------------

async def display_updater():
    while True:
        print("knobs:", int(qts.knobA//255), int(qts.knobB//255)
            #qts.touchins[0].raw_value, qts.touchins[1].raw_value,
            #qts.touchins[3].raw_value, qts.touchins[2].raw_value
        )
        display_update()
        await asyncio.sleep(0.1)

async def input_handler():
    while True:
        key = qts.check_key()
        qts.check_touch( touch_on, touch_off, touch_hold )

        (knobA, knobB) = qts.read_pots()
        if key == "pressed":
            ftpos = (filter_types.index(cfg.filter_type)+1) % len(filter_types)
            cfg.filter_type = filter_types[ ftpos ]

        if f_orig==0:  # HACK
            cfg.filter_f = map_range( knobA, 0,65535, 30, 4000)
        cfg.filter_q = map_range( knobB, 0,65535, 0.1, 2.8)

        await asyncio.sleep(0.01)

async def filter_tweaker():
    while True:
        for n in touch_notes:
            if n:
                n.filter = make_filter()
        await asyncio.sleep(0.01)

print("qtpy_synth hwtest4 ready")

async def main():
    task1 = asyncio.create_task(display_updater())
    task2 = asyncio.create_task(input_handler())
    task3 = asyncio.create_task(filter_tweaker())
    await asyncio.gather(task1,task2,task3)

asyncio.run(main())



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
