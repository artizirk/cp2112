#!/usr/bin/env python3

import time
import hid

# based on https://github.com/MLAB-project/pymlab
class HIDDriver:
    def __init__(self,*,serial=None, led=True):
        h = self.h = hid.device()
        self.h.open(0x10C4, 0xEA90, serial) # Connect HID again after enumeration

        print("Manufacturer: %s" % h.get_manufacturer_string())
        print("Product: %s" % h.get_product_string())
        print("Serial No: %s" % h.get_serial_number_string())

        print('blink led set gpio')
        self.h.send_feature_report([0x03, 0xFF, 0x00, 0x00, 0x00])  # Set GPIO to Open-Drain
        for k in range(3):      # blinking LED
            print('.')
            self.h.send_feature_report([0x04, 0x00, 0xFF])
            time.sleep(0.1)
            print('.')
            self.h.send_feature_report([0x04, 0xFF, 0xFF])
            time.sleep(0.1)

        self.gpio_direction = 0x00   # 0 - input, 1 - output
        self.gpio_pushpull  = 0x00   # 0 - open-drain, 1 - push-pull
        self.gpio_special   = 0x00   # only on bits 0-2,  0 standard gpio, 1 special function as LED, CLK out
        self.gpio_clockdiv  = 1   # should be 24Mhz on GPIO7, equation: 48Mhz / (2 * clockdiv)

        if led:     # Set GPIO to RX/TX LED
            self.gpio_direction = 0x83
            self.gpio_pushpull  = 0xFF
            self.gpio_special   = 0xFF

        print("set gpio")
        self.h.send_feature_report([0x02, self.gpio_direction, self.gpio_pushpull, self.gpio_special, self.gpio_clockdiv])  # initialize GPIO

        print("Set SMB Configuration (AN 495)")
        self.h.send_feature_report([0x06, 0x00, 0x01, 0x86, 0xA0, 0x02, 0x00, 0x00, 0xFF, 0x00, 0xFF, 0x01, 0x00, 0x0F])

    def I2CError(self):
        print("reset")
        self.h.send_feature_report([0x01, 0x01])  # Reset Device for cancelling all transfers and reset configuration
        self.h.close()
        time.sleep(3)   # Give a time to OS for release the BUS
        raise IOError()

    def write_hid(self, data):
        self.h.send_feature_report(data)

    def read_hid(self, len):
        return self.h.get_feature_report(len)

    def get_handler(self):
        return self.h

    # WARNING ! - CP2112 does not support I2C address 0
    def write_byte(self, address, value):
        return self.h.write([0x14, address<<1, 0x01, value]) # Data Write Request

    def read_byte(self, address):
        self.h.write([0x10, address<<1, 0x00, 0x01]) # Data Read Request

        for k in range(10):
            self.h.write([0x15, 0x01]) # Transfer Status Request
            response = self.h.read(7)
            if (response[0] == 0x16) and (response[2] == 5):  # Polling a data
                self.h.write([0x12, 0x00, 0x01]) # Data Read Force
                response = self.h.read(4)
                return response[3]
        print("CP2112 Byte Read Error...")
        self.I2CError()

    def write_byte_data(self, address, register, value):
        return self.h.write([0x14, address<<1, 0x02, register, value]) # Data Write Request

    def read_byte_data(self, address, register):
        self.h.write([0x11, address<<1, 0x00, 0x01, 0x01, register]) # Data Write Read Request

        for k in range(10):
            self.h.write([0x15, 0x01]) # Transfer Status Request
            response = self.h.read(7)
            #print "status",map(hex,response)
            if (response[0] == 0x16) and (response[2] == 5):  # Polling a data
                self.h.write([0x12, 0x00, 0x01]) # Data Read Force
                response = self.h.read(4)
                #print "data ",map(hex,response)
                return response[3]
        print("CP2112 Byte Data Read Error...")
        self.I2CError()

    def write_word_data(self, address, register, value):
        return self.h.write([0x14, address<<1, 0x03, register, value>>8, value & 0xFF]) # Word Write Request

    def read_word_data(self, address, register):
        self.h.write([0x11, address<<1, 0x00, 0x02, 0x01, register]) # Data Write Read Request
        self.h.write([0x12, 0x00, 0x02]) # Data Read Force

        for k in range(10):             # Polling a data
            response = self.h.read(10)
            #print map(hex,response)
            #print "status ",response
            if (response[0] == 0x13) and (response[2] == 2):
                return (response[4]<<8)+response[3]
            #self.h.write([0x15, 0x01]) # Transfer Status Request
            self.h.write([0x11, address<<1, 0x00, 0x02, 0x01, register]) # Data Write Read Request
            self.h.write([0x12, 0x00, 0x02]) # Data Read Force
        print("CP2112 Word Read Error...")
        self.I2CError()

    def write_block_data(self, address, register, value):
        raise NotImplementedError()

    def read_block_data(self, address, register):
        raise NotImplementedError()

    def write_i2c_block(self, address, value):
        if (len(value) > 61):
            raise IndexError()
        data = [0x14, address<<1, len(value)]  # Data Write Request (max. 61 bytes, hidapi allows max 8bytes transaction lenght)
        data.extend(value)
        return self.h.write(data) # Word Write Request
        self.I2CError()

    def read_i2c_block(self, address, length):
        self.h.write([0x10, address<<1, 0x00, length]) # Data Read Request (60 bytes)

        for k in range(10):
            self.h.write([0x15, 0x01]) # Transfer Status Request
            response = self.h.read(7)
            #print "response ",map(hex,response)
            if (response[0] == 0x16) and (response[2] == 5):  # Polling a data
                #length = (response[5]<<8)+response[6]
                self.h.write([0x12, response[5], response[6]]) # Data Read Force
                data = self.h.read(length+3)
                #print "length ",length
                #print "data ",map(hex,data)
                return data[3:]
        print("CP2112 Byte Data Read Error...")
        self.I2CError()

    def write_i2c_block_data(self, address, register, value):
        raise NotImplementedError()

    def read_i2c_block_data(self, address, register, length = 1):
        raise NotImplementedError()


if __name__ == '__main__':
    print("Start")
    d = HIDDriver()
    print("version")
    print("err", d.h.error())
    print("write", d.h.get_feature_report(0x05, 3))
    #print("answ", d.h.read(15, timeout_ms=3000))

    #d.I2CError()
