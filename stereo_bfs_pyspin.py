#!/usr/bin/env python

""" 'singleton' for setting up BFS stereo cameras """

# pylint: disable=global-statement,bad-whitespace,line-too-long

import atexit
import PySpin #pylint: disable=import-error

# ------------------- #
# "attributes"        #
# ------------------- #

CAM_PRIMARY = None
CAM_SECONDARY = None

# ------------------- #
# "static" functions  #
# ------------------- #

def __cam_exec_cmd(cam, cmd):
    """ Executes input command on the input camera """

    # cmd[0] = camera command to use
    # cmd[1] = optional argument to camera command
    # cmd[2] = optional access mode check

    # First, get camera attribute
    cam_attr = cam
    cam_attr_str_split = cmd[0].split('.')
    if len(cam_attr_str_split) > 1:
        # Need to get the camera attribute
        for sub_cam_attr_str in cam_attr_str_split[0:-1]:
            cam_attr = getattr(cam_attr, sub_cam_attr_str)

    # Perform optional access mode check
    if cmd[2] and cam_attr.GetAccessMode() != getattr(PySpin, cmd[2]):
        raise RuntimeError('Access mode check failed for: "' + '.'.join(cam_attr_str_split[0:-1]) + '"')

    # Print command info
    info_str = 'Executing: "' + '.'.join(cam_attr_str_split[0:-1]) + '"'
    if cmd[1]:
        info_str += ' with argument: "' + cmd[1] + '"'
    print(info_str)

    # Get command argument
    arg = None
    if cmd[1]:
        arg = cmd[1]
        # Check to see if argument is a PySpin attribute
        arg_split = cmd[1].split('.')
        if len(arg_split) == 2 and arg_split[0] == 'PySpin':
            arg = getattr(PySpin, arg_split[1])

    # Perform command
    if not arg:
        getattr(cam_attr,cam_attr_str_split[-1])()
    else:
        getattr(cam_attr,cam_attr_str_split[-1])(arg)

def __cam_exec_cmd_list(cam, cmd_list):
    """ Executes the commands in the order specified in cmd_list """

    for cmd in cmd_list:
        __cam_exec_cmd(cam, cmd)

def __init_secondary(cam):
    """ Initializes the secondary camera """

    # Execute the following in the following order
    cmd_list = [
        ['Init',                                       None,                                         None], # Initialize camera
        ['UserSetSelector.SetValue',                   'PySpin.UserSetDefault_Default',              'RW'], # Set default user set
        ['UserSetLoad.Execute',                        None,                                         'WO'], # Load default user set
        ['TriggerMode.SetValue',                       'PySpin.TriggerMode_Off',                     'RW'], # Ensure trigger mode is off first - this is required in order to set the trigger source and overlap
        ['TriggerSource.SetValue',                     'PySpin.TriggerSource_Line3',                 'RW'], # Select trigger source to line 3
        ['TriggerOverlap.SetValue',                    'PySpin.TriggerOverlap_ReadOut',              'RW'], # Set trigger overlap to readout
        ['TriggerMode.SetValue',                       'PySpin.TriggerMode_On',                      'RW'], # Turn trigger mode back on
        ['TLStream.StreamBufferHandlingMode.SetValue', 'PySpin.StreamBufferHandlingMode_NewestOnly', 'RW'], # Set stream buffer handling mode to newest only
        ['AcquisitionMode.SetValue',                   'PySpin.AcquisitionMode_Continuous',          'RW'], # Set acquisition mode to continuous
        ['BeginAcquisition',                           None,                                         None]  # Start acquisition
    ]
    __cam_exec_cmd_list(cam, cmd_list)

def __init_primary(cam):
    """ Initializes the primary camera """

    # Execute the following in the following order
    cmd_list = [
        ['Init',                                       None,                                         None], # Initialize camera
        ['UserSetSelector.SetValue',                   'PySpin.UserSetDefault_Default',              'RW'], # Set default user set
        ['UserSetLoad.Execute',                        None,                                         'WO'], # Load default user set
        ['LineSelector.SetValue',                      'PySpin.LineSelector_Line2',                  'RW'], # Set line selector to line 2
        ['V3_3Enable.SetValue',                        True,                                         'RW'], # Enable 3.3V
        ['TLStream.StreamBufferHandlingMode.SetValue', 'PySpin.StreamBufferHandlingMode_NewestOnly', 'RW'], # Set stream buffer handling mode to newest only
        ['AcquisitionMode.SetValue',                   'PySpin.AcquisitionMode_Continuous',          'RW'], # Set acquisition mode to continuous
        ['BeginAcquisition',                           None,                                         None]  # Start acquisition
    ]
    __cam_exec_cmd_list(cam, cmd_list)

def __deinit_secondary(cam):
    """ De-initializes the secondary camera """

    # Execute the following in the following order
    cmd_list = [
        ['EndAcquisition',                             None,                                         None], # Ends acquisition
        ['UserSetSelector.SetValue',                   'PySpin.UserSetDefault_Default',              'RW'], # Set default user set
        ['UserSetLoad.Execute',                        None,                                         'WO'], # Load default user set
        ['DeInit',                                     None,                                         None], # De-initializes camera
    ]
    __cam_exec_cmd_list(cam, cmd_list)

def __deinit_primary(cam):
    """ De-initializes the primary camera """

    # Execute the following in the following order
    cmd_list = [
        ['EndAcquisition',                             None,                                         None], # Ends acquisition
        ['UserSetSelector.SetValue',                   'PySpin.UserSetDefault_Default',              'RW'], # Set default user set
        ['UserSetLoad.Execute',                        None,                                         'WO'], # Load default user set
        ['DeInit',                                     None,                                         None], # De-initializes camera
    ]
    __cam_exec_cmd_list(cam, cmd_list)

# ------------------- #
# "public" functions  #
# ------------------- #

def init(cam_serial_primary, cam_serial_secondary):
    """ Finds primary and secondary camera and sets up hardware trigger and begins acquisition """
    global CAM_PRIMARY, CAM_SECONDARY

    # Get system
    system = PySpin.System.GetInstance()

    # Retrieve cameras from the system
    cam_list = system.GetCameras()

    # Make sure two cameras are present
    num_cameras = cam_list.GetSize()
    if num_cameras != 2:
        raise RuntimeError('Number of cameras detected: ' + str(num_cameras) +
                           '. Only two-camera configurations are supported.')
    print("Two cameras detected!")

    # Get the primary and secondary camera
    for i in range(2):
        # Get camera
        cam = cam_list.GetByIndex(i)

        # Read serial number to assign primary/secondary
        if cam.TLDevice.DeviceSerialNumber.GetAccessMode() == PySpin.RO:
            cam_serial = int(cam.TLDevice.DeviceSerialNumber.GetValue())
            if cam_serial == cam_serial_primary:
                print('Primary serial: ' + str(cam_serial))
                CAM_PRIMARY = cam
            elif cam_serial == cam_serial_secondary:
                print('Secondary serial: ' + str(cam_serial))
                CAM_SECONDARY = cam
            else:
                raise RuntimeError('Unrecognized camera with serial: ' + str(cam_serial))
        else:
            raise RuntimeError('Serial number could not be read from one of the cameras...')

    # Initialize secondary camera first to put it into trigger mode which will wait on primary camera
    print("Initializing secondary camera...")
    __init_secondary(CAM_SECONDARY)

    # Initialize primary camera next
    print("Initializing primary camera...")
    __init_primary(CAM_PRIMARY)

def deinit():
    """ De-initializes cameras """
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

# ------------------- #
# "Destructor"        #
# ------------------- #
atexit.register(deinit)
