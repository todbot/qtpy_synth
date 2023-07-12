
import board, busio
import analogio, keypad
import touchio
from adafruit_debouncer import Debouncer # circup install adafruit_debouncer
import neopixel  # circup install neopixel
import audiopwmio, audiomixer, synthio
import ulab.numpy as np
import displayio, terminalio
import adafruit_displayio_ssd1306  # circup install adafruit_displayio_ssd1306
from adafruit_display_text import bitmap_label as label
#import adafruit_midi
#from adafruit_midi.note_on import NoteOn
#from adafruit_midi.note_off import NoteOff

SAMPLE_RATE = 28_000
MIXER_BUFFER_SIZE = 4096
DW,DH = 128, 64  # display width/height

# note: we're hanging on to some of the interstitial objects like 'i2c' & 'display_bus'
# even though we shouldn't, because I think the gc will collect it unless we hold on to it

class QTPySynth():
    def __init__(self):

        self.led = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.2)
        self.knobA = analogio.AnalogIn(board.A0)
        self.knobB = analogio.AnalogIn(board.A1)
        self.keys = keypad.Keys( pins=(board.TX,),  value_when_pressed=False )

        self.touchins = []  # for raw_value
        self.touches = []   # for debouncer
        for pin in (board.A3, board.A2, board.SCK, board.MISO):
           touchin = touchio.TouchIn(pin)
           self.touchins.append(touchin)
           self.touches.append( Debouncer(touchin) )

        self.midi_uart = busio.UART(rx=board.RX, baudrate=31250, timeout=0.001)

        displayio.release_displays()
        i2c = busio.I2C(scl=board.SCL, sda=board.SDA, frequency=400_000 )
        display_bus = displayio.I2CDisplay(i2c, device_address=0x3c )
        self.display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=DW, height=DH, rotation=180)

        maingroup = displayio.Group()
        self.display.root_group = maingroup
        self.text1 = label.Label(terminalio.FONT, text="hello\nworld...", line_spacing=0.75, x=5,y=DH//4)
        self.text2 = label.Label(terminalio.FONT, text="@todbot", line_spacing=0.75, x=DW//2, y=DH-15)
        maingroup.append(self.text1)
        maingroup.append(self.text2)

        self.audio = audiopwmio.PWMAudioOut(board.MOSI)
        self.mixer = audiomixer.Mixer(sample_rate=SAMPLE_RATE, voice_count=1, channel_count=1,
                                     bits_per_sample=16, samples_signed=True,
                                     buffer_size=MIXER_BUFFER_SIZE)
        self.synth = synthio.Synthesizer(sample_rate=SAMPLE_RATE)
        self.audio.play(self.mixer)
        self.mixer.voice[0].level = 0.5 # turn down the volume a bit since this can get loud
        self.mixer.voice[0].play(self.synth)

    def check_key(self):
        if key := self.keys.events.get():
            if key.pressed:
                self.led.fill(0xffffff)
            if key.released:
                self.led.fill(0)


    def check_touch(self, press_func, release_func):
        for i in range(len(self.touches)):
            touch = self.touches[i]
            touch.update()
            if touch.rose:
                press_func(i)
            if touch.fell:
                release_func(i)
