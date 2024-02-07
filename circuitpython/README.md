
qtpy_synth circuitpython
========================

In the "examples" directory are a collection of example synths to run on the qtpy_synth board.

These exmaples include:
- "[hwtest](./examples/hwtest)" -- check that all hardware parts work
- "[simplesynth](./examples/simplesynth)" -- very simple single-patch synth with adjustable filter
- "[wavesynth](./examples/wavesynth)" -- wavetable synthesizer with GUI and wavetable selection

### Running the examples:

To run these examples:

1. Copy the "qtpy_synth" directory in this directory to the CIRCUITPY drive
2. Install external libraries. They are listed in `requirements.txt'.
The easiest way to install them is with `circup` on the commandline:
    ```sh
    circup install -r requirements.txt
    ```
