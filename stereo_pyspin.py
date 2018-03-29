#!/usr/bin/env python

""" 'singleton' for setting up stereo cameras with PySpin library """

# pylint: disable=global-statement

import os
import yaml

import PySpin #pylint: disable=import-error

# ------------------- #
# "attributes"        #
# ------------------- #

# Default values
CAM_PRIMARY = None
CAM_SECONDARY = None

# ------------------- #
# "static" functions  #
# ------------------- #

def __cam_node_cmd(cam, cam_attr_str, cam_method_str, pyspin_mode_str, cam_method_arg=None):
    """ Performs cam_method on input cam/attribute with access mode check  """

    # First, get camera attribute
    cam_attr = cam
    cam_attr_str_split = cam_attr_str.split('.')
    for sub_cam_attr_str in cam_attr_str_split:
        cam_attr = getattr(cam_attr, sub_cam_attr_str)

    # Perform access mode check
    if cam_attr.GetAccessMode() != getattr(PySpin, pyspin_mode_str):
        raise RuntimeError('Access mode check failed for: "' + cam_attr_str + '" with mode: "' +
                           pyspin_mode_str + '".')

    # Print command info
    info_str = 'Executing: "' + '.'.join([cam_attr_str, cam_method_str] + '(')
    if cam_method_arg:
        info_str += str(cam_method_arg)
    print(info_str + ')"')

    # Format command argument in case it's a string containing a PySpin attribute
    if cam_method_arg and isinstance(cam_method_arg, str):
        cam_method_arg_split = cam_method_arg.split('.')
        if cam_method_arg_split[0] == 'PySpin':
            if len(cam_method_arg_split) == 2:
                cam_method_arg = getattr(PySpin, cam_method_arg_split[1])
            else:
                raise RuntimeError('Arguments containing nested PySpin arguments are currently not '
                                   'supported...')

    # Perform command
    if not cam_method_arg: #pylint: disable=no-else-return
        return getattr(cam_attr, cam_method_str)()
    else:
        return getattr(cam_attr, cam_method_str)(cam_method_arg)

def __find_cam(cam_serial_match):
    """ returns PySpin camera object given a serial number """

    # Get system
    system = PySpin.System.GetInstance()

    # Retrieve cameras from the system
    cam_list = system.GetCameras()

    # Find camera matching serial
    cam_match = None
    for i in range(cam_list.GetSize()):
        # Get camera
        cam = cam_list.GetByIndex(i)

        # Read serial number
        cam_serial = int(__cam_node_cmd(cam, 'TLDevice.DeviceSerialNumber', 'GetValue', 'RO'))
        if cam_serial == cam_serial_match:
            cam_match = cam

    # Check to see if match was found
    if not cam_match:
        raise RuntimeError('Could not find camera with serial: "' + str(cam_serial_match) + '".')

    return cam_match

def __init_cam(cam, yaml_path=None):
    """ initializes input camera given optional node command list yaml file """

    if yaml_path and not os.path.isfile(yaml_path):
        raise RuntimeError('"' + yaml_path + '" could not be found!')

    # Must Init() camera first
    cam.Init()

    # Load yaml file (if provided) then run commands specified in the yaml file
    if yaml_path:
        with open(yaml_path, 'rb') as file:
            node_cmd_list = yaml.load(file)
            for node_cmd in node_cmd_list:
                # Get camera attribute string
                cam_attr_str = list(node_cmd.keys())
                if len(cam_attr_str) == 1:
                    cam_attr_str = cam_attr_str[0]
                    cam_method_arg = node_cmd[cam_attr_str]
                    if not cam_method_arg:
                        # If no argument is specified, then its assumed this is an "Execute"
                        __cam_node_cmd(cam, cam_attr_str, 'Execute', 'WO')
                    else:
                        # Make sure only key is a string named "value"
                        cam_method_arg_key = list(cam_method_arg.keys())
                        if len(cam_method_arg_key) == 1 and cam_method_arg_key[0] == 'value':
                            # If argument is provided, its assumed this is a "SetValue"
                            __cam_node_cmd(cam,
                                           cam_attr_str,
                                           'SetValue',
                                           'RW',
                                           cam_method_arg[cam_method_arg_key[0]])
                        else:
                            raise RuntimeError('Only a single argument key named "value" is '
                                               'supported; For camera attribute: "' + cam_attr_str +
                                               '" the following was set: ' +
                                               str(cam_method_arg_key))
                else:
                    raise RuntimeError('Only one camera attribute per "tick" is supported. '
                                       'Please fix: ' + str(cam_attr_str))

# ------------------- #
# "public" functions  #
# ------------------- #

def find_pimary(cam_serial):
    """ Finds primary camera """
    global CAM_PRIMARY

    CAM_PRIMARY = __find_cam(cam_serial)

def find_secondary(cam_serial):
    """ Finds secondary camera """
    global CAM_SECONDARY

    CAM_SECONDARY = __find_cam(cam_serial)

def init_primary(yaml_path=None):
    """ Initializes primary camera using optional yaml file """
    global CAM_PRIMARY

    if not CAM_PRIMARY:
        raise RuntimeError('Primary camera has not been found yet!')

    __init_cam(CAM_PRIMARY, yaml_path)

def init_secondary(yaml_path=None):
    """ Initializes secondary camera using optional yaml file """
    global CAM_SECONDARY

    if not CAM_SECONDARY:
        raise RuntimeError('Secondary camera has not been found yet!')

    __init_cam(CAM_SECONDARY, yaml_path)

def start_acquisition_primary():
    """ Starts acquisition of primary camera """
    global CAM_PRIMARY

    if not CAM_PRIMARY:
        raise RuntimeError('Primary camera has not been found yet!')

    CAM_PRIMARY.BeginAcquisition()

def start_acquisition_secondary():
    """ Starts acquisition of secondary camera """
    global CAM_SECONDARY

    if not CAM_SECONDARY:
        raise RuntimeError('Secondary camera has not been found yet!')

    CAM_SECONDARY.BeginAcquisition()

def set_frame_rate(frame_rate):
    """ Sets frame rate for both cameras """
    global CAM_PRIMARY, CAM_SECONDARY

    if not CAM_PRIMARY:
        raise RuntimeError('Primary camera has not been found yet!')

    if not CAM_SECONDARY:
        raise RuntimeError('Secondary camera has not been found yet!')

    __cam_node_cmd(CAM_PRIMARY, 'AcquisitionFrameRate', 'SetValue', 'RW', frame_rate)
    __cam_node_cmd(CAM_SECONDARY, 'AcquisitionFrameRate', 'SetValue', 'RW', frame_rate)

def set_exposure(exposure):
    """ Sets exposure for both cameras """
    global CAM_PRIMARY, CAM_SECONDARY

    if not CAM_PRIMARY:
        raise RuntimeError('Primary camera has not been found yet!')

    if not CAM_SECONDARY:
        raise RuntimeError('Secondary camera has not been found yet!')

    __cam_node_cmd(CAM_PRIMARY, 'ExposureTime', 'SetValue', 'RW', exposure)
    __cam_node_cmd(CAM_SECONDARY, 'ExposureTime', 'SetValue', 'RW', exposure)

def set_gain(gain):
    """ Sets gain for both cameras """
    global CAM_PRIMARY, CAM_SECONDARY

    if not CAM_PRIMARY:
        raise RuntimeError('Primary camera has not been found yet!')

    if not CAM_SECONDARY:
        raise RuntimeError('Secondary camera has not been found yet!')

    __cam_node_cmd(CAM_PRIMARY, 'Gain', 'SetValue', 'RW', gain)
    __cam_node_cmd(CAM_SECONDARY, 'Gain', 'SetValue', 'RW', gain)

def end_acquisition_primary():
    """ Ends acquisition of primary camera """
    global CAM_PRIMARY

    if not CAM_PRIMARY:
        raise RuntimeError('Primary camera has not been found yet!')

    CAM_PRIMARY.EndAcquisition()

def end_acquisition_secondary():
    """ Ends acquisition of secondary camera """
    global CAM_SECONDARY

    if not CAM_SECONDARY:
        raise RuntimeError('Secondary camera has not been found yet!')

    CAM_SECONDARY.EndAcquisition()

def deinit_primary():
    """ De-initializes primary camera """
    global CAM_PRIMARY

    if not CAM_PRIMARY:
        raise RuntimeError('Primary camera has not been found yet!')

    CAM_PRIMARY.DeInit()

def deinit_secondary():
    """ De-initializes secondary camera """
    global CAM_SECONDARY

    if not CAM_SECONDARY:
        raise RuntimeError('Secondary camera has not been found yet!')

    CAM_SECONDARY.DeInit()
