# qtpy_synth_test2.py -- test hardware of qtpy_synth board
# 27 Jun 2023 - @todbot / Tod Kurt
#
import asyncio
import time, random
import board, busio
# basic i/o
import analogio, keypad
# synth
import audiopwmio, audiomixer, synthio
import ulab.numpy as np
# display
import displayio, terminalio
import adafruit_displayio_ssd1306  # circup install adafruit_displayio_ssd1306
from adafruit_display_text import bitmap_label as label
# touch
import touchio
from adafruit_debouncer import Debouncer # circup install adafruit_debouncer

displayio.release_displays()

knobA = analogio.AnalogIn(board.A0)
knobB = analogio.AnalogIn(board.A1)
keys = keypad.Keys( pins=(board.TX,),  value_when_pressed=False )

touch_pins = (board.A3, board.A2, board.SCK, board.MISO)
touchins = []
touchs = []
for pin in touch_pins:
    touchin = touchio.TouchIn(pin)
    touchins.append(touchin)
    touchs.append( Debouncer(touchin) )

uart = busio.UART(rx=board.RX, baudrate=31250, timeout=0.001)
i2c = busio.I2C(scl=board.SCL, sda=board.SDA, frequency=1_000_000 )

dw,dh = 128, 64
display_bus = displayio.I2CDisplay(i2c, device_address=0x3c )
display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=dw, height=dh, rotation=180)

audio = audiopwmio.PWMAudioOut(board.MOSI)
mixer = audiomixer.Mixer(voice_count=1, sample_rate=28000, channel_count=1,
                         bits_per_sample=16, samples_signed=True,
                         #buffer_size=4096)
                         buffer_size=8192)
synth = synthio.Synthesizer(sample_rate=28000)
audio.play(mixer)
mixer.voice[0].level = 0.5 # turn down the volume a bit since this can get loud
mixer.voice[0].play(synth)

wave_saw = np.linspace(30000,-30000, num=512, dtype=np.int16)  # default squ is too clippy
amp_env = synthio.Envelope(sustain_level=1.0, release_time=0.4, attack_time=0.001)
synth.envelope = amp_env

# maingroup = displayio.Group()
# display.show(maingroup)
# text1 = label.Label(terminalio.FONT, text="hello\nworld...", line_spacing=0.75, x=5,y=dh//4,scale=1)
# text2 = label.Label(terminalio.FONT, text="@todbot", line_spacing=0.75, x=dw//2, y=dh-15, scale=1)
# maingroup.append(text1)
# maingroup.append(text2)

midi_notes = (38, 42, 48, 55)
touch_notes = [None] * 4

def check_touch():
    for i in range(len(touchs)):
        touch = touchs[i]
        touch.update()
        if touch.rose:
            #print("touch press",i)
            f = synthio.midi_to_hz(midi_notes[i])
            n = synthio.Note( frequency=f, waveform=wave_saw )
            synth.press( n )
            touch_notes[i] = n
        if touch.fell:
            #print("touch release", i)
            synth.release( touch_notes[i] )

note = synthio.Note(frequency=0)

async def printer():
    while True:
        #print("%3d %3d" % (knobA.value//255, knobB.value//255))
        print(knobA.value//255, knobB.value//255, touchins[2].raw_value, touchins[3].raw_value)
        await asyncio.sleep(0.3)

async def key_handler():
    while True:
        check_touch()
        if key := keys.events.get():
            if key.released:
                synth.release( note )
            if key.pressed:
                f = synthio.midi_to_hz(random.randint(32,48))
                note = synthio.Note(frequency=f, waveform=wave_saw)
                synth.press(note)
        await asyncio.sleep(0.01)


# main coroutine
async def main():  # Don't forget the async!
    task1 = asyncio.create_task(printer())
    task2 = asyncio.create_task(key_handler())
    await asyncio.gather(task1,task2)

asyncio.run(main())
