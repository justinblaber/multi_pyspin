#!/usr/bin/env python

""" simple 'singleton' API for multiple cameras with PySpin library """

# Designed and tested on:
#   -camera:                        Blackfly S BFS-U3-32S4M
#   -firmware:                      1804.0.113.3
#   -spinnaker version:             spinnaker-1.23.0.27-amd64-Ubuntu18.04
#   -spinnaker python version:      spinnaker_python-1.23.0.27-cp36-cp36m-linux_x86_64

import os
import atexit
import statistics
from datetime import datetime
from contextlib import suppress

import yaml

import PySpin


# ------------------- #
# "attributes"        #
# ------------------- #


# Make sure a reference to system and system event handler exist
_SYSTEM = None
_SYSTEM_EVENT_HANDLER = None

# Maintain dictionary which keeps correspondences between camera serial and camera stuff (camera object, timestamp
# offset, etc...)
_SERIAL_DICT = {}

# Set number of iterations used to compute timestamp offset
_TIMESTAMP_OFFSET_ITERATIONS = 20


# ------------------- #
# "static" functions  #
# ------------------- #


def _node_cmd(cam, cam_node_str, cam_method_str, pyspin_mode_str=None, cam_node_arg=None):
    """ Performs method on input cam node with optional access mode check """

    # Print command info
    info_str = cam.GetUniqueID() + ' - executing: "' + '.'.join([cam_node_str, cam_method_str]) + '('
    if cam_node_arg is not None:
        info_str += str(cam_node_arg)
    print(info_str + ')"')

    # Get camera node
    cam_node = cam
    cam_node_str_split = cam_node_str.split('.')
    for sub_cam_node_str in cam_node_str_split:
        cam_node = getattr(cam_node, sub_cam_node_str)

    # Perform optional access mode check
    if pyspin_mode_str is not None:
        if cam_node.GetAccessMode() != getattr(PySpin, pyspin_mode_str):
            raise RuntimeError('Access mode check failed for: "' + cam_node_str + '" with mode: "' +
                               pyspin_mode_str + '".')

    # Format command argument in case it's a string containing a PySpin attribute
    if isinstance(cam_node_arg, str):
        cam_node_arg_split = cam_node_arg.split('.')
        if cam_node_arg_split[0] == 'PySpin':
            if len(cam_node_arg_split) == 2:
                cam_node_arg = getattr(PySpin, cam_node_arg_split[1])
            else:
                raise RuntimeError('Arguments containing nested PySpin attributes are currently not supported...')

    # Perform command
    if cam_node_arg is None:
        return getattr(cam_node, cam_method_str)()
    else:
        return getattr(cam_node, cam_method_str)(cam_node_arg)


def _setup(cam, yaml_path):
    """ This will setup (initialize + configure) input camera given a path to a yaml file """

    if not os.path.isfile(yaml_path):
        raise RuntimeError('"' + yaml_path + '" could not be found!')

    # Print setup
    print(cam.GetUniqueID() + ' - setting up...')

    # Init camera
    cam.Init()

    # Load yaml file and grab init commands
    node_cmd_dicts = None
    with open(yaml_path, 'rb') as file:
        yaml_dict = yaml.load(file, Loader=yaml.SafeLoader)
        # Get commands from "init"
        if isinstance(yaml_dict, dict) and 'init' in yaml_dict:
            node_cmd_dicts = yaml_dict['init']

    # Perform node commands if they are provided
    if isinstance(node_cmd_dicts, list):
        # Iterate over commands
        for node_cmd_dict in node_cmd_dicts:
            if isinstance(node_cmd_dict, dict):
                # Get camera node string
                cam_node_str = list(node_cmd_dict.keys())
                if len(cam_node_str) == 1:
                    cam_node_str = cam_node_str[0]

                    # NOTE: I believe there should only be SetValue()'s and Execute()'s with RW access mode for
                    # initialization of camera (read only doesn't make sense and the write onlys that I've seen are
                    # mainly for rebooting the camera, which isn't necessary). If this is not the case, then the method
                    # and/or access mode(s) will need to be added to the yaml file.

                    # Get node argument (if it exists)
                    cam_node_arg = None
                    cam_node_dict = node_cmd_dict[cam_node_str]
                    if isinstance(cam_node_dict, dict) and 'value' in cam_node_dict:
                        cam_node_arg = cam_node_dict['value']

                    # Get method
                    if cam_node_arg is not None:
                        # Assume this is a SetValue()
                        cam_method_str = 'SetValue'
                    else:
                        # Assume this is an Execute()
                        cam_method_str = 'Execute'

                    # Get mode - Assume this is RW
                    pyspin_mode_str = 'RW'

                    # Perform command
                    _node_cmd(cam,
                              cam_node_str,
                              cam_method_str,
                              pyspin_mode_str,
                              cam_node_arg)
                else:
                    raise RuntimeError('Only one camera node per yaml "tick" is supported. '
                                       'Please fix: ' + str(cam_node_str))


def _compute_timestamp_offset(cam, timestamp_offset_iterations):
    """ Gets timestamp offset in seconds from input camera """

    # This method is required because the timestamp stored in the camera is relative to when it was powered on, so an
    # offset needs to be applied to get it into epoch time; from tests I've done, this appears to be accurate to ~1e-3
    # seconds.

    timestamp_offsets = []
    for i in range(timestamp_offset_iterations):
        # Latch timestamp. This basically "freezes" the current camera timer into a variable that can be read with
        # TimestampLatchValue()
        cam.TimestampLatch.Execute()

        # Compute timestamp offset in seconds; note that timestamp latch value is in nanoseconds
        timestamp_offset = datetime.now().timestamp() - cam.TimestampLatchValue.GetValue()/1e9

        # Append
        timestamp_offsets.append(timestamp_offset)

    # Return the median value
    return statistics.median(timestamp_offsets)


def _get_image(cam, timestamp_offset, *args):
    """ Gets image (and other info) from input camera; caller should handle releasing the image """

    # Get image
    image = cam.GetNextImage(*args)  # args is most likely a timeout in case trigger is set

    # Initialize image dict
    image_dict = {}

    # Ensure image is complete
    if not image.IsIncomplete():
        # Get data/metadata
        image_dict['image'] = image                                             # image
        image_dict['timestamp'] = timestamp_offset + image.GetTimeStamp()/1e9   # timestamp in seconds
        image_dict['bitsperpixel'] = image.GetBitsPerPixel()                    # bits per pixel
        image_dict['frameid'] = image.GetFrameID()                              # frame id

    return image_dict


def _validate_cam(cam, serial):
    """ Checks to see if camera is valid """

    if not cam.IsValid():
        raise RuntimeError('Camera "' + serial + '" is not valid.')


def _validate_cam_init(cam, serial):
    """ Checks to see if camera is valid and initialized """

    _validate_cam(cam, serial)

    if not cam.IsInitialized():
        raise RuntimeError('Camera "' + serial + '" is not initialized.')


def _validate_cam_streaming(cam, serial):
    """ Checks to see if camera is valid, initialized, and streaming """

    _validate_cam_init(cam, serial)

    if not cam.IsStreaming():
        raise RuntimeError('Camera "' + serial + '" is not streaming.')


# ------------------- #
# "private" methods   #
# ------------------- #


def _validate_serial(serial):
    """ Checks to see if serial is valid """

    if serial not in _SERIAL_DICT:
        raise RuntimeError('Camera "' + serial + '" not valid, please connect or reconnect!')


def _handle_cam_arrival(serial):
    """ Handles adding a camera """

    print(serial + ' - connected')

    # Get camera object
    cam = _SYSTEM.GetCameras().GetBySerial(serial)

    # Get timestamp offset; must initialize first before timestamp can be computed
    cam.Init()
    timestamp_offset = _compute_timestamp_offset(cam, _TIMESTAMP_OFFSET_ITERATIONS)

    # Add cam stuff to dict
    _SERIAL_DICT[serial] = {'cam': cam, 'timestamp_offset': timestamp_offset}


def _handle_cam_removal(serial):
    """ Handles removing a camera """

    print(serial + ' - removed')

    # Remove cam stuff from dict
    _SERIAL_DICT.pop(serial, None)


def _get_cam(serial):
    """ Returns camera """

    _validate_serial(serial)

    return _SERIAL_DICT[serial]['cam']


def _get_timestamp_offset(serial):
    """ Returns camera timestamp offset """

    _validate_serial(serial)

    return _SERIAL_DICT[serial]['timestamp_offset']


def _get_and_validate_cam(serial):
    """ Validates camera then returns it """

    cam = _get_cam(serial)
    _validate_cam(cam, serial)

    return cam


def _get_and_validate_init_cam(serial):
    """ Validates initialization of camera then returns it """

    cam = _get_cam(serial)
    _validate_cam_init(cam, serial)

    return cam


def _get_and_validate_streaming_cam(serial):
    """ Validates streaming of camera then returns it """

    cam = _get_cam(serial)
    _validate_cam_streaming(cam, serial)

    return cam


# ------------------- #
# "public" methods    #
# ------------------- #


def setup(yaml_path):
    """ This will setup (initialize + configure) a camera given a yaml configuration file """

    # Get serial from yaml file
    with open(yaml_path, 'rb') as file:
        yaml_dict = yaml.load(file, Loader=yaml.SafeLoader)
        if isinstance(yaml_dict, dict) and 'serial' in yaml_dict:
            # yaml might cast serial to number
            serial = str(yaml_dict['serial'])
        else:
            raise RuntimeError('Invalid yaml file: "' + yaml_path + '". Missing "serial" field.')

    # Setup cam
    _setup(_get_and_validate_cam(serial), yaml_path)

    # Return serial
    return serial


def init(serial):
    """ Initializes camera """

    _get_and_validate_cam(serial).Init()


def deinit(serial):
    """ De-initializes camera """

    _get_and_validate_cam(serial).DeInit()


def get_gain(serial):
    """ Gets gain from camera """

    return node_cmd(serial, 'Gain', 'GetValue')


def set_gain(serial, gain):
    """ Sets gain for camera """

    node_cmd(serial, 'Gain', 'SetValue', 'RW', gain)


def get_exposure(serial):
    """ Gets exposure from camera """

    return node_cmd(serial, 'ExposureTime', 'GetValue')


def set_exposure(serial, exposure):
    """ Sets exposure for camera """

    node_cmd(serial, 'ExposureTime', 'SetValue', 'RW', exposure)


def get_frame_rate(serial):
    """ Gets frame rate from camera """

    return node_cmd(serial, 'AcquisitionFrameRate', 'GetValue')


def set_frame_rate(serial, frame_rate):
    """ Sets frame rate for camera """

    node_cmd(serial, 'AcquisitionFrameRate', 'SetValue', 'RW', frame_rate)


def start_acquisition(serial):
    """ Starts acquisition of camera """

    _get_and_validate_init_cam(serial).BeginAcquisition()


def end_acquisition(serial):
    """ Ends acquisition of camera """

    _get_and_validate_init_cam(serial).EndAcquisition()


def get_image(serial, *args):
    """ Gets image from camera """

    return _get_image(_get_and_validate_streaming_cam(serial),
                      _get_timestamp_offset(serial),
                      *args)


def node_cmd(serial, cam_node_str, cam_method_str, pyspin_mode_str=None, cam_node_arg=None):
    """ Performs method on input cam node with optional access mode check """

    # This function allows running node commands without explicitly accessing the camera object, which is nice as the
    # caller doesn't need to worry about handling/clearing cam objects

    return _node_cmd(_get_and_validate_init_cam(serial),
                     cam_node_str,
                     cam_method_str,
                     pyspin_mode_str,
                     cam_node_arg)


def update_timestamp_offset(serial):
    """ Updates timestamp offset """

    # I've included this function because I assume if the camera has been running for quite a bit of time since the
    # offset was last computed, there might be some error.

    _validate_serial(serial)

    _SERIAL_DICT[serial]['timestamp_offset'] = _compute_timestamp_offset(_get_and_validate_init_cam(serial),
                                                                         _TIMESTAMP_OFFSET_ITERATIONS)


# --------------------#
# Event handler       #
# ------------------- #


class _SystemEventHandler(PySpin.InterfaceEvent):
    """ This class handles when cameras are added or removed """

    def __init__(self):
        super(_SystemEventHandler, self).__init__()

    def OnDeviceArrival(self, serial):
        _handle_cam_arrival(str(serial))

    def OnDeviceRemoval(self, serial):
        _handle_cam_removal(str(serial))


# --------------------#
# "constructor"       #
# ------------------- #


def _constructor():
    global _SYSTEM, _SYSTEM_EVENT_HANDLER, _SERIAL_DICT

    # Set system
    _SYSTEM = PySpin.System.GetInstance()

    # Set cameras
    cams = _SYSTEM.GetCameras()
    for cam in cams:
        # Treat them as new arrivals
        _handle_cam_arrival(cam.GetUniqueID())

    # Store event handler
    _SYSTEM_EVENT_HANDLER = _SystemEventHandler()

    # Register event handler
    _SYSTEM.RegisterInterfaceEvent(_SYSTEM_EVENT_HANDLER)

    # cams should clear itself after going out of scope


_constructor()  # Should be called once when first imported


# --------------------#
# "destructor"        #
# ------------------- #


def _destructor():
    """ Handles the release of the PySpin System object """

    print('Cleaning up multi_pyspin...')

    # Clean up cameras
    for serial in list(_SERIAL_DICT):  # Use list() to cache since stuff is getting removed from dictionary in loop
        # End acquisition
        with suppress(Exception):
            end_acquisition(serial)

        # Deinit
        with suppress(Exception):
            deinit(serial)

        # Clear camera stuff
        _SERIAL_DICT.pop(serial, None)

    # Debug output if system is still in use some how
    if _SYSTEM.IsInUse():
        print('System is still in use? How can this be? Printing all globals:')
        for name, value in globals().items():
            print(name, value)

    # PySpin system goes out of scope here, so no need to explicitly release the system


atexit.register(_destructor)
