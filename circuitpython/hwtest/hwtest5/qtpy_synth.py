
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
#import adafruit_midi
#from adafruit_midi.note_on import NoteOn
#from adafruit_midi.note_off import NoteOff

SAMPLE_RATE = 28_000
MIXER_BUFFER_SIZE = 4096
DW,DH = 128, 64  # display width/height

# note: we're hanging on to some of the interstitial objects like 'i2c' & 'display_bus'
# even though we shouldn't, because I think the gc will collect it unless we hold on to it

class QTPySynthConfig():
    def __init__(self):
        self.filter_f = 2000
        self.filter_q = 1.2
        self.filter_type = 'lpf'


class QTPySynth():
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
           self.touchins.append(touchin)
           self.touches.append( Debouncer(touchin) )

        self.midi_uart = busio.UART(rx=board.RX, baudrate=31250, timeout=0.001)

        displayio.release_displays()
        i2c = busio.I2C(scl=board.SCL, sda=board.SDA, frequency=400_000 )
        display_bus = displayio.I2CDisplay(i2c, device_address=0x3c )
        self.display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=DW, height=DH, rotation=180)

        self.audio = audiopwmio.PWMAudioOut(board.MOSI)
        self.mixer = audiomixer.Mixer(sample_rate=SAMPLE_RATE, voice_count=1, channel_count=1,
                                     bits_per_sample=16, samples_signed=True,
                                     buffer_size=MIXER_BUFFER_SIZE)
        self.synth = synthio.Synthesizer(sample_rate=SAMPLE_RATE)
        self.audio.play(self.mixer)
        self.mixer.voice[0].level = 0.5 # turn down the volume a bit since this can get loud
        self.mixer.voice[0].play(self.synth)

        self.cfg = QTPySynthConfig()

    def check_key(self):
        if key := self.keys.events.get():
            if key.pressed:
                self.led.fill(0xffffff)
            if key.released:
                self.led.fill(0)

    def read_pots(self):
        filt = 0.5
        avg_cnt = 10
        knobA_vals = [self.knobA] * avg_cnt
        knobB_vals = [self.knobB] * avg_cnt
        for i in range(avg_cnt):
            knobA_vals[i] = self._knobA.value
            knobB_vals[i] = self._knobB.value

        self.knobA = filt * self.knobA + (1-filt)*(sum(knobA_vals)/avg_cnt)  # filter noise
        self.knobB = filt * self.knobB + (1-filt)*(sum(knobB_vals)/avg_cnt)  # filter noise
        return (self.knobA, self.knobB)

    def check_touch(self, press_func, release_func=None, hold_func=None):
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

    def make_filter(self, cfg=None):
        if not cfg: cfg = self.cfg
        if cfg.filter_type == 'lpf':
            filter = self.synth.low_pass_filter(cfg.filter_f, cfg.filter_q)
        else:
            print("unknown filter type", self.filter_type)
        return filter

    def update_filter(self, filter_type, filter_f, filter_q):
        self.cfg.filter_type = filter_type
        self.cfg.filter_f = filter_f
        self.cfg.filter_q = filter_q


    def display_setup(self):
        disp_group = displayio.Group()
        self.display.root_group = disp_group

        lfilt_type = label.Label(terminalio.FONT, text=self.cfg.filter_type, x=5,y=5)
        lfreq_val  = label.Label(terminalio.FONT, text=str(self.cfg.filter_f), x=30,y=5)
        lfreq_q  = label.Label(terminalio.FONT, text=str(self.cfg.filter_q), x=60,y=5)

        self.disp_filter_info = displayio.Group()
        for l in (lfilt_type, lfreq_val, lfreq_q):
            self.disp_filter_info.append(l)
        disp_group.append(self.disp_filter_info)

    def display_update(self):
        self.display_update_filter()

    def display_update_filter(self):
        f_str = "%4d" % self.cfg.filter_f
        q_str = "%1.1f" % self.cfg.filter_q

        if self.cfg.filter_type != self.disp_filter_info[0].text:
            self.disp_filter_info[0].text = self.cfg.filter_type

        if f_str != self.disp_filter_info[1].text:
            self.disp_filter_info[1].text = f_str

        if q_str != self.disp_filter_info[2].text:
            self.disp_filter_info[2].text = q_str
            print("edit q", q_str)
