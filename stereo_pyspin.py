#!/usr/bin/env python

""" 'singleton' for setting up stereo cameras with PySpin library """

import os
from warnings import warn

import yaml
import PySpin

# ------------------- #
# "attributes"        #
# ------------------- #

# cameras must be found before they are used
__CAM_PRIMARY = None
__CAM_SECONDARY = None

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

def __get_image(cam):
    """ Gets image from input camera """

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
# "public" functions  #
# ------------------- #

def find_pimary(cam_serial):
    """ Finds primary camera """
    global __CAM_PRIMARY # pylint: disable=global-statement

    __CAM_PRIMARY = __find_cam(cam_serial)

def find_secondary(cam_serial):
    """ Finds secondary camera """
    global __CAM_SECONDARY # pylint: disable=global-statement

    __CAM_SECONDARY = __find_cam(cam_serial)

def init_primary(yaml_path=None):
    """ Initializes primary camera using optional yaml file """

    __init_cam(get_primary(), yaml_path)

def init_secondary(yaml_path=None):
    """ Initializes secondary camera using optional yaml file """

    __init_cam(get_secondary(), yaml_path)

def start_acquisition_primary():
    """ Starts acquisition of primary camera """

    get_primary().BeginAcquisition()

def start_acquisition_secondary():
    """ Starts acquisition of secondary camera """

    get_secondary().BeginAcquisition()

def end_acquisition_primary():
    """ Ends acquisition of primary camera """

    get_primary().EndAcquisition()

def end_acquisition_secondary():
    """ Ends acquisition of secondary camera """

    get_secondary().EndAcquisition()

def deinit_primary():
    """ De-initializes primary camera """

    get_primary().DeInit()

def deinit_secondary():
    """ De-initializes secondary camera """

    get_secondary().DeInit()

def set_frame_rate(frame_rate):
    """ Sets frame rate for both cameras """

    __cam_node_cmd(get_primary(), 'AcquisitionFrameRate', 'SetValue', 'RW', frame_rate)
    __cam_node_cmd(get_secondary(), 'AcquisitionFrameRate', 'SetValue', 'RW', frame_rate)

def set_gain(gain):
    """ Sets gain for both cameras """

    __cam_node_cmd(get_primary(), 'Gain', 'SetValue', 'RW', gain)
    __cam_node_cmd(get_secondary(), 'Gain', 'SetValue', 'RW', gain)

def set_exposure(exposure):
    """ Sets exposure for both cameras """

    __cam_node_cmd(get_primary(), 'ExposureTime', 'SetValue', 'RW', exposure)
    __cam_node_cmd(get_secondary(), 'ExposureTime', 'SetValue', 'RW', exposure)

def get_primary():
    """ Returns primary camera """

    if not __CAM_PRIMARY:
        raise RuntimeError('Primary camera has not been found yet!')

    return __CAM_PRIMARY

def get_secondary():
    """ Returns secondary camera """

    if not __CAM_SECONDARY:
        raise RuntimeError('Secondary camera has not been found yet!')

    return __CAM_SECONDARY

def get_frame_rate():
    """ Gets frame rate """

#    frame_rate_primary = float(__cam_node_cmd(get_primary(),
#                                              'AcquisitionFrameRate',
#                                              'GetValue',
#                                              'RW'))
#    frame_rate_secondary = float(__cam_node_cmd(get_secondary(),
#                                                'AcquisitionFrameRate',
#                                                'GetValue',
#                                                'RW'))
#
#    if frame_rate_primary != frame_rate_secondary:
#        warn('Primary and secondary frame rate are different: ' +
#             str([frame_rate_primary, frame_rate_secondary]) + ' ' +
#             '. Returning the average value')
#
#        return (frame_rate_primary+frame_rate_secondary)/2
#
#    return frame_rate_primary

    import numpy
    return 60 + numpy.random.rand(1)[0]

def get_gain():
    """ Gets gain """

#    gain_primary = float(__cam_node_cmd(get_primary(), 'Gain', 'GetValue', 'RW'))
#    gain_secondary = float(__cam_node_cmd(get_secondary(), 'Gain', 'GetValue', 'RW'))
#
#    if gain_primary != gain_secondary:
#        warn('Primary and secondary gain are different: ' +
#             str([gain_primary, gain_secondary]) + ' ' +
#             '. Returning the average value')
#
#        return (gain_primary+gain_secondary)/2
#
#    return gain_primary

    return 1

def get_exposure():
    """ Gets exposure """

#    exposure_primary = float(__cam_node_cmd(get_primary(), 'ExposureTime', 'GetValue', 'RW'))
#    exposure_secondary = float(__cam_node_cmd(get_secondary(), 'ExposureTime', 'GetValue', 'RW'))
#
#    if exposure_primary != exposure_secondary:
#        warn('Primary and secondary exposure are different: ' +
#             str([exposure_primary, exposure_secondary]) + ' ' +
#             '. Returning the average value')
#
#        return (exposure_primary+exposure_secondary)/2
#
#    return exposure_primary

    return 5

def get_image_primary():
    """ Gets image from primary camera """

    import numpy as np
    return np.random.rand(1536, 2048)*255

    #return __get_image(get_primary())

def get_image_secondary():
    """ Gets image from secondary camera """

    import numpy as np
    return np.random.rand(1536, 2048)*255

    #return __get_image(get_secondary())
