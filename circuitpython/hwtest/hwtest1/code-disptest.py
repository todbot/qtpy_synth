

import time

from disp_test import DispTester
disptester = DispTester()

#import board, busio, displayio
#import adafruit_displayio_ssd1306  # circup install adafruit_displayio_ssd1306
#displayio.release_displays() # can we put this in sequencer_hardware?
#i2c = busio.I2C( scl=board.SCL, sda=board.SDA, frequency=400_000 )
#display_bus = displayio.I2CDisplay(i2c, device_address=0x3C)  # or 0x3D depending on display
#display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64, rotation=180)

while True:
    print("hi there", time.monotonic())
    time.sleep(0.1)
