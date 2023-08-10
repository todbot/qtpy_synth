# qtpy_synth

A simple [QTPy RP2040](https://learn.adafruit.com/adafruit-qt-py-2040/overview)-based
synth to experiment with [`synthio`](https://github.com/todbot/circuitpython-synthio-tricks).

<img src="./docs/qtpy_synth_proto2a.jpg">

Features:
 - Mono audio output circuit, converting PWM to audio, as per [RP2040 design guidelines](https://datasheets.raspberrypi.com/rp2040/hardware-design-with-rp2040.pdf#page=24)
 - Optoisolated MIDI Input via TRS-A 3.5mm jack
 - Two pots for controlling parameters
 - One switch for controlling parameters
 - Four capsense touch buttons for synth triggering

Some programs written specifically for this board:

- [simpletouchsynth](https://github.com/todbot/qtpy_synth/tree/main/circuitpython/simpletouchsynth) - play with filters using touch sensors

- [wavesynth](https://github.com/todbot/qtpy_synth/tree/main/circuitpython/wavesynth) - larger general two-osc synth that can also do wavetables
  - early video demo: ["Wavetable synth w/ CircuitPython synthio on QTPy RP2040"](https://www.youtube.com/watch?v=4hgDi6MNfsI)
  - another demo: [More Wavetable synth w/ CircuitPython synthio on QTPy RP2040](https://www.youtube.com/watch?v=80yjwxscnnA)

For [many other synthio examples](https://github.com/todbot/circuitpython-synthio-tricks/tree/main/examples)
that can work with this synth with minimal changes,
see: https://github.com/todbot/circuitpython-synthio-tricks
