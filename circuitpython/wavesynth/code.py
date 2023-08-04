# wavesynth_code.py -- wavesynth for qtpy_synth
# 28 Jul 2023 - @todbot / Tod Kurt
# part of https://github.com/todbot/qtpy_synth
#
#  UI:
#  - Display shows four lines of two parameters each
#  - The current editable parameter pair is underlined, adjustable by the knobs
#  - The knobs have "catchup" logic  (
#       (knob must pass through the displayed value before value can be changed)
#
#  - Key tap (press & release) == change what editable line (what knobs are editing)
#  - Key hold + touch press = load patch 1,2,3,4  (turned off currently)
#  - Touch press/release == play note / release note
#

import asyncio
import time
import usb_midi
import adafruit_midi
from adafruit_midi.note_on import NoteOn
from adafruit_midi.note_off import NoteOff
from adafruit_midi.control_change import ControlChange

from qtpy_synth import QTPySynthHardware
from wavesynth_display import WavesynthDisplay
from synthio_instrument import WavePolyTwoOsc, Patch, FiltType

touch_midi_notes = [40, 48, 52, 55] # can be float

patch1 = Patch('oneuno')
patch2 = Patch('twotoo')
patch3 = Patch('three')
patch4 = Patch('fourfor')
patches = (patch1, patch2, patch3, patch4)

patch1.filt_env_params.attack_time = 0.5
patch1.amp_env_params.attack_time = 0.01

patch2.filt_type = FiltType.HP
patch2.wave = 'square'
patch2.detune=1.01
patch2.filt_env_params.attack_time = 0.0 # turn off filter  FIXME
patch2.amp_env_params.release_time = 1.0

patch3.waveformB = 'square'  # show off wavemixing
patch3.filt_type = FiltType.BP

patch4.wave_type = 'wtb'
patch4.wave = 'PLAITS02'  # 'MICROW02' 'BRAIDS04'
patch4.wave_mix_lfo_amount = 0.23
#patch4.detune = 0  # disable 2nd oscillator
patch4.amp_env_params.release_time = 0.5

print("--- qtpy_synth wavesynth starting up ---")

qts = QTPySynthHardware()
inst = WavePolyTwoOsc(qts.synth, patch4)
wavedisp = WavesynthDisplay(qts.display, inst.patch)

midi_usb = adafruit_midi.MIDI(midi_in=usb_midi.ports[0], in_channel=0 )
midi_uart = adafruit_midi.MIDI(midi_in=qts.midi_uart, in_channel=0 )

def map_range(s, a1, a2, b1, b2):  return  b1 + ((s - a1) * (b2 - b1) / (a2 - a1))


async def instrument_updater():
    while True:
        inst.update()
        await asyncio.sleep(0.01)  # as fast as possible

async def display_updater():
    while True:
        wavedisp.display_update()
        await asyncio.sleep(0.1)

async def midi_handler():
    while True:
        # MIDI input
        while msg := midi_usb.receive() or midi_uart.receive():
            if isinstance(msg, NoteOn) and msg.velocity != 0:
                inst.note_on(msg.note)
                qts.led.fill(0xff00ff)
            elif isinstance(msg,NoteOff) or isinstance(msg,NoteOn) and msg.velocity==0:
                inst.note_off(msg.note)
                qts.led.fill(0x000000)
            elif isinstance(msg,ControlChange):
                print("CC:",msg.control, msg.value)
                if msg.control == 71:  # "sound controller 1"
                    inst.patch.wave_mix = msg.value/127
                elif msg.control == 1: # mod wheel
                    inst.patch.wave_mix_lfo_amount = msg.value/127 * 50
                    #inst.patch.wave_mix_lfo_rate = msg.value/127 * 5
                elif msg.control == 74: # filter cutoff
                    inst.patch.filt_f = msg.value/127 * 8000

        await asyncio.sleep(0.001)

async def input_handler():

    # fixme: put these in qtpy_synth.py? no I think they are part of this "app"
    knob_mode = 0  # 0=frequency, 1=wavemix, 2=, 3=
    key_held = False
    key_with_touch = False
    knob_saves = [ (0,0) for _ in range(4) ]  # list of knob state pairs
    param_saves = [ (0,0) for _ in range(4) ]  # list of param state pairs for knobs
    knobA_pickup, knobB_pickup = False, False
    knobA, knobB = 0,0

    def reload_patch(wave_select):
        print("reload patch!", wave_select)
        # the below seems like the wrong way to do this, needlessly complex
        inst.patch.set_by_wave_select( wave_select )
        inst.reload_patch()
        param_saves[0] = wavedisp.wave_select_pos(), inst.patch.wave_mix
        param_saves[1] = inst.patch.detune, inst.patch.wave_mix_lfo_amount
        param_saves[2] = inst.patch.filt_type, inst.patch.filt_f
        param_saves[3] = inst.patch.filt_q, inst.patch.filt_env_params.attack_time

    while True:
        # KNOB input
        (knobA_new, knobB_new) = qts.read_pots()

        # simple knob pickup logic: if the real knob is close enough to
        if abs(knobA - knobA_new) <= 1000:  # knobs range 0-65535
            knobA_pickup = True
        if abs(knobB - knobB_new) <= 1000:
            knobB_pickup = True

        if knobA_pickup:
            knobA = knobA_new
        if knobB_pickup:
            knobB = knobB_new

        # TOUCH input
        if touches := qts.check_touch():
            for touch in touches:

                if touch.pressed:
                    if key_held:  # load a patch
                        print("load patch", touch.key_number)
                        # disable this for now
                        #inst.load_patch(patches[i])
                        #qts.patch = patches[i]
                        wavedisp.display_update()
                        key_with_touch = True
                    else:  # trigger a note
                        qts.led.fill(0xff00ff)
                        midi_note = touch_midi_notes[touch.key_number]
                        inst.note_on(midi_note)

                if touch.released:
                    if key_with_touch:
                        key_with_touch = False
                    else:
                        qts.led.fill(0)
                        midi_note = touch_midi_notes[touch.key_number]
                        inst.note_off(midi_note)

        # KEY input
        if key := qts.check_key():
            if key.pressed:
                key_held = True
            if key.released:
                key_held = False
                if not key_with_touch:  # key tap == change what knobs do
                    # turn off pickup mode since we change what knobs do
                    knobA_pickup, knobB_pickup = False, False
                    knob_saves[knob_mode] = knobA, knobB  # save knob positions
                    knob_mode = (knob_mode + 1) % 4  # FIXME: make a max_knob_mode
                    knobA, knobB = knob_saves[knob_mode] # retrive saved knob positions
                    print("knob mode:",knob_mode, knobA, knobB)
                    wavedisp.selected_info = knob_mode  # FIXME

        # Handle parameter changes depending on knob mode
        if knob_mode == 0:  # wave selection & wave_mix

            wave_select_pos, wave_mix = param_saves[knob_mode]

            if knobA_pickup:
                wave_select_pos = map_range( knobA, 0,65535, 0, len(wavedisp.wave_selects)-1)
            if knobB_pickup:
                wave_mix = map_range( knobB, 0,65535, 0, 1)

            param_saves[knob_mode] = wave_select_pos, wave_mix

            wave_select = wavedisp.wave_selects[ int(wave_select_pos) ]

            if inst.patch.wave_select() != wave_select:
                reload_patch(wave_select)

            inst.patch.wave_mix = wave_mix

        elif knob_mode == 1:  # osc detune & wave_mix lfo

            detune, wave_lfo = param_saves[knob_mode]

            if knobA_pickup:
                detune  = map_range(knobA, 300,65300, 1, 1.1)  # RP2040 has bad ADC
            if knobB_pickup:
                wave_lfo = map_range(knobB, 0,65535, 0, 1)

            param_saves[knob_mode] = detune, wave_lfo

            inst.patch.wave_mix_lfo_amount = wave_lfo
            inst.patch.detune = detune


        elif knob_mode == 2: # filter type and filter freq
            filt_type, filt_f = param_saves[knob_mode]

            if knobA_pickup:
                filt_type  = int(map_range(knobA, 0,65535, 0,3))
            if knobB_pickup:
                filt_f = map_range(knobB, 300,65300, 100, 8000)

            param_saves[knob_mode] = filt_type, filt_f

            inst.patch.filt_type = filt_type
            inst.patch.filt_f = filt_f

        elif knob_mode == 3:
            filt_q, filt_env = param_saves[knob_mode]

            if knobA_pickup:
                filt_q  = map_range(knobA, 0,65535, 0.5,2.5)
            if knobB_pickup:
                filt_env = map_range(knobB, 300,65300, 1, 0.01)

            param_saves[knob_mode] = filt_q, filt_env

            inst.patch.filt_q = filt_q
            inst.patch.filt_env_params.attack_time = filt_env

        else:
            pass

        await asyncio.sleep(0.02)


print("--- qtpy_synth wavesynth ready ---")

async def main():
    task1 = asyncio.create_task(display_updater())
    task2 = asyncio.create_task(input_handler())
    task3 = asyncio.create_task(midi_handler())
    task4 = asyncio.create_task(instrument_updater())
    await asyncio.gather(task1, task2, task3, task4)

asyncio.run(main())
