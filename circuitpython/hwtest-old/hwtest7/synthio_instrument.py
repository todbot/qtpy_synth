
import time
import synthio
from collections import namedtuple
import ulab.numpy as np
try:
    import adafruit_wave
except:
    print("synthio_instrment: no WAV import available")

# mix between values a and b, works with numpy arrays too,  t ranges 0-1
def lerp(a, b, t):  return (1-t)*a + t*b


class Waves:
    """
    Generate waveforms for either oscillator or LFO use
    """

    def make_waveform(waveid, size=512, volume=30000):
        if waveid=='sine':
            return Waves.sine(size,volume)
        elif waveid=='square':
            return Waves.square(size,volume)
        elif waveid=='saw':
            return Waves.saw(size,volume)
        elif waveid=='triangle':
            return Waves.triangle(size, -volume, volume)
        elif waveid=='silence':
            return Waves.silence(size)
        elif waveid=='noise':
            return Waves.noise(size,volume)
        else:
            print("unknown wave type", waveid)

    def sine(size, volume):
        return np.array(np.sin(np.linspace(0, 2*np.pi, size, endpoint=False)) * volume, dtype=np.int16)

    def square(size, volume):
        return np.concatenate((np.ones(size//2, dtype=np.int16) * volume,
                               np.ones(size//2, dtype=np.int16) * -volume))

    def triangle(size, min_vol, max_vol):
        return np.concatenate((np.linspace(min_vol, max_vol, num=size//2, dtype=np.int16),
                               np.linspace(max_vol, min_vol, num=size//2, dtype=np.int16)))

    def saw(size, volume):
        return Waves.saw_down(size,volume)

    def saw_down(size, volume):
        return np.linspace(volume, -volume, num=size, dtype=np.int16)

    def saw_up(size, volume):
        return np.linspace(-volume, volume, num=size, dtype=np.int16)

    def silence(size):
        return np.zeros(size, dtype=np.int16)

    def noise(size,volume):
        pass

    def from_list( vals ):
        print("vals=",vals)
        return np.array( [int(v) for v in vals], dtype=np.int16 )

    def lfo_ramp_up_pos():
        return np.array( (0,32767), dtype=np.int16)

    def lfo_ramp_down_pos():
        return np.array( (32767,0), dtype=np.int16)

    def lfo_triangle_pos():
        return np.array( (0, 32767, 0), dtype=np.int16)

    def lfo_triangle():
        return np.array( (0, 32767, 0, -32767), dtype=np.int16)

    def wav(filepath, size=256, pos=0):
        with adafruit_wave.open(filepath) as w:
            if w.getsampwidth() != 2 or w.getnchannels() != 1:
                raise ValueError("unsupported format")
            #n = w.getnframes() if size==0 else size
            n = size
            w.setpos(pos)
            return np.frombuffer(w.readframes(n), dtype=np.int16)

    def wav_info(filepath):
        with adafruit_wave.open(filepath) as w:
            return (w.getnframes(), w.getnchannels(), w.getsampwidth())


class Wavetable:
    """
    A 'waveform' for synthio.Note that uses a wavetable with a scannable
    wave position. A wavetable is a collection of harmonically-related
    single-cycle waveforms. Often the waveforms are 256 samples long and
    the wavetable containing 64 waves. The wavetable oscillator lets the
    user pick which of those 64 waves to use, usually allowing one to mix
    between two waves.

    Some example wavetables usable by this classs: https://waveeditonline.com/

    In this implementation, you select a wave position (wave_pos) that can be
    fractional, and the fractional part allows for mixing of the waves
    at wave_pos and wave_pos+1.
    """

    def __init__(self, filepath, size=256, in_memory=False):
        self.filepath = filepath
        """Sample size of each wave in the table"""
        self.size = size
        self.w = adafruit_wave.open(filepath)
        if self.w.getsampwidth() != 2 or self.w.getnchannels() != 1:
            raise ValueError("unsupported WAV format")
        self.wav = None
        if in_memory:  # load entire WAV into RAM
            self.wav = np.frombuffer(self.w.readframes(self.w.getnframes()), dtype=np.int16)
        self.samp_posA = -1

        """How many waves in this wavetable"""
        self.num_waves = self.w.getnframes() / self.size
        """ The waveform to be used by synthio.Note """
        self.waveform = Waves.silence(size) # makes a buffer for us to lerp into
        self.set_wave_pos(0)

    def set_wave_pos(self,wave_pos):
        """
        wave_pos integer part of specifies which wave from 0-num_waves,
        and fractional part specifies mix between wave and wave next to it
        (e.g. wave_pos=15.66 chooses 1/3 of waveform 15 and 2/3 of waveform 16)
        """
        wave_pos = min(max(wave_pos, 0), self.num_waves-1)  # constrain
        self.wave_pos = wave_pos

        samp_posA = int(wave_pos) * self.size
        samp_posB = int(wave_pos+1) * self.size
        print("samp_posA", samp_posA, self.samp_posA, wave_pos)
        if samp_posA != self.samp_posA:  # avoid needless computation
            if self.wav:  # if we've loaded the entire wavetable into RAM
                waveformA = self.wav[samp_posA : samp_posA + self.size] # slice
                waveformB = self.wav[samp_posB : samp_posB + self.size]
            else:
                self.w.setpos(samp_posA)
                waveformA = np.frombuffer(self.w.readframes(self.size), dtype=np.int16)
                self.w.setpos(samp_posB)
                waveformB = np.frombuffer(self.w.readframes(self.size), dtype=np.int16)

            self.samp_posA = samp_posA  # save
            self.waveformA = waveformA
            self.waveformB = waveformB

        # fractional position between a wave A & B
        wave_pos_frac = wave_pos - int(wave_pos)
        # mix waveforms A & B and copy result into waveform used by synthio
        self.waveform[:] = lerp(self.waveformA, self.waveformB, wave_pos_frac)

    def deinit(self):
        self.w.close()


class LFOParams:
    """
    """
    def __init__(self, rate=None, scale=None, offset=None, once=False, waveform=None):
        self.rate = rate
        self.scale = scale
        self.offset = offset
        self.once = once
        self.waveform = waveform

    def make_lfo(self):
        return synthio.LFO(rate=self.rate, once=self.once,
                           scale=self.scale, offset=self.offset,
                           waveform=self.waveform)

class EnvParams():
    """
    """
    def __init__(self, attack_time=0.1, decay_time=0.01, release_time=0.2, attack_level=1, sustain_level=1):
        self.attack_time = attack_time
        self.decay_time = decay_time
        self.release_time = release_time
        self.attack_level = attack_level
        self.sustain_level = sustain_level

    def make_env(self):
        return synthio.Envelope(attack_time = self.attack_time,
                                decay_time = self.decay_time,
                                release_time = self.release_time,
                                attack_level = self.attack_level,
                                sustain_level = self.sustain_level)


class Patch:
    """ Patch is a serializable data structure for the Instrument's settings
    FIXME: patches should have names too, tod
    """
    def __init__(self, wave_type='osc', wave='saw', detune=1.01,
                 filt_type='lp', filt_f=8000, filt_q=1.2, filt_env_amount=0.5,
                 filt_env_params=None, amp_env_params=None):
        self.wave_type = 'osc'  # or 'osc' or 'wav' or 'wtb'
        self.wave = wave
        self.waveB = None
        self.wave_mix = 0.0  # 0 = wave, 1 = waveB
        self.wave_mix_lfo_amount = 3
        self.detune = detune
        self.filt_type = filt_type   # allowed values: 'lp', 'bp', or 'hp'
        self.filt_f = filt_f
        self.filt_q = filt_q
        #self.filt_env_amount = filt_env_amount
        self.filt_env_params = filt_env_params or EnvParams()
        self.amp_env_params = amp_env_params or EnvParams()

    def __repr__(self):
        print("patch", self.wave_type)


# not to be instantiated just an example
class Instrument():

    def __init__(self, synth, patch=Patch()):
        self.synth = synth
        self.patch = patch
        self.voices = {}  # keys = midi note, vals = oscs

    def update(self):
        for v in self.voices:
            print("note:",v)

    def note_on(self, midi_note, midi_vel=127):
        # FIXME: deal with multiple note_ons of same note
        f = synthio.midi_to_hz(midi_note)
        amp_env = self.patch.amp_env_params.make_env()
        voice = synthio.Note( frequency=f, envelope=amp_env )
        self.voices[midi_note] = voice
        self.synth.press( voice )

    def note_off(self, midi_note, midi_vel=0):
        voice = self.voices.get(midi_note, None)
        if voice:
            self.synth.release(voice)
            self.voices.pop(midi_note)  # FIXME: need to run filter after release cycle


class PolyTwoOsc(Instrument):
    #Voice = namedtuple("Voice", "osc1 osc2 filt_env amp_env")   # idea:
    """
    This is a two-oscillator per voice subtractive synth patch
    with a low-pass filter w/ filter envelope and an amplitude envelope
    """
    def __init__(self, synth, patch):
        super().__init__(synth)
        self.load_patch(patch)

    def load_patch(self, patch):
        print("load patch", patch)
        self.patch = patch

        if patch.wave_type == 'osc':
            self.waveform = Waves.make_waveform('silence')  # our working buffer, overwritten w/ wavemix
            self.waveformA = Waves.make_waveform( patch.wave )
            self.waveformB = None
            if patch.waveB:
                self.waveformB = Waves.make_waveform( patch.waveB )
            else:
                self.waveform = self.waveformA

        elif patch.wave_type == 'wtb':
            self.wavetable = Wavetable(patch.wave)
            self.waveform = self.wavetable.waveform
            raw_lfo1 = synthio.LFO(rate = 0.3) #, scale=0.5, offset=0.5)
            lfo1 = synthio.Math( synthio.MathOperation.SCALE_OFFSET, raw_lfo1, 0.5, 0.5) # unipolar
            self.wave_lfo = lfo1
            self.synth.blocks.append(lfo1)  # global lfo for wave_lfo

        self.filt_env_wave = Waves.lfo_triangle()

    def update(self):
        for (osc1,osc2,filt_env,amp_env) in self.voices.values():

            # let Wavetable do the work  # FIXME: don't need to do this per osc1 yeah?
            if self.patch.wave_type == 'wtb':
                wave_pos = self.wave_lfo.value * self.patch.wave_mix_lfo_amount
                wave_pos += self.patch.wave_mix * self.wavetable.num_waves
                self.wavetable.set_wave_pos( wave_pos )

            # else simple osc wave mixing
            else:
                if self.waveformB:
                    osc1.waveform[:] = lerp(self.waveformA, self.waveformB, self.patch.wave_mix)
                    if self.patch.detune:
                        osc2.waveform[:] = lerp(self.waveformA, self.waveformB, self.patch.wave_mix)

            filt_q = self.patch.filt_q
            filt_mod = 0
            filt_f = 0
            filt = None

            # prevent filter instability around note frequency
            # must do this for each voice
            #if self.patch.filt_f / osc1.frequency < 1.2:
            #    filt_q = filt_q / 2

            #filt_f = max(self.patch.filt_f * filt_env.value, osc1.frequency*0.75) # filter unstable <oscfreq?
            #filt_f = max(self.patch.filt_f * filt_env.value, 0) # filter unstable <100?

            if self.patch.filt_type == 'lp':
                if self.patch.filt_env_params.attack_time > 0:
                    filt_mod = max(0, 0.5 * 8000 * (filt_env.value/2))  # 8k/2 = max freq, 0.5 = filtermod amt
                    filt_f = self.patch.filt_f + filt_mod
                    filt = self.synth.low_pass_filter( filt_f,filt_q )

            elif self.patch.filt_type == 'hp':
                    filt_mod = max(0, 0.5 * 8000 * (filt_env.value/2))  # 8k/2 = max freq, 0.5 = filtermod amt
                    filt_f = self.patch.filt_f + filt_mod
                    filt = self.synth.high_pass_filter( filt_f,filt_q )

            elif self.patch.filt_type == 'bp':
                    filt_mod = max(0, 0.5 * 8000 * (filt_env.value/2))  # 8k/2 = max freq, 0.5 = filtermod amt
                    filt_f = self.patch.filt_f + filt_mod
                    filt = self.synth.band_pass_filter( filt_f,filt_q )

            #print("%s: %.1f %.1f %.1f %.1f"%(self.patch.filt_type,osc1.frequency,filt_f,self.patch.filt_f,filt_q))
            osc1.filter = filt
            if self.patch.detune:
                osc2.filter = filt

    def note_on(self, midi_note, midi_vel=127):
        amp_env = self.patch.amp_env_params.make_env()

        #filt_env = self.patch.filt_env_params.make_env()  # synthio.Envelope.value does not exist
        # fake an envelope with an LFO in 'once' mode
        filt_env = synthio.LFO(once=True, scale=0.9, offset=1.01,
                               waveform=self.filt_env_wave,
                               rate=self.patch.filt_env_params.attack_time, ) # always positve

        f = synthio.midi_to_hz(midi_note)
        osc1 = synthio.Note( frequency=f, waveform=self.waveform, envelope=amp_env )
        osc2 = synthio.Note( frequency=f * self.patch.detune, waveform=self.waveform, envelope=amp_env )

        self.voices[midi_note] = (osc1, osc2, filt_env, amp_env)
        self.synth.press( (osc1,osc2) )
        self.synth.blocks.append(filt_env) # not tracked automaticallly by synthio

    def note_off(self, midi_note, midi_vel=0):
        (osc1,osc2,filt_env,amp_env) = self.voices.get(midi_note, None)
        if osc1:
            self.synth.release( (osc1,osc2) )
            self.voices.pop(midi_note)  # FIXME: let filter run on release, check amp_env?
            self.synth.blocks.remove(filt_env)  # FIXME: figure out how to release after note is done
        print(self.synth.blocks)

    def redetune(self):
        for (osc1,osc2,filt_env,amp_env) in self.voices.values():
            osc2.frequency = osc1.frequency * self.patch.detune

    def adjust_filter(filt_f, filt_q):
        self.filt_f = filt_f
        self.filt_q = filt_q
