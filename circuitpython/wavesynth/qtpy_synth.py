#
# libraries needed:
#  circup install adafruit_debouncer
#  circup install neopixel
#  circup install adafruit_displayio_ssd1306
#  circup install adafruit_display_text
#
# UI fixme:
# knob "pickup" vs knob "catchup"

from collections import namedtuple
import os
import board, busio
import analogio, keypad
import touchio
from adafruit_debouncer import Debouncer
import neopixel
import audiopwmio, audiomixer
import synthio
import ulab.numpy as np
import displayio, terminalio, vectorio
import adafruit_displayio_ssd1306
from adafruit_display_text import bitmap_label as label

SAMPLE_RATE = 25600   # lets try powers of two
MIXER_BUFFER_SIZE = 4096
DW,DH = 128, 64  # display width/height

# note: we're hanging on to some of the interstitial objects like 'i2c' & 'display_bus'
# even though we shouldn't, because I think the gc will collect it unless we hold on to it

TouchEvent = namedtuple("TouchEvent", "key_number pressed released")

class QTPySynth():
    def __init__(self, patch=None):

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
           # noise protection (wiggle potA causes touch triggers?)
           touchin.threshold = int(touchin.threshold * 1.1)
           self.touchins.append(touchin)
           self.touches.append( Debouncer(touchin) )

        self.midi_uart = busio.UART(rx=board.RX, baudrate=31250, timeout=0.001)

        displayio.release_displays()
        i2c = busio.I2C(scl=board.SCL, sda=board.SDA, frequency=400_000 )
        display_bus = displayio.I2CDisplay(i2c, device_address=0x3c )
        self.display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=DW, height=DH, rotation=180)

        print("QTPySynth:init: patch=",patch)
        self.patch = patch
        self.update_wave_selects()
        self.selected_info = 0 # which part of the display is currently selected

        self.display_setup()
        self.display_update()

        # now do audio setup so we have minimal audible glitches
        self.audio = audiopwmio.PWMAudioOut(board.MOSI)
        self.mixer = audiomixer.Mixer(sample_rate=SAMPLE_RATE, voice_count=1, channel_count=1,
                                     bits_per_sample=16, samples_signed=True,
                                     buffer_size=MIXER_BUFFER_SIZE)
        self.synth = synthio.Synthesizer(sample_rate=SAMPLE_RATE)
        self.audio.play(self.mixer)
        self.mixer.voice[0].level = 0.5 # turn down the volume a bit since this can get loud
        self.mixer.voice[0].play(self.synth)

    def check_key(self):
        return self.keys.events.get()

    def read_pots(self):
        """Read the knobs, filter out their noise """
        filt = 0.5
        avg_cnt = 5
        knobA_vals = [self.knobA] * avg_cnt
        knobB_vals = [self.knobB] * avg_cnt
        for i in range(avg_cnt):
            knobA_vals[i] = self._knobA.value
            knobB_vals[i] = self._knobB.value

        self.knobA = filt * self.knobA + (1-filt)*(sum(knobA_vals)/avg_cnt)  # filter noise
        self.knobB = filt * self.knobB + (1-filt)*(sum(knobB_vals)/avg_cnt)  # filter noise
        return (int(self.knobA), int(self.knobB))

    def check_touch(self):
        """Check the four touch inputs, return keypad-like Events"""
        events = []
        for i in 0,1,2,3:
            touch = self.touches[i]
            touch.update()
            if touch.rose:
                events.append(TouchEvent(i,True, False))
            elif touch.fell:
                events.append(TouchEvent(i,False,True))
        return events

    def check_touch_old(self, press_func, release_func=None, hold_func=None):
        """Check the four touch inputs, calling the press/release/hold callbacks as appropriate """
        for i in 0,1,2,3:
            touch = self.touches[i]
            touch.update()
            if touch.rose:
                press_func(i)
            elif touch.fell:
                if release_func:
                    release_func(i)
            elif touch.value:  # pressed & held
                v = self.touchins[i].raw_value - self.touchins[i].threshold
                if hold_func:
                    hold_func(i, v)

    def display_setup(self):
        disp_group = displayio.Group()
        self.display.root_group = disp_group

        lwave_sel = label.Label(terminalio.FONT, text=self.patch.wave_select(), x=2, y=6)
        lwave_mix = label.Label(terminalio.FONT, text=str(self.patch.wave_mix), x=80, y=6)

        ldetune  = label.Label(terminalio.FONT, text="detun:%.3f" % self.patch.detune, x=2, y=19)
        lwave_lfo= label.Label(terminalio.FONT, text="%.2f:wlfo" % self.patch.wave_mix_lfo_amount, x=75, y=19)

        lfilt_type = label.Label(terminalio.FONT, text="filter:"+self.patch.filt_type, x=2,y=32)
        lfilt_f  = label.Label(terminalio.FONT, text="%4d" % self.patch.filt_f, x=80,y=32)

        lfilt_q  = label.Label(terminalio.FONT, text="filtq:%1.1f" % self.patch.filt_q, x=2,y=45)
        lfilt_env= label.Label(terminalio.FONT, text="0.3:fenv", x=70,y=45)

        self.disp_line1 = displayio.Group()
        for l in (lwave_sel, lwave_mix):
            self.disp_line1.append(l)
        disp_group.append(self.disp_line1)

        self.disp_line2 = displayio.Group()
        for l in (ldetune, lwave_lfo):
            self.disp_line2.append(l)
        disp_group.append(self.disp_line2)

        self.disp_line3 = displayio.Group()
        for l in (lfilt_type, lfilt_f):
            self.disp_line3.append(l)
        disp_group.append(self.disp_line3)

        self.disp_line4 = displayio.Group()
        for l in (lfilt_q, lfilt_env):
            self.disp_line4.append(l)
        disp_group.append(self.disp_line4)

        # selection lines
        pal = displayio.Palette(1)
        pal[0] = 0xffffff
        selectF = vectorio.Rectangle(pixel_shader=pal, width=128, height=1, x=0, y=6 + 8)
        selectW = vectorio.Rectangle(pixel_shader=pal, width=128, height=1, x=0, y=19 + 8)
        selectG = vectorio.Rectangle(pixel_shader=pal, width=128, height=1, x=0, y=32 + 8)
        selectH = vectorio.Rectangle(pixel_shader=pal, width=128, height=1, x=0, y=45 + 8)

        self.disp_selects = displayio.Group()
        for s in (selectF,selectW,selectG, selectH):
            s.hidden=True
            self.disp_selects.append(s)
        disp_group.append(self.disp_selects)

    def display_update(self):
        self.disp_select()
        self.display_update_line1()
        self.display_update_line2()
        #self.display_update_line3()
        #self.display_update_filter()

    def disp_select(self):
        for s in self.disp_selects:
            s.hidden = True
        self.disp_selects[self.selected_info].hidden = False

    def display_update_line1(self):
        wave_select = self.patch.wave_select()
        wave_mix = "%.2f:mix" % self.patch.wave_mix

        if self.disp_line1[0].text != wave_select:
            self.disp_line1[0].text = wave_select
        if self.disp_line1[1].text != wave_mix:
            self.disp_line1[1].text = wave_mix


    def display_update_line2(self):
        detune = "detun:%1.3f" % self.patch.detune
        wave_lfo = "%1.2f:wlfo" % self.patch.wave_mix_lfo_amount

        if self.disp_line2[0].text != detune:
            self.disp_line2[0].text = detune
        if self.disp_line2[1].text != wave_lfo:
            self.disp_line2[1].text = wave_lfo


    def update_wave_selects(self):   # fixme: why isn't this a Patch class method?
        wave_selects = [
            "osc:SAW/TRI",
            "osc:SAW/SQU",
            "osc:SAW/SIN",
            "osc:SQU/SIN"
        ]
        # fixme: check for bad/none dir_path
        for path in os.listdir(self.patch.wave_dir):
            path = path.upper()
            if path.endswith('.WAV') and not path.startswith('.'):
                wave_selects.append("wtb:"+path.replace('.WAV',''))

        self.wave_selects = wave_selects

    def wave_select_pos(self):
        print("wave_select_pos:",self.patch.wave_select())
        return self.wave_selects.index( self.patch.wave_select() ) # fixme: this seems wrong

    def wave_select(self):
        return self.patch.wave_select()
        #return Patch.wave_selects[ self.make_wave_select_pos ]

    def make_wave_select(self):
        """Construct a 'wave_select' string from patch parts"""
        waveB_str = "/"+self.patch.waveB if self.patch.waveB else ""
        waveA_str = self.patch.wave.replace('.WAV','')  # if it's a wavetable
        wave_select = self.patch.wave_type + ":" + waveA_str + waveB_str
        return wave_select

    def set_wave_select(self, wavsel):
        self.patch.wave_type, oscs = wavsel.split(':')
        self.patch.wave, *waveB = oscs.split('/')  # wave contains wavetable filename if wave_type=='wtb'
        self.patch.waveB = waveB[0] if waveB and len(waveB) else None  # can this be shorter?
