#!/usr/bin/env python

""" 'singleton' for setting up stereo cameras with PySpin library """

import os
import atexit
from warnings import warn

import yaml
import PySpin

# ------------------- #
# "attributes"        #
# ------------------- #

# Initialize system; if system goes out of scope it will throw an error if there
# are any references to cameras remaining
__SYSTEM = PySpin.System.GetInstance()

__SERIAL_PRIMARY = None
__SERIAL_SECONDARY = None

__CAM_PRIMARY = None
__CAM_SECONDARY = None

# --------------------#
# destructor          #
# ------------------- %

# This ensures camera references are removed before releasing the system
def __destructor():
    """ Removes references to cameras before releasing system """
    global __CAM_PRIMARY, __CAM_SECONDARY # pylint: disable=global-statement

    print('Exiting stereo pyspin...')

    # Clear cameras
    if __CAM_PRIMARY is not None:
        del __CAM_PRIMARY
    if __CAM_SECONDARY is not None:
        del __CAM_SECONDARY

    # Now clear system
    __SYSTEM.ReleaseInstance()

atexit.register(__destructor)

# ------------------- #
# "static" functions  #
# ------------------- #

def __get_serial(cam_serial_or_yaml_path):
    """ cam_serial_or_yaml_path is either a cam serial or a path to a yaml file """

    # NOTE: I'm not sure if serial numbers can contain letters; If so, if the
    # serial number happens to end with ".yaml" this can fail. The
    # DeviceSerialNumber method returns a string, so I'm assuming letters are
    # possible.

    if cam_serial_or_yaml_path.endswith('.yaml'):
        # This is a yaml path
        yaml_path = cam_serial_or_yaml_path
        with open(yaml_path, 'rb') as file:
            cam_dict = yaml.load(file)
            if isinstance(cam_dict, dict) and 'serial' in cam_dict:
                # yaml might cast serial to number
                cam_serial = str(cam_dict['serial'])
            else:
                raise RuntimeError('Invalid yaml file: "' + yaml_path +
                                   '". Missing "serial" field.')
    else:
        # This is a cam serial
        cam_serial = cam_serial_or_yaml_path

    return cam_serial

def __cam_node_cmd(cam, cam_attr_str, cam_method_str, pyspin_mode_str=None, cam_method_arg=None):
    """ Performs cam_method on input cam and attribute with optional access mode check  """

    # First, get camera attribute
    cam_attr = cam
    cam_attr_str_split = cam_attr_str.split('.')
    for sub_cam_attr_str in cam_attr_str_split:
        cam_attr = getattr(cam_attr, sub_cam_attr_str)

    # Print command info
    info_str = 'Executing: "' + '.'.join([cam_attr_str, cam_method_str]) + '('
    if cam_method_arg is not None:
        info_str += str(cam_method_arg)
    print(info_str + ')"')

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
                raise RuntimeError('Arguments containing nested PySpin arguments are currently not '
                                   'supported...')

    # Perform command
    if cam_method_arg is None: #pylint: disable=no-else-return
        return getattr(cam_attr, cam_method_str)()
    else:
        return getattr(cam_attr, cam_method_str)(cam_method_arg)

def __find_cam(cam_serial):
    """ returns PySpin camera object given a serial number """

    # Retrieve cameras from the system
    cam_list = __SYSTEM.GetCameras()

    # Find camera matching serial
    cam_match = None
    for i in range(cam_list.GetSize()):
        # Get camera
        cam = cam_list.GetByIndex(i)

        # Compare serial number
        if cam_serial == __cam_node_cmd(cam, 'TLDevice.DeviceSerialNumber', 'GetValue', 'RO'):
            # This is a match, so exit loop
            cam_match = cam
            break

    # Check to see if match was found
    if cam_match is None:
        raise RuntimeError('Could not find camera with serial: "' + str(cam_serial) + '".')

    return cam_match

def __init_cam(cam, yaml_path=None): # pylint: disable=too-many-branches
    """ Initializes input camera given optional path to yaml file """

    if yaml_path is not None and not os.path.isfile(yaml_path):
        raise RuntimeError('"' + yaml_path + '" could not be found!')

    # Must Init() camera first
    cam.Init()

    # Load yaml file (if provided) and grab (optional) init commands
    node_cmd_list = None
    if yaml_path is not None:
        with open(yaml_path, 'rb') as file:
            cam_dict = yaml.load(file)
            # Get commands from "init"
            if isinstance(cam_dict, dict) and 'init' in cam_dict:
                node_cmd_list = cam_dict['init']

    # Perform init commands if they are provided
    if isinstance(node_cmd_list, list): # pylint: disable=too-many-nested-blocks
        # Iterate over commands
        for node_cmd in node_cmd_list:
            # Get camera attribute string
            if isinstance(node_cmd, dict):
                cam_attr_str = list(node_cmd.keys())
                if len(cam_attr_str) == 1:
                    cam_attr_str = cam_attr_str[0]

                    # Get optional method attributes
                    cam_method_arg = None
                    pyspin_mode_str = None

                    cam_method_attributes = node_cmd[cam_attr_str]
                    if isinstance(cam_method_attributes, dict):
                        # Get method argument
                        if 'value' in cam_method_attributes:
                            cam_method_arg = cam_method_attributes['value']

                        # Get access mode
                        if 'access' in cam_method_attributes:
                            pyspin_mode_str = cam_method_attributes['access']

                    # NOTE: I believe there should only be SetValue()'s and Execute()'s for
                    # initialization of camera. If this is not the case, then the method will
                    # need to be added to the yaml file.

                    # Get method
                    if cam_method_arg is not None:
                        # Assume this is a SetValue()
                        cam_method_str = 'SetValue'
                    else:
                        # Assume this is an Execute()
                        cam_method_str = 'Execute'

                    # Perform command
                    __cam_node_cmd(cam,
                                   cam_attr_str,
                                   cam_method_str,
                                   pyspin_mode_str,
                                   cam_method_arg)
                else:
                    raise RuntimeError('Only one camera attribute per "tick" is supported. '
                                       'Please fix: ' + str(cam_attr_str))

def __get_image(cam):
    """ Gets image as a numpy array from input camera """

    # Get image object
    image = cam.GetNextImage()

    # Initialize image data
    image_data = None

    # Ensure image is complete
    if not image.IsIncomplete():
        # Reshape into array
        image_data = image.GetData()
        image_data = image_data.reshape(image.GetHeight(), image.GetWidth())

        # Release image
        image.Release()

    return image_data

# ------------------- #
# "private" method    #
# ------------------- #

def __get_cam_primary():
    """ Returns primary camera """

    if __CAM_PRIMARY is None:
        raise RuntimeError('Primary camera has not been found yet!')

    return __CAM_PRIMARY

def __get_cam_secondary():
    """ Returns secondary camera """

    if __CAM_SECONDARY is None:
        raise RuntimeError('Secondary camera has not been found yet!')

    return __CAM_SECONDARY

# ------------------- #
# "public" methods    #
# ------------------- #

def find_primary(cam_serial_or_yaml_path):
    """ Finds primary camera """
    global __CAM_PRIMARY, __SERIAL_PRIMARY # pylint: disable=global-statement

    __SERIAL_PRIMARY = __get_serial(cam_serial_or_yaml_path)
    __CAM_PRIMARY = __find_cam(__SERIAL_PRIMARY)

    print('Found primary camera with serial: ' + __SERIAL_PRIMARY)

def find_secondary(cam_serial_or_yaml_path):
    """ Finds secondary camera """
    global __CAM_SECONDARY, __SERIAL_SECONDARY # pylint: disable=global-statement

    __SERIAL_SECONDARY = __get_serial(cam_serial_or_yaml_path)
    __CAM_SECONDARY = __find_cam(__SERIAL_SECONDARY)

    print('Found secondary camera with serial: ' + __SERIAL_SECONDARY)

def get_serial_primary():
    """ Returns primary camera serial number """

    if __SERIAL_PRIMARY is None:
        raise RuntimeError('Primary camera has not been found yet!')

    return __SERIAL_PRIMARY

def get_serial_secondary():
    """ Returns secondary camera serial number """

    if __SERIAL_SECONDARY is None:
        raise RuntimeError('Secondary camera has not been found yet!')

    return __SERIAL_SECONDARY

def get_frame_rate():
    """ Gets frame rate """

    frame_rate_primary = __cam_node_cmd(__get_cam_primary(),
                                        'AcquisitionFrameRate',
                                        'GetValue')
    frame_rate_secondary = __cam_node_cmd(__get_cam_secondary(),
                                          'AcquisitionFrameRate',
                                          'GetValue')

    if frame_rate_primary != frame_rate_secondary:
        warn('Primary and secondary frame rate are different: ' +
             str([frame_rate_primary, frame_rate_secondary]) +
             '. Returning the average value.')

        return (frame_rate_primary+frame_rate_secondary)/2

    return frame_rate_primary

def get_gain():
    """ Gets gain """

    gain_primary = __cam_node_cmd(__get_cam_primary(), 'Gain', 'GetValue')
    gain_secondary = __cam_node_cmd(__get_cam_secondary(), 'Gain', 'GetValue')

    if gain_primary != gain_secondary:
        warn('Primary and secondary gain are different: ' +
             str([gain_primary, gain_secondary]) +
             '. Returning the average value.')

        return (gain_primary+gain_secondary)/2

    return gain_primary

def get_exposure():
    """ Gets exposure """

    exposure_primary = __cam_node_cmd(__get_cam_primary(), 'ExposureTime', 'GetValue')
    exposure_secondary = __cam_node_cmd(__get_cam_secondary(), 'ExposureTime', 'GetValue')

    if exposure_primary != exposure_secondary:
        warn('Primary and secondary exposure are different: ' +
             str([exposure_primary, exposure_secondary]) +
             '. Returning the average value.')

        return (exposure_primary+exposure_secondary)/2

    return exposure_primary

def get_image_primary():
    """ Gets image from primary camera """

    return __get_image(__get_cam_primary())

def get_image_secondary():
    """ Gets image from secondary camera """

    return __get_image(__get_cam_secondary())

def set_frame_rate(frame_rate):
    """ Sets frame rate for both cameras """

    __cam_node_cmd(__get_cam_primary(), 'AcquisitionFrameRate', 'SetValue', 'RW', frame_rate)
    __cam_node_cmd(__get_cam_secondary(), 'AcquisitionFrameRate', 'SetValue', 'RW', frame_rate)

def set_gain(gain):
    """ Sets gain for both cameras """

    __cam_node_cmd(__get_cam_primary(), 'Gain', 'SetValue', 'RW', gain)
    __cam_node_cmd(__get_cam_secondary(), 'Gain', 'SetValue', 'RW', gain)

def set_exposure(exposure):
    """ Sets exposure for both cameras """

    __cam_node_cmd(__get_cam_primary(), 'ExposureTime', 'SetValue', 'RW', exposure)
    __cam_node_cmd(__get_cam_secondary(), 'ExposureTime', 'SetValue', 'RW', exposure)

def init_primary(yaml_path=None):
    """ Initializes primary camera using optional yaml file """

    __init_cam(__get_cam_primary(), yaml_path)

def init_secondary(yaml_path=None):
    """ Initializes secondary camera using optional yaml file """

    __init_cam(__get_cam_secondary(), yaml_path)

def start_acquisition_primary():
    """ Starts acquisition of primary camera """

    __get_cam_primary().BeginAcquisition()

def start_acquisition_secondary():
    """ Starts acquisition of secondary camera """

    __get_cam_secondary().BeginAcquisition()

def end_acquisition_primary():
    """ Ends acquisition of primary camera """

    __get_cam_primary().EndAcquisition()

def end_acquisition_secondary():
    """ Ends acquisition of secondary camera """

    __get_cam_secondary().EndAcquisition()

def deinit_primary():
    """ De-initializes primary camera """

    __get_cam_primary().DeInit()

def deinit_secondary():
    """ De-initializes secondary camera """

    __get_cam_secondary().DeInit()
