# UI fixme:
# knob "pickup" vs knob "catchup"

import board, busio
import analogio, keypad
import touchio
from adafruit_debouncer import Debouncer # circup install adafruit_debouncer
import neopixel  # circup install neopixel
import audiopwmio, audiomixer
import synthio
import ulab.numpy as np
import displayio, terminalio, vectorio
import adafruit_displayio_ssd1306  # circup install adafruit_displayio_ssd1306
from adafruit_display_text import bitmap_label as label
from adafruit_display_shapes.rect import Rect

#import adafruit_midi
#from adafruit_midi.note_on import NoteOn
#from adafruit_midi.note_off import NoteOff

SAMPLE_RATE = 25600
MIXER_BUFFER_SIZE = 4096
DW,DH = 128, 64  # display width/height

# note: we're hanging on to some of the interstitial objects like 'i2c' & 'display_bus'
# even though we shouldn't, because I think the gc will collect it unless we hold on to it

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

        self.patch = patch
        self.selected_disp = 0 # which part of the display is currently selected

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

    def check_key(self, press_func, release_func=None):
        if key := self.keys.events.get():
            if key.pressed:
                press_func()
            if key.released and release_func:
                release_func()

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
        return (self.knobA, self.knobB)


    def check_touch(self, press_func, release_func=None, hold_func=None):
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

        lfilt_type = label.Label(terminalio.FONT, text=self.patch.filt_type, x=5,y=6)
        lfilt_f  = label.Label(terminalio.FONT, text=str(self.patch.filt_f), x=30,y=6, scale=1)
        lfilt_q  = label.Label(terminalio.FONT, text=str(self.patch.filt_q), x=90,y=6, scale=1)

        lwavetype = label.Label(terminalio.FONT, text=self.patch.wave_type, x=5,y=25)
        lwaveA = label.Label(terminalio.FONT, text=str(self.patch.wave), x=30,y=20)
        lwaveB  = label.Label(terminalio.FONT, text=str(self.patch.waveB), x=30,y=30, scale=1)
        lwave_mix  = label.Label(terminalio.FONT, text=str(self.patch.wave_mix), x=60,y=25, scale=1)
        ldetune  = label.Label(terminalio.FONT, text=str(self.patch.wave_mix), x=95,y=25, scale=1)

        self.disp_filt_info = displayio.Group()
        for l in (lfilt_type, lfilt_f, lfilt_q):
            self.disp_filt_info.append(l)
        disp_group.append(self.disp_filt_info)

        self.disp_wave_info = displayio.Group()
        for l in (lwavetype, lwaveA, lwaveB, lwave_mix, ldetune):
            self.disp_wave_info.append(l)
        disp_group.append(self.disp_wave_info)

        pal = displayio.Palette(1)
        pal[0] = 0xffffff
        selectF = vectorio.Rectangle(pixel_shader=pal, width=128, height=1, x=0, y=15)
        selectW = vectorio.Rectangle(pixel_shader=pal, width=128, height=1, x=0, y=37)
        selectG = vectorio.Rectangle(pixel_shader=pal, width=128, height=1, x=0, y=50)
        selectH = vectorio.Rectangle(pixel_shader=pal, width=128, height=1, x=0, y=63)

        #selectF = Rect(0, 0, 128, 14, fill=None, outline=0xffffff)
        #selectW = Rect(0,15, 128, 21, fill=None, outline=0xffffff)
        #selectG = Rect(0,37, 128, 14, fill=None, outline=0xffffff)
        #selectH = Rect(0,50, 128, 14, fill=None, outline=0xffffff)

        self.disp_selects = displayio.Group()
        for s in (selectF,selectW,selectG, selectH):
            s.hidden=True
            self.disp_selects.append(s)
        disp_group.append(self.disp_selects)

    def display_update(self):
        self.disp_select()
        self.display_update_filter()
        self.display_update_wave()

    def disp_select(self):
        for s in self.disp_selects:
            s.hidden = True
        self.disp_selects[self.selected_disp].hidden = False

    def display_update_wave(self):
        wavtype = '%3.3s' % self.patch.wave_type
        wavA = '%3.3s' % self.patch.wave
        wavB = '%3.3s' % self.patch.waveB
        wavmix = "%.2f" % self.patch.wave_mix
        detune = "%.3f" % (self.patch.detune-1)
        # only update if needed
        if self.disp_wave_info[0].text != wavtype:
            self.disp_wave_info[0].text = wavtype
        if self.disp_wave_info[1].text != wavA:
            self.disp_wave_info[1].text = wavA
        if self.disp_wave_info[2].text != wavB:
            self.disp_wave_info[2].text = wavB
        if self.disp_wave_info[3].text !=wavmix:
            self.disp_wave_info[3].text = wavmix
        if self.disp_wave_info[4].text != detune:
            self.disp_wave_info[4].text = detune

    def display_update_filter(self):
        f_str = "%4d" % self.patch.filt_f
        q_str = "%1.1f" % self.patch.filt_q

        if self.patch.filt_type != self.disp_filt_info[0].text:
            self.disp_filt_info[0].text = self.patch.filt_type

        if f_str != self.disp_filt_info[1].text:
            self.disp_filt_info[1].text = f_str

        if q_str != self.disp_filt_info[2].text:
            self.disp_filt_info[2].text = q_str
            #print("edit q", q_str)
