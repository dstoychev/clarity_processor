import hid

VENDORID	=0x1F0A
PIDRUN		=0x0088
#VENDORID	=0x136e
#PIDRUN		=0x1088

#general status/action values
SLEEP		=0x7f			#device in sleep mode
RUN		    =0x0f			#device running

DOORCLSD	=0x01			#door closed
DOOROPEN	=0x02			#door open

DSKPOS0     =0x00           #disk out of beam path, wide field
DSKPOS1		=0x01			#disk pos 1, low sectioning
DSKPOS2		=0x02			#disk pos 2, mid sectioning
DSKPOS3     =0x03           #disk pos 3, high sectioning
DSKERR		=0xff			#An error has occurred in setting slide position (end stops not detected)
DSKMID		=0x10			#slide is moving between positions

FLTPOS1		=0x01			#Filter in position 1
FLTPOS2		=0x02			#Filter in position 2
FLTPOS3		=0x03			#Filter in position 3
FLTPOS4		=0x04			#Filter in position 4
FLTERR		=0xff			#An error has been detected in the filter drive (eg filters not present)
FLTMID		=0x10			#Filter in mid position

CALON		=0x01			#CALibration led power on
CALOFF		=0x02			#CALibration led power off

#common commands

# Common commands consist of 1 byte of command immediately followed by any data
# Total record length is expected to be 16 bytes for RUNSTATE

GETVERSION	=0x00			#No data out, returns 3 byte version byte1.byte2.byte3
CMDERROR	=0xff			#Reply to sent command that was not understood

#Run state status commands

# Run State commands are 16 byte records consisting of a single command byte imediately followed by any data
# Response has same format 

GETONOFF	=0x12			#No data out, returns 1 byte on/off status
GETDOOR 	=0x13			#No data out, returns 1 byte shutter status, or SLEEP if device sleeping
GETDISK 	=0x14			#No data out, returns 1 byte disk-slide status, or SLEEP if device sleeping
GETFILT		=0x15			#No data out, returns 1 byte filter position, or SLEEP if device sleeping
GETCAL		=0x16			#No data out, returns 1 byte CAL led status, or SLEEP if device sleeping
GETSERIAL	=0x19			#No data out, returns 4 byte BCD serial number (little endian)
FULLSTAT	=0x1f			#No data, Returns 10 bytes VERSION[3],ONOFF,DOOR,DISK,FILT,CAL,??,??

#run state action commands
SETONOFF	=0x21			#1 byte out on/off status, echoes command or SLEEP
SETDISK 	=0x23			#1 byte out disk position, echoes command or SLEEP
SETFILT		=0x24			#1 byte out filter position, echoes command or SLEEP
SETCAL		=0x25			#1 byte out CAL led status, echoes command or SLEEP

#run state service mode commands - not for general user usage, stops the disk spinning for alignment purposes

SETSVCMODE1	=0xe0			#1 byte for service mode (SLEEP activates service mode and RUN, returns unit to normal run state), echoes command

class Controller:
    def __init__(self, index=0):
        devices = hid.enumerate(vendor_id=VENDORID, product_id=PIDRUN)
        self.hiddevice = hid.device()
        self.hiddevice.open_path(devices[index]["path"])
        self.hiddevice.set_nonblocking(0)

    def __del__(self):
        if hasattr(self, "hiddevice"):
            self.hiddevice.close()

    ## Send command to HID device using cython-hidapi, all transactions are 2 way - write then read
    def sendCommand(self, command, param = 0, maxLength = 16, timeoutMs = 100):
        buffer = [0x00] * maxLength
        buffer[1] = command
        buffer[2] = param
        result = self.hiddevice.write(buffer)
        answer = self.hiddevice.read(maxLength, timeoutMs)
        return answer

    ## Switch on Clarity
    def switchOn(self):
        self.sendCommand(SETONOFF, RUN)

    ## Switch off Clarity
    def switchOff(self):
        self.sendCommand(SETONOFF, SLEEP)

    ## Get of/off status
    def getOnOff(self):
        res = self.sendCommand(GETONOFF)
        return res[1]

    # Set Clarity's disk position
    def setDiskPosition(self, newDiskPosition):
        self.sendCommand(SETDISK, newDiskPosition)

    # Get Clarity's disk position
    def getDiskPosition(self):
        res = self.sendCommand(GETDISK)
        return res[1]

    # Set Clarity's filter position
    def setFilterPosition(self, filterPosition) :
        self.sendCommand(SETFILT, filterPosition)

    # Get Clarity's filter position
    def getFilterPosition(self):
        res = self.sendCommand(GETFILT)
        return res[1]

    # Set Clarity's calibration LED on or off
    def setCalibrationLED(self, calLED):
        self.sendCommand(SETCAL, calLED)

    # Get Clarity's calibration LED status
    def getCalibrationLED(self):
        res = self.sendCommand(GETCAL)
        return res[1]

    # Get Clarity's door status
    def getDoor(self):
        res = self.sendCommand(GETDOOR)
        return res[1]

    # Get Clarity's serial number
    def getSerialNumber(self):
        res = self.sendCommand(GETSERIAL)
        return ((res[4]//16)*10000000+(res[4]%16)*1000000+(res[3]//16)*100000+(res[3]%16)*10000+
                (res[2]//16)*1000+(res[2]%16)*100+(res[1]//16)*10+(res[1]%16))

    # Returns 10 bytes Firmware VERSION[3], ONOFF, DOOR, DISK, FILT, CAL
    def getFullStat(self):
        res = self.sendCommand(FULLSTAT)
        return [(res[1],res[2],res[3]),res[4],res[5],res[6],res[7],res[8]]

    def getVersion(self):
        res = self.sendCommand(GETVERSION)
        return (res[1], res[2], res[3])
