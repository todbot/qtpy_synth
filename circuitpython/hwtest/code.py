# qtpy_synth_hwtest_code.py -- test hardware of qtpy_synth board
# 27 Jun 2023 - @todbot / Tod Kurt
#
# Functionality:
# - touch pads 1,2,3,4 trigger synth notes (defined in 'midi_notes')
# - middle button triggers random synth notes
# - left knob controls filter cutoff
# - right knob controls filter resonance
# - sending MIDI via USB or TRS UART MIDI will print MIDI messages to REPL and play simple tones
#
# Libaries needed:
# - asyncio
# - adafruit_debouncer
# - adafruit_displayio_ssd1306
# - adafruit_display_text
# - winterbloom_smolmidi   (included, but from https://github.com/wntrblm/Winterbloom_SmolMIDI)
# Install them all with:
#   circup install asyncio adafruit_debouncer adafruit_displayio_ssd1306 adafruit_display_text
#
#
import asyncio
import time, random
import board
# knobs
import analogio, keypad
# audio
import audiopwmio, audiomixer, synthio
import ulab.numpy as np
# display
import displayio, terminalio
import adafruit_displayio_ssd1306
from adafruit_display_text import bitmap_label as label
# touch
import touchio
from adafruit_debouncer import Debouncer
# midi
import busio
import usb_midi
import qtpy_synth.winterbloom_smolmidi as smolmidi

midi_notes = (33, 45, 52, 57)
filter_freq = 4000
filter_resonance = 1.2

displayio.release_displays()

# set up our knobs and button
knobA = analogio.AnalogIn(board.A0)
knobB = analogio.AnalogIn(board.A1)
keys = keypad.Keys( pins=(board.TX,),  value_when_pressed=False )

# set up touch pins using a debouncer
touch_pins = (board.A3, board.A2, board.MISO, board.SCK)
touchins = []
touchs = []
for pin in touch_pins:
    touchin = touchio.TouchIn(pin)
    touchins.append(touchin)
    touchs.append( Debouncer(touchin) )

midi_uart = busio.UART(rx=board.RX, baudrate=31250, timeout=0.001)
i2c = busio.I2C(scl=board.SCL, sda=board.SDA, frequency=1_000_000 )

dw,dh = 128, 64
display_bus = displayio.I2CDisplay(i2c, device_address=0x3c )
display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=dw, height=dh, rotation=180)

# set up the synth->audio system
audio = audiopwmio.PWMAudioOut(board.MOSI)
mixer = audiomixer.Mixer(voice_count=1, sample_rate=28000, channel_count=1,
                         bits_per_sample=16, samples_signed=True,
                         buffer_size=4096)  # need a big buffer when screen updated
synth = synthio.Synthesizer(sample_rate=28000)
audio.play(mixer)
mixer.voice[0].level = 0.75 # turn down the volume a bit since this can get loud
mixer.voice[0].play(synth)

# set up MIDI inputs
midi_usb_in = smolmidi.MidiIn(usb_midi.ports[0])
midi_uart_in = smolmidi.MidiIn(midi_uart)

# set up the synth
wave_saw = np.linspace(30000,-30000, num=256, dtype=np.int16)  # default squ is too clippy
amp_env = synthio.Envelope(sustain_level=0.8, release_time=0.4, attack_time=0.001)
synth.envelope = amp_env

# set up info to be displayed
maingroup = displayio.Group()
display.show(maingroup)
text1 = label.Label(terminalio.FONT, text="helloworld...", x=0, y=10)
text2 = label.Label(terminalio.FONT, text="@todbot", x=0, y=25)
text3 = label.Label(terminalio.FONT, text="hwtest. press!", x=0, y=50)
for t in (text1, text2, text3):
    maingroup.append(t)

touch_notes = [None] * 4
sw_pressed = False

def check_touch():
    for i in range(len(touchs)):
        touch = touchs[i]
        touch.update()
        if touch.rose:
            print("touch press",i)
            f = synthio.midi_to_hz(midi_notes[i])
            filt = synth.low_pass_filter(filter_freq, filter_resonance)
            n = synthio.Note( frequency=f, waveform=wave_saw, filter=filt)
            synth.press( n )
            touch_notes[i] = n
        if touch.fell:
            print("touch release", i)
            synth.release( touch_notes[i] )

async def debug_printer():
    while True:
        text1.text = "K:%3d %3d S:%d" % (knobA.value//255, knobB.value//255, sw_pressed)
        text2.text = "T:" + ''.join(["%3d " % v for v in (
            touchins[0].raw_value//16, touchins[1].raw_value//16,
            touchins[2].raw_value//16, touchins[3].raw_value//16)])
        print(text1.text, text2.text, midi_usb_in._error_count)
        await asyncio.sleep(0.3)

async def input_handler():
    global sw_pressed
    global filter_freq, filter_resonance

    note = None

    while True:
        filter_freq = knobA.value/65535 * 8000 + 100  # range 100-8100
        filter_resonance = knobB.value/65535 * 3 + 0.2  # range 0.2-3.2

        for n in touch_notes:  # real-time adjustment of filter
            if n:
                n.filter = synth.low_pass_filter(filter_freq, filter_resonance)

        check_touch()

        if key := keys.events.get():
            if key.released:
                sw_pressed = False
                synth.release( note )
                print("button release!")
            if key.pressed:
                sw_pressed = True
                f = synthio.midi_to_hz(random.randint(32,60))
                note = synthio.Note(frequency=f, waveform=wave_saw) # , filter=filter)
                synth.press(note)
                print("button press!")
        await asyncio.sleep(0.01)


async def midi_handler():
    while True:
        while msg := midi_uart_in.receive() or midi_usb_in.receive():
            if msg.type == smolmidi.NOTE_ON:
                chan = msg.channel
                note = msg.data[0]
                vel = msg.data[1]
                print('NoteOn: Ch: {} Note: {} Vel:{}'.format(chan, note, vel))
                synth.press( note )
            elif msg.type == smolmidi.NOTE_OFF:
                chan = msg.channel
                note = msg.data[0]
                vel = msg.data[1]
                print('NoteOff: Ch: {} Note: {} Vel:{}'.format(chan, note, vel))
                synth.release( note )
            elif msg.type == smolmidi.PITCH_BEND:
                chan = msg.channel
                pbval = (msg.data[1] << 7) | msg.data[0]
                print("PitchBend: Ch: {} Bend: {}".format(chan, pbval))
            elif msg.type == smolmidi.CC:
                chan = msg.channel
                ccnum = msg.data[0]
                ccval = msg.data[1]
                print('CC Ch: {}, Num: {} Val: {}'.format(chan, ccnum, ccval))
            elif msg.type == smolmidi.CHANNEL_PRESSURE:
                chan = msg.channel
                press_val = msg.data[0]
                print('Ch Pressure: Ch: {}, Val: {}'.format(chan, press_val))
            elif msg.type == smolmidi.SYSTEM_RESET:
                print('System reset')
            else:
                print("unknown message:",msg)
        await asyncio.sleep(0)


# main coroutine
async def main():  # Don't forget the async!
    task1 = asyncio.create_task(debug_printer())
    task2 = asyncio.create_task(input_handler())
    task3 = asyncio.create_task(midi_handler())
    await asyncio.gather(task1,task2,task3)

print("hello qtpy_synth hwtest")
asyncio.run(main())
