
qtpy_synth circuitpython
========================

This is a collection of example synths to run on the qtpy_synth board.

These examples include:

- "[hwtest](./hwtest)" -- check that all hardware parts work
- "[simpletouchsynth](./simpletouchsynth)" -- very simple single-patch synth with adjustable filter
- "[wavesynth](./wavesynth)" -- wavetable synthesizer with GUI and wavetable selection


### Running the examples:

To run these examples:

1. Copy the contents of the `lib` here directory to CIRCUITPY/lib
2. Copy everything in example synth's directory to the CIRCUITPY drive 
     (e.g. `code.py` file and any other files)
3. Install external libraries. They are listed in `requirements.txt`.
    The easiest way to install them is with `circup` on the commandline:
    ```sh
    circup install -r requirements.txt
    ```
