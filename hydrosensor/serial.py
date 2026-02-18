"""Serial devices."""

import pickle
import time

import serial

from hydrosensor.logger import create_logger
from hydrosensor.utils import MsgStatus, Response, checksum_hex_string, checksum_lower_byte, encode_string_to_message


class SerialDevice:
    """Generic serial device class.

    Can be inherited for specific serial devices.
    """

    def __init__(self, port, baud_rate=9600, timeout=5, logger=None, logger_name=None):
        """Initiate object with defaults."""
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.port = port
        self.serial = None
        self.data = None
        self.text = None
        if logger is None:
            logger = create_logger(logger_name or __name__)
        self.logger = logger

    def open(self):
        """Open the serial device on self.port.

        Returns IOError if not found.
        """
        if self.port is not None:
            try:
                self.serial = serial.Serial(self.port, self.baud_rate, timeout=self.timeout)
                self.logger.info(f"Serial port on {self.port} opened with baud rate {self.baud_rate}")
            except Exception:
                raise IOError("Cannot open serial device, check permissions")
        else:
            raise IOError("No port specified, please connect a device.")

    def close(self):
        """Close the serial device on self.port.

        Return IOError if no open device is found.
        """
        if self.serial is not None:
            self.serial.close()
            self.logger.warning(f"Serial connection to {self.port} is closed.")
        else:
            raise IOError("No serial connection is open.")

    def send_method(self, name, **kwargs):
        """Serialize a function name and its arguments in pickle, and write to device.

        function arguments must be provided in **kwargs
        """
        if self.serial is None:
            raise IOError("No serial connection is open.")

        msg = {"name": name, "kwargs": kwargs}
        p = pickle.dumps(msg)  # serialize msg
        self.serial.write(p)

    def write(self, data):
        """Write a raw msg from serial connection."""
        if self.serial is not None:
            # Clear input and output buffers before sending
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()

            # encode data
            p = data.encode("utf-8")
            # p = pickle.dumps(data)  # serialize msg
            r = self.serial.write(p)
            return r

        else:
            raise IOError("No serial connection is open.")

    def read(self):
        """Read a raw msg from serial connection."""
        if self.serial is not None:
            data = self.serial.readline()
            if len(data) == 0:
                return None
            try:
                return data.decode("utf-8").rstrip("\n").rstrip("\r")
            except UnicodeDecodeError:
                # apparently decoding is not possible, as it is not a proper utf-8
                return None
            # return pickle.loads(data)  # return loaded data
        else:
            raise IOError("No serial connection is open.")

    def read_until_substring(self, substring: str, timeout: float = 1):
        """Continuously read from device until a substring is found."""
        if self.serial is None:
            raise IOError("No serial connection is open.")
        self.serial.reset_input_buffer()
        self.serial.reset_output_buffer()

        time1 = time.time()
        dt = time.time() - time1
        while dt < timeout:
            data = self.read()
            # print(data)
            if data is not None:
                # check for substring
                if substring in data:
                    # remove any data before the last occurrence of the substring
                    data_content = substring + data.split(substring)[-1]
                    return data_content
            dt = time.time() - time1
        self.logger.debug("Timeout reached")
        return None


# specific class for MIC device of M2Sat
class M2sat(SerialDevice):
    """M2Sat modem device."""

    def __init__(self, **kwargs):
        """Initialize M2Sat modem."""
        super().__init__(logger_name="MIC", **kwargs)

    def device_info(self):
        """Return device status."""
        msg = ">C43\r"
        self.write(msg)
        # now read until we get the response
        data = self.read_until_substring(">C", timeout=10)
        if not data:
            return Response(status=MsgStatus.ERROR, message="timeout")
        if ">C00" not in data:
            return Response(status=MsgStatus.ERROR, value=data, message=f"Device status indicates error {data[2:4]}")
        else:
            # strip serial number, firmware version and other info from data and return as dict in value
            substring = data[4:]
            hardware_version, substring = substring.strip("HW=").split(" ", 1)
            firmware_version, substring = substring.strip("FW=").split(" ", 1)
            serial_number, _ = substring.strip("SN=").split(" ", 1)
            value = {
                "hardware_version": hardware_version,
                "firmware_version": firmware_version,
                "serial_number": serial_number,
            }
        return Response(status=MsgStatus.OK, value=value, message="Device info reported")

    def message_send(self, msg: str) -> Response:
        """Send message to satellite."""
        # check if message status is idle before sending message, otherwise return error
        r = self.message_status()
        if r.value is None:
            return Response(status=MsgStatus.ERROR, message="Not able to read message status from modem device.")
        if not r.status == MsgStatus.OK:
            return r
        if not r.value["transfer_status"] == "idle":
            return Response(status=MsgStatus.ERROR, message="Message status is not idle, cannot send new message.")
        # encode message
        hex_msg = encode_string_to_message(msg)
        self.write(hex_msg + "\r")
        wait_str = ">F"
        data = self.read_until_substring(wait_str, timeout=60)
        if not data:
            return Response(status=MsgStatus.ERROR, value=data, message="timeout")
        if not checksum_lower_byte(data[1:4], data[4:]):
            self.logger.error("checksum error")
            return Response(status=MsgStatus.ERROR, value=data, message="checksum error")
        if ">F02" in data:
            msg = "Modem is busy sending a message, try again later"
            self.logger.error(msg)
            return Response(status=MsgStatus.ERROR, value=data, message=msg)
        elif ">F03" in data:
            # retrieve modem info to know max length of message
            r = self.modem_info()
            if r.status == MsgStatus.OK and r.value is not None and "max_payload_txt" in r.value:
                max_length = r.value["max_payload_txt"]
                msg = f"Message too long to send {len(msg)}, max length is {max_length}"
            else:
                msg = f"Message too long to send {len(msg)}, could not retrieve max length from modem info"
            return Response(status=MsgStatus.ERROR, value=data, message=msg)
        elif ">F09" in data:
            msg = f"Message could not be sent due to an unknown error, raw response was {data}"
            self.logger.error(msg)
            return Response(status=MsgStatus.ERROR, value=data, message=msg)
        self.logger.info("Message sent successfully")
        return Response(status=MsgStatus.OK, value=data, message="Message sent successfully")

    def message_status(self) -> Response:
        """Return message status."""
        msg = ">E45\r"
        self.logger.debug(f"Writing {msg}")
        self.write(msg)
        wait_str = ">E"
        data = self.read_until_substring(wait_str, timeout=10)
        if not data:
            return Response(status=MsgStatus.ERROR, message="timeout")
        if not checksum_lower_byte(data[1:12], data[12:]):
            self.logger.error("Message status checksum error")
            return Response(status=MsgStatus.ERROR, message="checksum error")
        ok_status = int(data[0:2], 16)
        if ok_status != 0:
            self.logger.error(f"Modem info response indicates error {ok_status}, raw response was {data}")
            return Response(
                status=MsgStatus.ERROR, message=f"Not able to read modem info ERROR {ok_status}, response was {data}"
            )
        if int(data[2:4], 16) == 0:
            transfer_status = "idle"
        elif int(data[2:4], 16) == 1:
            transfer_status = "busy"
        else:
            transfer_status = "unknown"
        if int(data[4:6], 16) == 0:
            last_transfer_status = "success"
        elif int(data[4:6], 16) == 16:
            last_transfer_status = "failed error code 10"
        elif int(data[4:6], 16) == 17:
            last_transfer_status = "failed error code 11"
        elif int(data[4:6], 16) == 32:
            last_transfer_status = "aborted"
        elif int(data[4:6], 16) == 48:
            last_transfer_status = "timeout"
        elif int(data[4:6], 16) == 255:
            last_transfer_status = "unknown status"
        else:
            # TODO: check if there are other last msg states
            last_transfer_status = f"unknown transfer status code {data[4:6]}"
        value = {
            "transfer_status": transfer_status,
            "last_transfer_status": last_transfer_status,
            "timer": int(data[6:10], 16),
            "raw": data,
        }
        return Response(status=MsgStatus.OK, value=value, message="Message status read")

    def modem_activate(self):
        """Activate modem."""
        raise NotImplementedError

    def modem_info(self):
        """Return modem info."""
        msg = ">D44\r"
        self.logger.debug(f"Writing {msg}")
        self.write(msg)
        # TODO: finish function with full system for testing
        wait_str = ">D"
        data = self.read_until_substring(wait_str, timeout=10)
        if not data:
            return Response(status=MsgStatus.ERROR, message="timeout")
        # checksum
        if not checksum_lower_byte(data[1:12], data[12:]):
            self.logger.error("Modem info checksum error")
            return Response(status=MsgStatus.ERROR, message="checksum error")
        ok_status = int(data[0:2], 16)
        if ok_status != 0:
            self.logger.error(f"Modem info response indicates error {ok_status}, raw response was {data}")
            return Response(
                status=MsgStatus.ERROR, message=f"Not able to read modem info ERROR {ok_status}, response was {data}"
            )
        value = {
            "modem_type": int(data[2:4], 16),
            "max_payload_txt": int(data[4:6], 16),
            "max_payload_bin": int(data[6:8], 16),
            "serial_port": int(data[8:10], 16),
        }
        return Response(status=MsgStatus.OK, value=value, message="Modem info read")

    def modem_select(
        self,
        modem_type: int,
    ):
        """Select modem type."""
        msg = ">A{:02d}".format(modem_type)
        # calculate checksum of msg without > and add to msg
        msg += checksum_hex_string(msg[1:]) + "\r"
        wait_str = ">A"
        self.logger.debug(f"Writing {msg}")
        self.write(msg)
        data = self.read_until_substring(wait_str, timeout=10)
        if not data:
            return Response(status=MsgStatus.ERROR, message="timeout")
        # get >A part of data and check content
        data_content = wait_str + data.split(wait_str)[-1]
        if not checksum_lower_byte(data_content[1:-2], data_content[-2:]):
            self.logger.error("checksum error")
            return Response(status=MsgStatus.ERROR, message="checksum error", value=data_content)
        if ">A00" in data_content:
            # this means modem type seems successfully selected
            msg = f"Modem type {modem_type} selected successfully"
            self.logger.info(msg)
            return Response(status=MsgStatus.OK, value=data_content, message=msg)
        elif ">A01" in data_content:
            msg = f"Modem type {modem_type} out of range (1-6)"
            self.logger.error(msg)
            return Response(status=MsgStatus.ERROR, message=msg, value=data_content)
        elif ">A02" in data_content:
            msg = f"Modem type {modem_type} not available or not installed (check wiring)"
            self.logger.error(msg)
            return Response(status=MsgStatus.ERROR, message=msg, value=data_content)
        elif ">A03" in data_content:
            msg = f"Modem type {modem_type} cannot be selected, software driver not implemented yet"
            self.logger.error(msg)
            return Response(status=MsgStatus.ERROR, message=msg, value=data_content)


class M2satMic(M2sat):
    """M2Sat modem with MIC water level device."""

    def __init__(self, **kwargs):
        """Initialize M2Sat MIC reader."""
        super().__init__(**kwargs)
        # add properties specific to M2Sat modem with MIC water level device

    def read_level(self):
        """Read water level from M2Sat MIC."""
        msg = ">Z5A\r"
        self.write(msg)
        data = self.read_until_substring(">Z", timeout=5)
        if data is None:
            return Response(status=MsgStatus.ERROR, message="timeout")
        if ">Z05" in data:
            return Response(status=MsgStatus.ERROR, message="no sensor")
        if ">Z00" in data:
            # perform checksum. Last byte should be equal to the sum of bytes of the first characters.
            if checksum_lower_byte(data[1:8], data[8:]):
                return Response(status=MsgStatus.OK, value=int(data[4:8], 16), message="Level read")
            else:
                return Response(status=MsgStatus.ERROR, message="checksum error")
        # something else than >Z00 or >Z05 was returned
        return Response(status=MsgStatus.ERROR, message="unknown error")
