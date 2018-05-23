#!/usr/bin/env python

""" 'singleton' for setting up stereo cameras with PySpin library """

import os
import atexit
from warnings import warn
from contextlib import suppress

import yaml
import PySpin

# ------------------- #
# "attributes"        #
# ------------------- #

# Initialize system; if system goes out of scope, it will throw an error if there
# are any references to cameras remaining, so make sure to remove all references
# to cameras before exiting.
__SYSTEM = PySpin.System.GetInstance()

# Only state maintained is basically just primary and secondary camera objects.
# Any other state should be retrieved directly from the camera objects.
__CAM_PRIMARY = None
__CAM_SECONDARY = None

# --------------------#
# destructor          #
# ------------------- %

def __destructor():
    """ Handles the release of the PySpin System object """

    print('Cleaning up stereo_pyspin...')

    # NOTE: it might actually be a nice feature to allow cameras to remain
    # initialized and streaming after exiting stereo_pyspin... but I think
    # the destructor for System object prevents this. Maybe come back to
    # this later.

    # Clean up primary and secondary cameras
    __cleanup_primary_cam()
    __cleanup_secondary_cam()

    # Debug output if system is still in use some how
    if __SYSTEM.IsInUse():
        print('System is still in use? How can this be? Printing all globals:')
        for name, value in globals().items():
            print(name, value)

    # PySpin system goes out of scope here, so no need to explicitly
    # release the system

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
        if cam_serial == __cam_node_cmd(cam,
                                        'TLDevice.DeviceSerialNumber',
                                        'GetValue',
                                        'RO'):
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
    """ Gets image (and other info) from input camera """

    # Get image object
    image = cam.GetNextImage()

    # Initialize image dict
    image_dict = {}

    # Ensure image is complete
    if not image.IsIncomplete():
        # Get data/metadata
        image_dict['data'] = image.GetNDArray()
        image_dict['timestamp'] = image.GetTimeStamp()
        image_dict['bitsperpixel'] = image.GetBitsPerPixel()

    # PySpin image goes out of scope here, so no need to explicitly
    # release the image

    return image_dict

def __validate_cam(cam, cam_str):
    """ Checks to see if camera is valid """

    # NOTE: as of 10-May-2018 the IsValid() method does not work, but
    # I've kept it here to make the code future proof

    if not cam.IsValid():
        raise RuntimeError(cam_str + ' cam is not valid. Please find() it.')

def __validate_cam_init(cam, cam_str):
    """ Checks to see if camera is valid and initialized """

    __validate_cam(cam, cam_str)

    if not cam.IsInitialized():
        raise RuntimeError(cam_str + ' cam is not initialized. Please init() it.')

def __validate_cam_streaming(cam, cam_str):
    """ Checks to see if camera is valid, initialialized, and streaming """

    __validate_cam_init(cam, cam_str)

    if not cam.IsStreaming():
        raise RuntimeError(cam_str + ' cam is not streaming. Please start_acquisition() it.')

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

def __get_and_validate_cam_primary():
    """ Validates primary camera then returns it """

    cam_primary = __get_cam_primary()
    __validate_cam(cam_primary, 'Primary')
    return cam_primary

def __get_and_validate_cam_secondary():
    """ Validates secondary camera then returns it """

    cam_secondary = __get_cam_secondary()
    __validate_cam(cam_secondary, 'Secondary')
    return cam_secondary

def __get_and_validate_init_cam_primary():
    """ Validates initialization of primary camera then returns it """

    cam_primary = __get_cam_primary()
    __validate_cam_init(cam_primary, 'Primary')
    return cam_primary

def __get_and_validate_init_cam_secondary():
    """ Validates initialization of secondary camera then returns it """

    cam_secondary = __get_cam_secondary()
    __validate_cam_init(cam_secondary, 'Secondary')
    return cam_secondary

def __get_and_validate_streaming_cam_primary():
    """ Validates streaming of primary camera then returns it """

    cam_primary = __get_cam_primary()
    __validate_cam_streaming(cam_primary, 'Primary')
    return cam_primary

def __get_and_validate_streaming_cam_secondary():
    """ Validates streaming of secondary camera then returns it """

    cam_secondary = __get_cam_secondary()
    __validate_cam_streaming(cam_secondary, 'Secondary')
    return cam_secondary

def __cleanup_primary_cam():
    """ This will "clean up" primary camera """
    global __CAM_PRIMARY # pylint: disable=global-statement

    # End acquisition and de-init
    with suppress(Exception):
        end_acquisition_primary()
    with suppress(Exception):
        deinit_primary()

    # Clear camera reference
    __CAM_PRIMARY = None

def __cleanup_secondary_cam():
    """ This will "clean up" secondary camera """
    global __CAM_SECONDARY # pylint: disable=global-statement

    # End acquisition and de-init
    with suppress(Exception):
        end_acquisition_secondary()
    with suppress(Exception):
        deinit_secondary()

    # Clear camera references
    __CAM_SECONDARY = None

# ------------------- #
# "public" methods    #
# ------------------- #

def find_primary(cam_serial_or_yaml_path):
    """ Finds primary camera """
    global __CAM_PRIMARY # pylint: disable=global-statement

    # Find camera
    serial_primary = __get_serial(cam_serial_or_yaml_path)
    cam_primary = __find_cam(serial_primary)

    # Cleanup AFTER new camera is found successfully
    __cleanup_primary_cam()

    # Assign camera
    __CAM_PRIMARY = cam_primary

    print('Found primary camera with serial: ' + serial_primary)

def find_secondary(cam_serial_or_yaml_path):
    """ Finds secondary camera """
    global __CAM_SECONDARY # pylint: disable=global-statement

    # Find camera
    serial_secondary = __get_serial(cam_serial_or_yaml_path)
    cam_secondary = __find_cam(serial_secondary)

    # Cleanup AFTER new camera is found successfully
    __cleanup_secondary_cam()

    # Assign camera
    __CAM_SECONDARY = cam_secondary

    print('Found secondary camera with serial: ' + serial_secondary)

def get_serial_primary():
    """ Returns primary camera serial number """

    return __get_cam_primary().GetUniqueID()

def get_serial_secondary():
    """ Returns secondary camera serial number """

    return __get_cam_secondary().GetUniqueID()

def primary_node_cmd(cam_attr_str, cam_method_str, pyspin_mode_str=None, cam_method_arg=None):
    """ Performs cam_method on primary cam and attribute with optional access mode check """

    return __cam_node_cmd(__get_and_validate_init_cam_primary(),
                          cam_attr_str,
                          cam_method_str,
                          pyspin_mode_str,
                          cam_method_arg)

def secondary_node_cmd(cam_attr_str, cam_method_str, pyspin_mode_str=None, cam_method_arg=None):
    """ Performs cam_method on secondary cam and attribute with optional access mode check """

    return __cam_node_cmd(__get_and_validate_init_cam_secondary(),
                          cam_attr_str,
                          cam_method_str,
                          pyspin_mode_str,
                          cam_method_arg)

def get_frame_rate():
    """ Gets frame rate """

    frame_rate_primary = primary_node_cmd('AcquisitionameRate', 'GetValue')
    frame_rate_secondary = secondary_node_cmd('AcquisitionFrameRate', 'GetValue')

    if frame_rate_primary != frame_rate_secondary:
        warn('Primary and secondary frame rate are different: ' +
             str([frame_rate_primary, frame_rate_secondary]) +
             '. Returning the average value.')

        return (frame_rate_primary+frame_rate_secondary)/2

    return frame_rate_primary

def get_gain():
    """ Gets gain """

    gain_primary = primary_node_cmd('Gain', 'GetValue')
    gain_secondary = secondary_node_cmd('Gain', 'GetValue')

    if gain_primary != gain_secondary:
        warn('Primary and secondary gain are different: ' +
             str([gain_primary, gain_secondary]) +
             '. Returning the average value.')

        return (gain_primary+gain_secondary)/2

    return gain_primary

def get_exposure():
    """ Gets exposure """

    exposure_primary = primary_node_cmd('ExposureTime', 'GetValue')
    exposure_secondary = secondary_node_cmd('ExposureTime', 'GetValue')

    if exposure_primary != exposure_secondary:
        warn('Primary and secondary exposure are different: ' +
             str([exposure_primary, exposure_secondary]) +
             '. Returning the average value.')

        return (exposure_primary+exposure_secondary)/2

    return exposure_primary

def get_image_primary():
    """ Gets image from primary camera """

    return __get_image(__get_and_validate_streaming_cam_primary())

def get_image_secondary():
    """ Gets image from secondary camera """

    return __get_image(__get_and_validate_streaming_cam_secondary())

def set_frame_rate(frame_rate):
    """ Sets frame rate for both cameras """

    primary_node_cmd('AcquisitionFrameRate',
                     'SetValue',
                     'RW',
                     frame_rate)
    secondary_node_cmd('AcquisitionFrameRate',
                       'SetValue',
                       'RW',
                       frame_rate)

def set_gain(gain):
    """ Sets gain for both cameras """

    primary_node_cmd('Gain',
                     'SetValue',
                     'RW',
                     gain)
    secondary_node_cmd('Gain',
                       'SetValue',
                       'RW',
                       gain)

def set_exposure(exposure):
    """ Sets exposure for both cameras """

    primary_node_cmd('ExposureTime',
                     'SetValue',
                     'RW',
                     exposure)
    secondary_node_cmd('ExposureTime',
                       'SetValue',
                       'RW',
                       exposure)

def init_primary(yaml_path=None):
    """ Initializes primary camera using optional yaml file """

    __init_cam(__get_cam_primary(), yaml_path)

def init_secondary(yaml_path=None):
    """ Initializes secondary camera using optional yaml file """

    __init_cam(__get_cam_secondary(), yaml_path)

def start_acquisition_primary():
    """ Starts acquisition of primary camera """

    __get_and_validate_init_cam_primary().BeginAcquisition()

def start_acquisition_secondary():
    """ Starts acquisition of secondary camera """

    __get_and_validate_init_cam_secondary().BeginAcquisition()

def end_acquisition_primary():
    """ Ends acquisition of primary camera """

    __get_and_validate_streaming_cam_primary().EndAcquisition()

def end_acquisition_secondary():
    """ Ends acquisition of secondary camera """

    __get_and_validate_streaming_cam_secondary().EndAcquisition()

def deinit_primary():
    """ De-initializes primary camera """

    __get_and_validate_init_cam_primary().DeInit()

def deinit_secondary():
    """ De-initializes secondary camera """

    __get_and_validate_init_cam_secondary().DeInit()
