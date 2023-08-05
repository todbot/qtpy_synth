# qtpy_synth.py -- hardware defines and setup for qtpy_synth board
# 22 Jul 2023 - @todbot / Tod Kurt
# part of https://github.com/todbot/qtpy_synth
#
# libraries needed:
#  circup install neopixel, adafruit_debouncer, adafruit_displayio_ssd1306
#
# UI fixme:
# knob "pickup" vs knob "catchup"  (maybe done in app instead)

import board, busio
import analogio, keypad
import touchio
from adafruit_debouncer import Debouncer
import neopixel
import audiopwmio, audiomixer
import synthio
import displayio
import adafruit_displayio_ssd1306

SAMPLE_RATE = 25600   # lets try powers of two
MIXER_BUFFER_SIZE = 4096
DW,DH = 128, 64  # display width/height

# note: we're hanging on to some of the interstitial objects like 'i2c' & 'display_bus'
# even though we shouldn't, because I think the gc will collect it unless we hold on to it

class QTPySynthHardware():
    def __init__(self):

        self.led = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.1)
        self.keys = keypad.Keys( pins=(board.TX,),  value_when_pressed=False )
        self._knobA = analogio.AnalogIn(board.A0)
        self._knobB = analogio.AnalogIn(board.A1)
        self.knobA = self._knobA.value
        self.knobB = self._knobB.value

        self.touchins = []  # for raw_value
        self.touches = []   # for debouncer
        for pin in (board.A3, board.A2, board.MISO, board.SCK):
           touchin = touchio.TouchIn(pin)
           # touchin.threshold = int(touchin.threshold * 1.1) # noise protection
           self.touchins.append(touchin)
           self.touches.append( Debouncer(touchin) )

        self.midi_uart = busio.UART(rx=board.RX, baudrate=31250, timeout=0.001)

        displayio.release_displays()
        i2c = busio.I2C(scl=board.SCL, sda=board.SDA, frequency=400_000 )
        display_bus = displayio.I2CDisplay(i2c, device_address=0x3c )
        self.display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=DW, height=DH, rotation=180)

        # now do audio setup so we have minimal audible glitches
        self.audio = audiopwmio.PWMAudioOut(board.MOSI)
        self.mixer = audiomixer.Mixer(sample_rate=SAMPLE_RATE, voice_count=1, channel_count=1,
                                     bits_per_sample=16, samples_signed=True,
                                     buffer_size=MIXER_BUFFER_SIZE)
        self.synth = synthio.Synthesizer(sample_rate=SAMPLE_RATE)
        self.audio.play(self.mixer)
        self.mixer.voice[0].play(self.synth)

    def check_key(self):
        return self.keys.events.get()

    def read_pots(self):
        """Read the knobs, filter out their noise """
        filt = 0.5

        # avg_cnt = 5
        # knobA_vals = [self.knobA] * avg_cnt
        # knobB_vals = [self.knobB] * avg_cnt
        # for i in range(avg_cnt):
        #     knobA_vals[i] = self._knobA.value
        #     knobB_vals[i] = self._knobB.value

        # self.knobA = filt * self.knobA + (1-filt)*(sum(knobA_vals)/avg_cnt)  # filter noise
        # self.knobB = filt * self.knobB + (1-filt)*(sum(knobB_vals)/avg_cnt)  # filter noise

        self.knobA = filt * self.knobA + (1-filt)*(self._knobA.value)  # filter noise
        self.knobB = filt * self.knobB + (1-filt)*(self._knobB.value)  # filter noise
        return (int(self.knobA), int(self.knobB))

    def check_touch(self):
        """Check the four touch inputs, return keypad-like Events"""
        events = []
        for i in 0,1,2,3:
            touch = self.touches[i]
            touch.update()
            if touch.rose:
                events.append(keypad.Event(i,True))
            elif touch.fell:
                events.append(keypad.Event(i,False))
        return events

    def check_touch_hold(self, hold_func):
        for i in 0,1,2,3:
            if self.touches[i].value:  # pressed
                v = self.touchins[i].raw_value - self.touchins[i].threshold
                hold_func(i, v)
