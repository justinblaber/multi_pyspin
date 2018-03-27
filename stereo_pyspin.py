#!/usr/bin/env python

""" 'singleton' for setting up stereo cameras with PySpin library """

# pylint: disable=global-statement,bad-whitespace,line-too-long

import os
import yaml
import PySpin #pylint: disable=import-error

# ------------------- #
# "attributes"        #
# ------------------- #

# Default values
CAM_PRIMARY = None
CAM_SECONDARY = None
CAM_FRAME_RATE = None
CAM_EXPOSURE = None
CAM_GAIN = None

# ------------------- #
# "static" functions  #
# ------------------- #

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
        if cam.TLDevice.DeviceSerialNumber.GetAccessMode() == PySpin.RO:
            cam_serial = int(cam.TLDevice.DeviceSerialNumber.GetValue())
            if cam_serial == cam_serial_match:
                cam_match = cam

    # Check to see if match was found
    if not cam_match:
        raise RuntimeError('Could not find camera with serial: "' + str(cam_serial_match) + '". Serial is either wrong or camera was busy.')

    return cam_match

def __cam_node_cmd(cam, cam_attr_str, cam_method_str, pyspin_mode_str, cam_method_arg=None):
    """ Performs cam_method (with optional argument) on input cam/attribute with access mode check  """

    # First, get camera attribute
    cam_attr = cam
    cam_attr_str_split = cam_attr_str.split('.')
    for sub_cam_attr_str in cam_attr_str_split:
        cam_attr = getattr(cam_attr, sub_cam_attr_str)

    # Perform access mode check
    if cam_attr.GetAccessMode() != getattr(PySpin, pyspin_mode_str):
        raise RuntimeError('Access mode check failed for: "' + cam_attr_str + '" with mode: "' + pyspin_mode_str + '".')

    # Print command info
    info_str = 'Executing: "' + '.'.join([cam_attr_str,cam_method_str])
    if cam_method_arg:
        info_str += '(' + str(cam_method_arg) + ')'
    print(info_str + '"')

    # Format command argument in case it's a string containing a PySpin attribute
    if cam_method_arg and isinstance(cam_method_arg, str):
        cam_method_arg_split = cam_method_arg.split('.')
        if cam_method_arg_split[0] == 'PySpin':
            if len(cam_method_arg_split) == 2:
                cam_method_arg = getattr(PySpin, cam_method_arg_split[1])
            else:
                raise RuntimeError('Arguments containing nested PySpin arguments are currently not supported...')

    # Perform command
    if not cam_method_arg:
        getattr(cam_attr,cam_method_str)()
    else:
        getattr(cam_attr,cam_method_str)(cam_method_arg)

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

def init_primary(yaml_path):
    """ Initializes primary camera using yaml file """
    global CAM_PRIMARY

    if not CAM_PRIMARY:
        raise RuntimeError('Primary camera has not been found yet!')

    if not os.path.isfile(yaml_path):
        raise RuntimeError('"' + yaml_path + '" could not be found!')

    # Load yaml file then run commands
    with open(yaml_path, 'rb') as file:
        cmd_list = yaml.load(file)
        for cmd in cmd_list:
            print(cmd)

"""
def __deinit_secondary(cam):

    # Execute the following in the following order
    cmd_list = [
        ['EndAcquisition',                             None,                                         None], # Ends acquisition
        ['UserSetSelector.SetValue',                   'PySpin.UserSetDefault_Default',              'RW'], # Set default user set
        ['UserSetLoad.Execute',                        None,                                         'WO'], # Load default user set
        ['DeInit',                                     None,                                         None], # De-initializes camera
    ]
    __cam_exec_cmd_list(cam, cmd_list)

def __deinit_primary(cam):

    # Execute the following in the following order
    cmd_list = [
        ['EndAcquisition',                             None,                                         None], # Ends acquisition
        ['UserSetSelector.SetValue',                   'PySpin.UserSetDefault_Default',              'RW'], # Set default user set
        ['UserSetLoad.Execute',                        None,                                         'WO'], # Load default user set
        ['DeInit',                                     None,                                         None], # De-initializes camera
    ]
    __cam_exec_cmd_list(cam, cmd_list)

    # Initialize secondary camera first to put it into trigger mode which will wait on primary camera
    print("Initializing secondary camera...")
    __init_secondary(CAM_SECONDARY, **CAM_PARAMS_DICT)

    # Initialize primary camera next
    print("Initializing primary camera...")
    __init_primary(CAM_PRIMARY, **CAM_PARAMS_DICT)

def deinit():
    global CAM_PRIMARY, CAM_SECONDARY

    print("De-initializing cameras...")

    # De-initialize secondary camera if it was set
    if CAM_SECONDARY:
        print("De-initializing secondary camera...")
        __deinit_secondary(CAM_SECONDARY)

    # De-initialize primary camera if it was set
    if CAM_PRIMARY:
        print("De-initializing primary camera...")
        __deinit_primary(CAM_PRIMARY)

    # Remove references to cameras
    CAM_SECONDARY = None
    CAM_PRIMARY = None

"""
