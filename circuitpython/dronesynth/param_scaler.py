# SPDX-FileCopyrightText: Copyright (c) 2024 Tod Kurt
# SPDX-License-Identifier: MIT
"""
`param_scaler`
================================================================================

`ParamScaler` attempts to solve the "knob pickup" problem when a control's
position does not match the Param position.

The scaler will increase/decrease its internal value relative to the change
of the incoming knob position and the amount of "runway" remaining on the
value. Once the knob reaches its max or min position, the value will
move in sync with the knob.  The value will always decrease/increase
in the same direction as the knob.
This mirrors how the Deluge synth's "SCALE" mode works.

Part of synth_tools.

Example:

  scaler = ParamScaler(127, pot.value)  # make a scaler
  while True:

    knob_pos = pot.value  # get "real" position of pot

    # scales 'val' in direciton of 'knob_val' turning
    val_to_use = scaler.update(knob_pos)

    if button:
       # loading a new value, means need to update scaler
       val = get_new_val()
       scaler.reset(val, knob_pos)
       
"""

from micropython import const

knob_min, knob_max = const(0), const(255) 
val_min, val_max = const(0), const(255) 

dbg_scaler = True
def dbg(*args):
    if dbg_scaler: print(*args)

class ParamScaler:
    def __init__(self, val_start, knob_pos):
        """ Make a ParamScaler, val and knob_pos range from 0-255, floating point """
        self.val = val_start
        self.last_knob_pos = knob_pos
        self.knob_match = False
        self.dead_zone = 1

    def reset(self, val=None, knob_pos=None):
        """ Resets current val and knob_pos (e.g. for loading a new controlled parameter """
        if val is not None:
            self.val = val
        if knob_pos is not None:
            self.last_knob_pos = knob_pos
        self.knob_match = False

    def update(self, knob_pos):
        """
        Call whenever knob_position changes.
        Returns a value scale in direction of knob turn
        """
        dbg("knob_pos:%3d last:%3d val:%.1f" % (knob_pos, self.last_knob_pos, self.val))
        
        knob_delta = knob_pos - self.last_knob_pos
        
        if abs(knob_delta) < self.dead_zone:
            return self.val

        self.last_knob_pos = knob_pos
        
        knob_delta_pos = (knob_max - knob_pos)
        knob_delta_neg = (knob_pos - knob_min)

        val_delta_pos  = (val_max - self.val)
        val_delta_neg  = (self.val - val_min)

        dbg("deltas: %.1f %.1f, %.1f %.1f" %
              (knob_delta_pos,knob_delta_neg, val_delta_pos,val_delta_neg))
        
        val_change = 0
        if knob_delta > self.dead_zone:
            val_change = (knob_delta / knob_delta_pos) * val_delta_pos
        elif knob_delta < self.dead_zone:
            val_change = (knob_delta / knob_delta_neg) * val_delta_neg
            
        dbg("val_change:%.1f" % val_change)
        self.val = self.val + val_change
        return min(max(self.val, val_min), val_max)

