"""Quickstart example for using the M2satMic class to read water level and send a message to the satellite."""

import time
from datetime import datetime

from hydrosensor.serial import M2satMic
from hydrosensor.utils import MsgStatus, decode_string, encode_string

nap_offset_sensor = 98.0  # z-level of sensor in NAP

work = "water_level"
work = "modem_test"
# work = "codecs"


def work_modem_test(m2sat):
    """Work function to test modem."""
    # modem selection default seems to be 6.
    r = m2sat.modem_select(modem_type=6)
    r = m2sat.modem_info()
    m2sat.logger.info(f"Modem select result: {r}")
    # send a message
    timestr = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    message = f"Hello from Rainbow Sensing at time! {timestr}"
    message = (message * 3)[0:-30]
    m2sat.logger.info(f"Sending message: {message} of length {len(message)} to satellite")
    r = m2sat.message_send(message)
    m2sat.logger.info(f"Message send result: {r}")
    # m2sat.write(message)
    if not r.status == MsgStatus.OK:
        m2sat.logger.warning(
            f"Message sending returned some error. Status: {r.status}, message: {r.message}, value: {r.value}"
        )
        raise ValueError(
            f"Message sending returned some error. Status: {r.status}, message: {r.message}, value: {r.value}"
        )
    while True:
        r = m2sat.message_status()
        if r.status == MsgStatus.OK and r.value["transfer_status"] == "idle":
            m2sat.logger.info(f"Message transfer completed successfully! {r}")
            break
        else:
            m2sat.logger.info(f"Message status result: {r}")
        time.sleep(5)

    m2sat.close()


def work_codecs():
    """Work function to test codecs."""
    s = "Hello, world!"
    encoded = encode_string(s)
    print(f"Encoded string: {encoded}")
    decoded = decode_string(encoded)
    print(f"Decoded string: {decoded}")


def work_water_level(m2sat):
    """Work function to read water level."""
    r = m2sat.read_level()
    m2sat.close()

    # create proper string
    time = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    m2sat.logger.info("Converting distance to level N.A.P.")
    if not r.status == MsgStatus.OK:
        msg = f"Water level could not be read. Status: {r.status}, message: {r.message}"
        m2sat.logger.error(msg)
        raise ValueError(msg)
    water_level = -r.value / 1000 + nap_offset_sensor
    m2sat.logger.info(f"Printing the time, value pair {time}, {water_level} for serialization\n")
    print(f"{time},{water_level}")


m2sat = M2satMic(baud_rate=4800, port="/dev/ttyUSB0")
try:
    m2sat.open()
    m2sat.logger.info("Checking device status")
    r = m2sat.device_info()
    m2sat.logger.info(f"{r}")
    # if work == "water_level":
    #     work_water_level(m2sat)
    # elif work == "modem_test":
    #     work_modem_test(m2sat)
    # elif work == "codecs":
    #     work_codecs()

finally:
    m2sat.close()
