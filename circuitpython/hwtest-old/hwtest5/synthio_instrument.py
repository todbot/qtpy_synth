
import time
import synthio
from collections import namedtuple
import ulab.numpy as np

class Waves:
    SINE = 'sine'
    SQUARE = 'square'
    SAW = 'saw'
    TRIANGLE = 'triangle'

    def make_waveform(waveid, size=512, volume=30000):
        if waveid=='sine':
            return Waves.make_sine(size,volume)
        elif waveid=='square':
            return Waves.make_square(size,volume)
        elif waveid=='saw':
            return Waves.make_saw(size,volume)
        elif waveid=='triangle':
            return Waves.make_triangle(size,volume)
        else:
            print("unknown wave type", waveid)

    def make_sine(size, volume):
        return np.array(np.sin(np.linspace(0, 2*np.pi, size, endpoint=False)) * volume, dtype=np.int16)

    def make_square(size, volume):
        return np.concatenate((np.ones(size//2, dtype=np.int16) * volume,
                               np.ones(size//2, dtype=np.int16) * -volume))

    def make_triangle(size, volume):
        return np.concatenate((np.linspace(-volume, volume, num=size//2, dtype=np.int16),
                              np.linspace(volume, -volume, num=size//2, dtype=np.int16)))

    def make_saw(size, volume):
        return Waves.make_ramp_down(size,volume)

    def make_ramp_down(size, volume):
        return np.linspace(volume, -volume, num=size, dtype=np.int16)


class LFOParams:
    """
    """
    def __init__(self, rate=None, scale=None, offset=None, once=False):
        self.rate = rate
        self.scale = scale
        self.offset = offset
        self.once = once

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
    """ Patch is a serializable data structure for the Instrument
    """
    def __init__(self, waveform='saw', detune=1.01, filt_f=4000, filt_q=1.2, filt_env_amount=0.5,
                 filt_env_params=None, amp_env_params=None):
        self.waveform = waveform
        self.detune = detune
        self.filt_f = filt_f
        self.filt_q = filt_q
        #self.filt_env_amount = filt_env_amount
        self.filt_env_params = filt_env_params or EnvParams()
        self.amp_env_params = amp_env_params or EnvParams()


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
    #Voice = namedtuple("Voice", "osc1 osc2 filt_env amp_env")

    """
    This is a two-oscillator per voice subtractive synth patch
    with a low-pass filter w/ filter envelope and an amplitude envelope
    """
    def __init__(self, synth, patch):
        super().__init__(synth)
        self.load_patch(patch)

    def load_patch(self, patch):
        self.patch = patch
        self.waveform = Waves.make_waveform( patch.waveform )
        self.filt_env_wave = Waves.make_triangle(size=16, volume=32676)

    # oh wait, this would make it paraphonic
    # we need filter envelope per note (not per voice tho)
    def update(self):
        for (osc1,osc2,filt_env,amp_env) in self.voices.values():
            # prevent filter instability around note frequency
            # must do this for each voice
            filt_q = self.patch.filt_q
            if self.patch.filt_f / osc1.frequency < 1.2:
                filt_q = filt_q / 2
            #filt_f = max(self.patch.filt_f * filt_env.value, osc1.frequency*0.75) # filter unstable <oscfreq?
            #filt_f = max(self.patch.filt_f * filt_env.value, 0) # filter unstable <100?
            filt_mod = 0
            if self.patch.filt_env_params.attack_time>0:
                filt_mod = max(0, 0.5 * 8000 * (filt_env.value/2))  # 8k/2 = max freq, 0.5 = filtermod amt
            filt_f = self.patch.filt_f + filt_mod
            print("%.1f %.1f %.1f %.1f" % (osc1.frequency, filt_f, self.patch.filt_f, filt_q))
            filt = self.synth.low_pass_filter( filt_f,filt_q )
            osc1.filter = filt
            osc2.filter = filt

    def note_on(self, midi_note, midi_vel=127):
        amp_env = self.patch.amp_env_params.make_env()

        #filt_env = self.patch.filt_env_params.make_env()  # synthio.Envelope.value does not exist
        filt_env = synthio.LFO(once=True, scale=0.9, offset=1.01,
                               waveform=self.filt_env_wave,
                               rate=self.patch.filt_env_params.attack_time, ) # always positve

        f = synthio.midi_to_hz(midi_note)
        osc1 = synthio.Note( frequency=f, waveform=self.waveform, envelope=amp_env )
        osc2 = synthio.Note( frequency=f * self.patch.detune, waveform=self.waveform, envelope=amp_env )
        #voice = PolyTwoOsc.Voice(osc1, osc2, filt_env, amp_env)

        self.voices[midi_note] = (osc1, osc2, filt_env, amp_env)
        self.synth.press( (osc1,osc2) )
        self.synth.blocks.append(filt_env) # not tracked automaticallly by synthio
        #print("filt_env_param:", self.patch.filt_env_params)

    def note_off(self, midi_note, midi_vel=0):
        (osc1,osc2,filt_env,amp_env) = self.voices.get(midi_note, None)
        if osc1:
            self.synth.release( (osc1,osc2) )
            self.voices.pop(midi_note)  # FIXME: let filter run on release, check amp_env?

    def adjust_filter(filt_f, filt_q):
        self.filt_f = filt_f
        self.filt_q = filt_q
