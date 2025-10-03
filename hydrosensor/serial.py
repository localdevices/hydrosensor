"""Serial devices."""

import pickle
import time

import serial

from hydrosensor.logger import create_logger
from hydrosensor.utils import MsgStatus, Response, checksum_lower_byte


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
            logger = create_logger(logger_name or __name__)  # create logger obj.
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
                    return data
            dt = time.time() - time1
        self.logger.debug("Timeout reached")
        return None


# specific class for MIC device of M2Sat
class M2sat(SerialDevice):
    """M2Sat modem device."""

    def __init__(self, **kwargs):
        """Initialize M2Sat modem."""
        super().__init__(logger_name="MIC", **kwargs)

    def activate_modem(self):
        """Activate modem."""
        raise NotImplementedError

    def device_status(self):
        """Return device status."""
        msg = ">C43\r"
        self.write(msg)
        # now read until we get the response
        data = self.read_until_substring(">C", timeout=10)
        if data:
            return Response(status=MsgStatus.OK, value=data, message="Device status recognized")
        else:
            return Response(status=MsgStatus.ERROR, message="Not able to read device status")

    def modem_info(self):
        """Return modem info."""
        msg = ">D44\r"
        self.write(msg)
        # TODO: finish function with full system for testing
        pass

    def modem_select(
        self,
        modem_type: int,
    ):
        """Select modem type."""
        # TODO: cannot seem to select anything but 6, test with full setup
        if modem_type < 1 or modem_type > 6:
            err_msg = "Modem type must be an integer ge 1 and le 6"
            self.logger.error(err_msg)
            raise ValueError(err_msg)
        msg = ">A{:02d}A7\r".format(modem_type)

        self.logger.debug(f"Writing {msg}")
        self.write(msg)
        data = self.read_until_substring(">A", timeout=10)
        if data:
            return Response(status=MsgStatus.OK, message=f"mode set to {modem_type}")
        else:
            return Response(status=MsgStatus.ERROR, message=f"Not able to select modem type {modem_type}")


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
