# Introduction
Calibration and processing for [Aurox Clarity](http://www.aurox.co.uk/aurox-confocal-microscope-confocals.php) microscopy data.

This package provides two Python modules for Aurox Clarity instruments -- one for control and another for processing of image data.

# Installation
The package can be installed or uninstalled using `pip`, the standard Python package manager:

    python -m pip install /path/to/this/repository
    python -m pip uninstall aurox_clarity

# Description
## Controller
The controller module uses a Python wrapper around the [hidapi](https://github.com/libusb/hidapi) library to access devices on the serial bus. Communication can be accomplished via the `sendCommand()` method and the module provides definitions for all commands and parameters of the protocol:

Command      | Input/Output
-------------|-------------
`GETONOFF`   | 1 byte; `SLEEP` or `RUN`
`SETONOFF`   | 1 byte; `SLEEP` or `RUN`
`GETDOOR`    | 1 byte; `DOORCLSD` or `DOOROPEN`
`GETDISK`    | 1 byte; `DSKPOS0` or `DSKPOS1` or `DSKPOS2` or `DSKPOS3` or `DSKERR` or `DSKMID`
`SETDISK`    | 1 byte; `DSKPOS0` or `DSKPOS1` or `DSKPOS2` or `DSKPOS3`
`GETFILT`    | 1 byte; `FLTPOS0` or `FLTPOS1` or `FLTPOS2` or `FLTPOS3` or `FLTERR` or `FLTMID`
`SETFILT`    | 1 byte; `FLTPOS0` or `FLTPOS1` or `FLTPOS2` or `FLTPOS3`
`GETCAL`     | 1 byte; `CALON` or `CALOFF`
`SETCAL`     | 1 byte; `CALON` or `CALOFF`
`GETVERIOSN` | 3 bytes; version in the format byte1.byte2.byte3
`GETSERIAL`  | 4 bytes; BCD serial number (little endian)
`FULLSTAT`   | 8 bytes; 3 bytes for the version and 1 byte for each of on/off status, door status, disk position, filter turret position, and calibration light status

All commands sent to a Clarity device could also get a response of `CMDERROR` when the command could not be interpreted. As an alternative to sending command directly, methods are provided for each command:

* switchOn
* switchOff
* getOnOff
* setDiskPosition
* getDiskPosition
* setFilterPosition
* getFilterPosition
* setCalibrationLED
* getCalibrationLED
* getDoor
* getSerialNumber
* getFullStat
* getVersion

Usage:

```python
import aurox_clarity.controller

ctrl = aurox_clarity.controller.Controller()

# Specify the device's index (useful on systems with multiple Clarity devices)
ctrl = aurox_clarity.controller.Controller(2)

ctrl.switchOn()

# Set the filter wheel to the 3rd position
ctrl.sendCommand(aurox_clarity.controller.SETFILT, aurox_clarity.controller.FLTPOS3)

# Set the disk slide to 2nd position
ctrl.setDiskPosition(aurox_clarity.controller.DSKPOS2)

if ctrl.getDoor() == aurox_clarity.controller.DOOROPEN:
    print("The filter turret door is open!")

serial = ctrl.getSerialNumber()

version, onoff_state, door_state, disk_pos, filt_pos, cal_state = ctrl.getFullStat()

# Turn off and close
ctrl.switchOff()
ctrl.close()
```

## Processor
The processor module uses [OpenCV](https://github.com/opencv/opencv) to process images that have been acquired with
a camera connected to an Aurox Clarity instrument. Before confocal images can
be computed, the system needs to be calibrated first. For this the calibration
LED needs to be turned on with the controller module. This will project a calibration pattern on the camera. An image of this pattern is used for the initialisation of the `Processor` class. You should set up a instance of the class for each filter/disk position combination that you use as the calibration can be different.

The class provides several methods that differ in their inputs and algorithms:

* `process()`: takes 1 combined Numpy array, converts it to a cv2.UMat, and then performs scaled subtraction.
* `process_gpu1()`: takes 2 cv2.UMat images and performs scaled addition
* `process_gpu2()`: takes 1 combined Numpy array, converts it to two cv2.UMat images, and then performs scaled subtraction
* `process_gpu3()`: takes 1 combined Numpy array, converts it to two cv2.UMat images, and then performs scaled addition
* `process_cpu()`: takes 1 combined Numpy array and performs scaled subtraction
* `process_cpu1()`: takes 1 combined Numpy array and performs scaled addition
* `get_deforms()`: returns as Numpy arrays the deformation maps used for matching of left and right images

The performance of these different methods can be benchmarked with the `opencv_test` module in the `tests` directory. On a macbook pro with i7 processor at 2.2GHz and Intel Iris Pro graphics, the calibration calculation takes 1.2 secs (this only needs to be done at initialisation) and then processing individual images takes about 7.5ms. We have some evidence that this final processing step is quicker in C++ (~1ms) so ultimately it might be worth rewriting the processing step using the opencv C++ library directly. Some other processing methods have been added that show a significant (~3x) speed-up on this. Basically this is all depends on how the data to be processed is converted to the opencv UMat class for processing. The UMat class encompases data that is stored in GPU memory and will be processed using OPENCL. Different routines might see different speed-up depending on the hardware used.
 
Usage:

```python
import aurox_clarity.controller
import aurox_clarity.processor

ctrl = aurox_clarity.controller.Controller()
ctrl.switchOn()
ctrl.setCalibrationLED(aurox_clarity.controller.CALON)

# Take an image with the camera (not covered by this package)
calib_img = take_image()

proc = aurox_clarity.processor.Processor(calib_img)
# Calibration is successful in the absence of exceptions

ctrl.setCalibrationLED(aurox_clarity.controller.CALOFF)

img = take_image()

confocal_img = proc.process(img)

deform_X, deform_Y = proc.get_deforms()
```
