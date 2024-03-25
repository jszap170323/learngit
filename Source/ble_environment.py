import bluetooth
import random
import struct
import time
from ble_advertising import advertising_payload

from micropython import const

import bme280_float as bme280
from machine import Pin, I2C

from gpio import blink

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_INDICATE_DONE = const(20)

# org.bluetooth.service.environmental_sensing
_ENV_SENSE_UUID = bluetooth.UUID(0x181A)

# atmospheric pressure
# org.bluetooth.characteristic.pressure
_PRESSURE_CHAR = (
    bluetooth.UUID("521645ba-36ab-4580-ac6c-8e921697da23"),
    bluetooth.FLAG_READ,
)

# percentage humidity
# org.bluetooth.characteristic.humidity
_SETCONTROL_CHAR = (
    bluetooth.UUID("521645ba-36ac-4580-ac6c-8e921697da23"),
    bluetooth.FLAG_WRITE,
)


_ENV_SENSE_SERVICE = (
    _ENV_SENSE_UUID,
    (_PRESSURE_CHAR, _SETCONTROL_CHAR),
)

# org.bluetooth.characteristic.gap.appearance.xml
_ADV_APPEARANCE_GENERIC_ENVIRONMENTAL_SENSOR = const(5696)


class BLEEnvironment:
    def __init__(self, ble, name="esp32-ble-demo"):
        """
        __init__ :: BLEEnvironment -> bluetooth.BLE -> str -> BLEEnvironment
        """
        self._ble = ble
        self._ble.active(True)
        # register the event handler for events in the BLE stack
        self._ble.irq(self._irq)
        # unpack the gatt handles returned from service registration
        ((self._pressure_handle, self._setcontrol_handle), ) = self._ble.gatts_register_services((_ENV_SENSE_SERVICE,))
        # a set to contain connections to enable the sending of notifications
        self._connections = set()
        # create the payload for advertising the server
        self._payload = advertising_payload(
            name=name,
            services=[_ENV_SENSE_UUID],
            appearance=_ADV_APPEARANCE_GENERIC_ENVIRONMENTAL_SENSOR
        )
        # begin advertising the gatt server
        self._advertise()

    def _irq(self, event, data):
        # callback function for events from the BLE stack
        # Track connections so we can send notifications.
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            self._connections.add(conn_handle)
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            self._connections.remove(conn_handle)
            # Start advertising again to allow a new connection.
            self._advertise()
        elif event == _IRQ_GATTS_INDICATE_DONE:
            conn_handle, value_handle, status = data

    def set_environment_data(self, pressure, notify=False, indicate=False):

        # write fresh temperature, pressure, and humidity data to the GATT server characteristics
        self._ble.gatts_write(self._pressure_handle,
                              struct.pack("<i", int(pressure)))

        # optionally notify and or indicate connected centrals
        if notify or indicate:
            for conn_handle in self._connections:
                if notify:
                    # Notify connected centrals.
                    self._ble.gatts_notify(conn_handle, self._pressure_handle)
                if indicate:
                    # Indicate connected centrals.
                    self._ble.gatts_indicate(
                        conn_handle, self._pressure_handle)

    def _advertise(self, interval_us=100):
        self._ble.gap_advertise(interval_us, adv_data=self._payload)


def run():
    ble = bluetooth.BLE()
    env = BLEEnvironment(ble)

    i = 0

    while True:
        # Write every second, notify every 10 seconds.
        i = (i + 1) % 10

        pressure = 2

        # publish environment data
        env.set_environment_data(
            pressure, notify=False, indicate=False)

        # take a break
        # TODO can micropython power the board down for a duration instead of sleeping? or is that how sleep is implemented?
        time.sleep_ms(1000)


if __name__ == "__main__":
    run()
