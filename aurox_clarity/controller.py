import hid
import threading
import typing

VENDORID = 0x1F0A
PIDRUN = 0x0088
# VENDORID	=0x136e
# PIDRUN		=0x1088

# general status/action values
# device in sleep mode
SLEEP = 0x7F
# device running
RUN = 0x0F

# door closed
DOORCLSD = 0x01
# door open
DOOROPEN = 0x02

# disk out of beam path, wide field
DSKPOS0 = 0x00
# disk pos 1, low sectioning
DSKPOS1 = 0x01
# disk pos 2, mid sectioning
DSKPOS2 = 0x02
# disk pos 3, high sectioning
DSKPOS3 = 0x03
# An error has occurred in setting slide position (end stops not detected)
DSKERR = 0xFF
# slide is moving between positions
DSKMID = 0x10

# Filter in position 1
FLTPOS1 = 0x01
# Filter in position 2
FLTPOS2 = 0x02
# Filter in position 3
FLTPOS3 = 0x03
# Filter in position 4
FLTPOS4 = 0x04
# An error has been detected in the filter drive (eg filters not present)
FLTERR = 0xFF
# Filter in mid position
FLTMID = 0x10

# CALibration led power on
CALON = 0x01
# CALibration led power off
CALOFF = 0x02

# common commands

# Common commands consist of 1 byte of command immediately followed by any data
# Total record length is expected to be 16 bytes for RUNSTATE

# No data out, returns 3 byte version byte1.byte2.byte3
GETVERSION = 0x00
# Reply to sent command that was not understood
CMDERROR = 0xFF

# Run state status commands

# Run State commands are 16 byte records consisting of a single command byte
# imediately followed by any data. Response has same format

# No data out, returns 1 byte on/off status
GETONOFF = 0x12
# No data out, returns 1 byte shutter status, or SLEEP if device sleeping
GETDOOR = 0x13
# No data out, returns 1 byte disk-slide status, or SLEEP if device sleeping
GETDISK = 0x14
# No data out, returns 1 byte filter position, or SLEEP if device sleeping
GETFILT = 0x15
# No data out, returns 1 byte CAL led status, or SLEEP if device sleeping
GETCAL = 0x16
# No data out, returns 4 byte BCD serial number (little endian)
GETSERIAL = 0x19
# No data, Returns 10 bytes VERSION[3],ONOFF,DOOR,DISK,FILT,CAL,??,??
FULLSTAT = 0x1F

# run state action commands
# 1 byte out on/off status, echoes command or SLEEP
SETONOFF = 0x21
# 1 byte out disk position, echoes command or SLEEP
SETDISK = 0x23
# 1 byte out filter position, echoes command or SLEEP
SETFILT = 0x24
# 1 byte out CAL led status, echoes command or SLEEP
SETCAL = 0x25

# run state service mode commands - not for general user usage, stops the disk
# spinning for alignment purposes

# 1 byte for service mode (SLEEP activates service mode and RUN, returns unit
# to normal run state), echoes command
SETSVCMODE1 = 0xE0


class Controller:
    """Control of Aurox Clarity devices.

    Args:
        index: the index of the HID, as enumerated by the hidapi library.
    """

    def __init__(self, index: int = 0):
        devices = hid.enumerate(vendor_id=VENDORID, product_id=PIDRUN)
        self._hiddevice = hid.device()
        self._hiddevice.open_path(devices[index]["path"])
        self._hiddevice.set_nonblocking(0)
        self._lock = threading.Lock()

    def __del__(self):
        if hasattr(self, "_hiddevice"):
            self._hiddevice.close()

    def sendCommand(
        self,
        command: int,
        param: typing.Optional[int] = 0,
        maxLength: typing.Optional[int] = 16,
        timeoutMs: typing.Optional[int] = 100,
    ):
        """Send a command to the Clarity device.

        Communication is via exchange of records of maximum size 16 bytes.
        All transactions are done in two steps: first write a record, then read
        a record. The return value is a list of the read bytes.

        Args:
            command: command byte
            param: param byte
            maxLength: maximum number of bytes to read
            timeoutMs: timeout threshold in miliseconds
        """
        with self._lock:
            buffer = [0x00] * maxLength
            buffer[1] = command
            buffer[2] = param
            result = self._hiddevice.write(buffer)
            answer = self._hiddevice.read(maxLength, timeoutMs)
            return answer

    def switchOn(self):
        """Switch on."""
        self.sendCommand(SETONOFF, RUN)

    def switchOff(self):
        """Switch off."""
        self.sendCommand(SETONOFF, SLEEP)

    def getOnOff(self):
        """Get on/off status."""
        res = self.sendCommand(GETONOFF)
        return res[1]

    def setDiskPosition(self, newDiskPosition: int):
        """Set the disk's position.

        Args:
            newDiskPosition: the new position of the disk
        """
        self.sendCommand(SETDISK, newDiskPosition)

    def getDiskPosition(self):
        """Get the disk's position."""
        res = self.sendCommand(GETDISK)
        return res[1]

    def setFilterPosition(self, filterPosition: int):
        """Set the filter cube turret's position.

        Args:
            filterPosition: the new position of the filter cube turret
        """
        self.sendCommand(SETFILT, filterPosition)

    def getFilterPosition(self):
        """Get the filter cube turret's position."""
        res = self.sendCommand(GETFILT)
        return res[1]

    def setCalibrationLED(self, calLED: int):
        """Switches the calibration LED on/off.

        Args:
            calLED: the on or off state of the LED
        """
        self.sendCommand(SETCAL, calLED)

    def getCalibrationLED(self):
        """Get the on/off state of the calibration LED."""
        res = self.sendCommand(GETCAL)
        return res[1]

    def getDoor(self):
        """Get the open/closed state of the filter cube turret door."""
        res = self.sendCommand(GETDOOR)
        return res[1]

    def getSerialNumber(self):
        """Get the device's serial number."""
        res = self.sendCommand(GETSERIAL)
        return (
            (res[4] // 16) * 10000000
            + (res[4] % 16) * 1000000
            + (res[3] // 16) * 100000
            + (res[3] % 16) * 10000
            + (res[2] // 16) * 1000
            + (res[2] % 16) * 100
            + (res[1] // 16) * 10
            + (res[1] % 16)
        )

    def getFullStat(self):
        """Get the full state of the device.

        Returns 8 bytes: VERSION[3], ONOFF, DOOR, DISK, FILT, CALIB.
        """
        res = self.sendCommand(FULLSTAT)
        return [
            (res[1], res[2], res[3]),
            res[4],
            res[5],
            res[6],
            res[7],
            res[8],
        ]

    def getVersion(self):
        """Get the firmware version of the device."""
        res = self.sendCommand(GETVERSION)
        return (res[1], res[2], res[3])
