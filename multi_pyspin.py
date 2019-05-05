#!/usr/bin/env python

""" simple 'singleton' API for multiple cameras with PySpin library """

import os
import atexit
from contextlib import suppress

import yaml
import PySpin


# ------------------- #
# "attributes"        #
# ------------------- #


# Make sure a reference to system and system event handler exist
_SYSTEM = None
_SYSTEM_EVENT_HANDLER = None

# Maintain dictionary which keeps correspondences between camera serial and camera object
_CAM_DICT = {}


# ------------------- #
# "static" functions  #
# ------------------- #


def _node_cmd(cam, cam_attr_str, cam_method_str, pyspin_mode_str=None, cam_method_arg=None):
    """ Performs method on input cam attribute with optional access mode check """

    # Print command info
    info_str = 'Executing: "' + '.'.join([cam_attr_str, cam_method_str]) + '('
    if cam_method_arg is not None:
        info_str += str(cam_method_arg)
    print(info_str + ')"')

    # Get camera attribute
    cam_attr = cam
    cam_attr_str_split = cam_attr_str.split('.')
    for sub_cam_attr_str in cam_attr_str_split:
        cam_attr = getattr(cam_attr, sub_cam_attr_str)

    # Perform optional access mode check
    if pyspin_mode_str is not None:
        if cam_attr.GetAccessMode() != getattr(PySpin, pyspin_mode_str):
            raise RuntimeError('Access mode check failed for: "' + cam_attr_str + '" with mode: "' +
                               pyspin_mode_str + '".')

    # Format command argument in case it's a string containing a PySpin attribute
    if isinstance(cam_method_arg, str):
        cam_method_arg_split = cam_method_arg.split('.')
        if cam_method_arg_split[0] == 'PySpin':
            if len(cam_method_arg_split) == 2:
                cam_method_arg = getattr(PySpin, cam_method_arg_split[1])
            else:
                raise RuntimeError('Arguments containing nested PySpin arguments are currently not supported...')

    # Perform command
    if cam_method_arg is None:
        return getattr(cam_attr, cam_method_str)()
    else:
        return getattr(cam_attr, cam_method_str)(cam_method_arg)


def _setup(cam, yaml_path):
    """ This will setup (initialize + configure) input camera given a path to a yaml file """

    if not os.path.isfile(yaml_path):
        raise RuntimeError('"' + yaml_path + '" could not be found!')

    # Must Init() camera first
    cam.Init()

    # Load yaml file and grab init commands
    node_cmd_dicts = None
    with open(yaml_path, 'rb') as file:
        yaml_dict = yaml.load(file, Loader=yaml.SafeLoader)
        # Get commands from "init"
        if isinstance(yaml_dict, dict) and 'init' in yaml_dict:
            node_cmd_dicts = yaml_dict['init']

    # Perform init commands if they are provided
    if isinstance(node_cmd_dicts, list):
        # Iterate over commands
        for node_cmd_dict in node_cmd_dicts:
            # Get camera attribute string
            if isinstance(node_cmd_dict, dict):
                cam_attr_str = list(node_cmd_dict.keys())
                if len(cam_attr_str) == 1:
                    cam_attr_str = cam_attr_str[0]

                    # NOTE: I believe there should only be SetValue()'s and Execute()'s with RW access mode for
                    # initialization of camera (read only doesn't make sense and the write onlys that I've seen are
                    # mainly for rebooting the camera, which isn't necessary). If this is not the case, then the method
                    # and/or access mode(s) will need to be added to the yaml file.

                    # Get method argument (if it exists)
                    cam_method_arg = None
                    cam_method_dict = node_cmd_dict[cam_attr_str]
                    if isinstance(cam_method_dict, dict):
                        # Get method argument
                        if 'value' in cam_method_dict:
                            cam_method_arg = cam_method_dict['value']

                    # Get method
                    if cam_method_arg is not None:
                        # Assume this is a SetValue()
                        cam_method_str = 'SetValue'
                    else:
                        # Assume this is an Execute()
                        cam_method_str = 'Execute'

                    # Get mode
                    pyspin_mode_str = 'RW'

                    # Perform command
                    _node_cmd(cam,
                              cam_attr_str,
                              cam_method_str,
                              pyspin_mode_str,
                              cam_method_arg)
                else:
                    raise RuntimeError('Only one camera attribute per yaml "tick" is supported. '
                                       'Please fix: ' + str(cam_attr_str))


def _get_image(cam, *args):
    """ Gets image (and other info) from input camera """

    # Get image object
    image = cam.GetNextImage(*args)

    # Initialize image dict
    image_dict = {}

    # Ensure image is complete
    if not image.IsIncomplete():
        # Get data/metadata
        image_dict['data'] = image.GetNDArray()
        image_dict['timestamp'] = image.GetTimeStamp()
        image_dict['bitsperpixel'] = image.GetBitsPerPixel()

    # PySpin image goes out of scope here, so no need to explicitly release the image

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


def _handle_cam_arrival(serial):
    """ Handles adding a new camera """

    print('Camera "' + serial + '" connected.')

    # Add to serial dict
    _CAM_DICT[serial] = _SYSTEM.GetCameras().GetBySerial(serial)


def _handle_cam_removal(serial):
    """ Handles removing a new camera """

    print('Camera "' + serial + '" removed.')

    # Remove from serial dict
    _CAM_DICT.pop(serial, None)


def _get_cam(serial):
    """ Returns camera """

    if serial not in _CAM_DICT:
        raise RuntimeError('Camera "' + serial + '" not connected!')

    return _CAM_DICT[serial]


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

    print('Setting up camera "' + serial + '"...')

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


def node_cmd(serial, cam_attr_str, cam_method_str, pyspin_mode_str=None, cam_method_arg=None):
    """ Performs method on input cam attribute with optional access mode check """

    # This function allows running node commands without explicitly accessing the camera object, which is nice as the
    # caller doesn't need to worry about handling/clearing cam objects

    return _node_cmd(_get_and_validate_init_cam(serial),
                     cam_attr_str,
                     cam_method_str,
                     pyspin_mode_str,
                     cam_method_arg)


def get_gain(serial):
    """ Gets gain from camera """

    return node_cmd(serial, 'Gain', 'GetValue')


def set_gain(serial, gain):
    """ Sets gain for camera """

    node_cmd(serial, 'Gain', 'SetValue', 'RW', gain)


def get_exposure(serial):
    """ Gets exposure """

    return node_cmd(serial, 'ExposureTime', 'GetValue')


def set_exposure(serial, exposure):
    """ Sets exposure for camera """

    node_cmd(serial, 'ExposureTime', 'SetValue', 'RW', exposure)


def get_frame_rate(serial):
    """ Gets frame rate """

    return node_cmd(serial, 'AcquisitionFrameRate', 'GetValue')


def set_frame_rate(serial, frame_rate):
    """ Sets frame rate for cameras """

    node_cmd(serial, 'AcquisitionFrameRate', 'SetValue', 'RW', frame_rate)


def start_acquisition(serial):
    """ Starts acquisition of camera """

    _get_and_validate_init_cam(serial).BeginAcquisition()


def end_acquisition(serial):
    """ Ends acquisition of camera """

    _get_and_validate_init_cam(serial).EndAcquisition()


def get_image(serial, *args):
    """ Gets image from camera """

    # TODO: test speed of this function; make sure it can hit max FPS. If not, maybe add option to skip some validation

    return _get_image(_get_and_validate_streaming_cam(serial), *args)


# --------------------#
# "constructor"       #
# ------------------- #


class _SystemEventHandler(PySpin.InterfaceEvent):
    """ This class handles when cameras are added or removed """

    def __init__(self):
        super(_SystemEventHandler, self).__init__()

    def OnDeviceArrival(self, serial):
        _handle_cam_arrival(str(serial))

    def OnDeviceRemoval(self, serial):
        _handle_cam_removal(str(serial))


def _constructor():
    global _SYSTEM, _SYSTEM_EVENT_HANDLER, _CAM_DICT

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


_constructor()  # Should be called once when first imported - note that ipython with autoreload might break this


# --------------------#
# "destructor"        #
# ------------------- #


def _destructor():
    """ Handles the release of the PySpin System object """

    print('Cleaning up multi_pyspin...')

    # NOTE: it might actually be a nice feature to allow cameras to remain initialized and streaming after exiting...
    # Maybe come back to this later.

    # Clean up cameras
    for serial in list(_CAM_DICT):  # Use list() to cache since stuff is getting removed from dictionary in loop
        # End acquisition
        with suppress(Exception):
            end_acquisition(serial)

        # Deinit
        with suppress(Exception):
            deinit(serial)

        # Clear camera reference
        _CAM_DICT.pop(serial, None)

    # Debug output if system is still in use some how
    if _SYSTEM.IsInUse():
        print('System is still in use? How can this be? Printing all globals:')
        for name, value in globals().items():
            print(name, value)

    # PySpin system goes out of scope here, so no need to explicitly release the system


atexit.register(_destructor)
