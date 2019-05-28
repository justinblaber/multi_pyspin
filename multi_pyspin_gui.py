#!/usr/bin/env python

""" GUI for multiple cameras with PySpin library """

# Designed and tested on:
#   -camera:                        Blackfly S BFS-U3-32S4M
#   -firmware:                      1804.0.113.0
#   -spinnaker version:             spinnaker-1.21.0.61-amd64-Ubuntu18.04-pkg
#   -spinnaker python version:      spinnaker_python-1.21.0.61-cp36-cp36m-linux_x86_64

import sys
import copy
import time
import queue
import functools
from datetime import datetime
from tkinter import messagebox

import numpy as np

import matplotlib.pyplot as plt
from matplotlib.widgets import TextBox
from matplotlib.widgets import Button
from matplotlib.widgets import Slider

import PySpin

import multi_pyspin


# ------------------- #
# "attributes"        #
# ------------------- #


# Set default number of cameras and set serial numbers
_NUM_CAMS = 1
_SERIALS = [None]

# These are default min/max values. You can actually grab these from the camera nodes, but since we want to synchronize
# across all cameras I've set defaults here.
_GAIN_MIN = 0              # Units are dB
_GAIN_MAX = 47             # Units are dB
_EXPOSURE_MIN = 5          # Units are micro seconds
_EXPOSURE_MAX = 1000000    # actual max is much larger, but more than 1 second exposure is absurdly long
_FPS_MIN = 1
_FPS_MAX = 120

# Timeout factor is a multiple of the "resulting" fps which sets a timeout to prevent infinite hanging in case something
# goes wrong or a trigger is set
_IMAGE_TIMEOUT_FACTOR = 5  # Multiple of image period
_IMAGE_TIMEOUT_MIN = 5000  # Minimum timeout
_IMAGE_TIMEOUT = None      # Gets set after camera is setup or exposure/fps values get updated

# Set stream buffer count, which determines the buffer queue size in PC RAM
_STREAM_BUFFER_COUNT = 10  # TODO: Possibly calculate this dynamically...

# Delay warning tolerance
_DELAY_WARNING_TOLERANCE = 1e-3

# Set number of histogram bins
_NUM_HISTOGRAM_BINS = 50

# GUI params
_FIG = None
_QUEUE = queue.Queue()
_STREAMS = [False]
_IMSHOW_DICTS = [{}]
_HIST_DICTS = [{}]
_GUI_DICT = None


# ------------------- #
# "static" functions  #
# ------------------- #


def _update_fig(fig):
    """ Updates figure """

    fig.canvas.draw()
    fig.canvas.flush_events()


def _slider_with_text(fig, pos, slider_str, val_min, val_max, val_default, padding):
    """ Creates a slider with text box given a position """

    # Position params
    slider_left_offset = (pos[2]-4*padding)/3 + 2*padding
    slider_width = (pos[2]-4*padding)/3
    text_width = pos[2] - slider_left_offset - slider_width - 2*padding

    # Slider
    slider_pos = [pos[0]+slider_left_offset,
                  pos[1],
                  slider_width,
                  pos[3]]
    slider_axes = fig.add_axes(slider_pos)
    slider = Slider(slider_axes,
                    slider_str,
                    val_min,
                    val_max,
                    valinit=val_default,
                    dragging=False)
    slider.valtext.set_visible(False)
    slider.label.set_fontsize(7)

    # Text
    text_pos = [slider_pos[0]+slider_pos[2]+padding,
                slider_pos[1],
                text_width,
                pos[3]]
    text_axes = fig.add_axes(text_pos)
    text = TextBox(text_axes, '')

    return slider, text


def _cam_plot(fig, pos, cam_str, row_height, gain_min, gain_max, gain_default, padding):
    """ Creates camera plot; make one of these per camera """

    # position params
    num_rows = 3
    residual_height = pos[3] - num_rows*row_height - (num_rows+3)*padding
    image_height = residual_height*0.85
    image_width = pos[2]-2*padding
    hist_height = residual_height-image_height

    # image axes
    image_pos = [pos[0]+padding, pos[1]+pos[3]-image_height-padding, image_width, image_height]
    image_axes = fig.add_axes(image_pos)
    image_axes.set_xticklabels([])
    image_axes.set_yticklabels([])
    image_axes.set_xticks([])
    image_axes.set_yticks([])

    # hist axes
    hist_pos = [image_pos[0], image_pos[1]-hist_height-padding, image_width, hist_height]
    hist_axes = fig.add_axes(hist_pos)
    hist_axes.set_xticklabels([])
    hist_axes.set_yticklabels([])
    hist_axes.set_xticks([])
    hist_axes.set_yticks([])

    # setup button
    setup_button_pos = [image_pos[0],
                        hist_pos[1] - row_height - padding,
                        (image_width-padding)/2,
                        row_height]
    setup_button_axes = fig.add_axes(setup_button_pos)
    setup_button = Button(setup_button_axes, 'Setup ' + cam_str)
    setup_button.label.set_fontsize(7)

    # setup text
    setup_text_pos = [setup_button_pos[0] + setup_button_pos[2] + padding,
                      setup_button_pos[1],
                      (image_width-padding)/2,
                      row_height]
    setup_text_axes = fig.add_axes(setup_text_pos)
    setup_text = TextBox(setup_text_axes, '')

    # start stream button
    start_stream_button_pos = [setup_button_pos[0],
                               setup_button_pos[1] - row_height - padding,
                               (image_width-padding)/2,
                               row_height]
    start_stream_button_axes = fig.add_axes(start_stream_button_pos)
    start_stream_button = Button(start_stream_button_axes, 'Start Stream')
    start_stream_button.label.set_fontsize(7)

    # stop stream button
    stop_stream_button_pos = [start_stream_button_pos[0] + start_stream_button_pos[2] + padding,
                              start_stream_button_pos[1],
                              (image_width-padding)/2,
                              row_height]
    stop_stream_button_axes = fig.add_axes(stop_stream_button_pos)
    stop_stream_button = Button(stop_stream_button_axes, 'Stop Stream')
    stop_stream_button.label.set_fontsize(7)

    # gain slider
    gain_pos = [pos[0], pos[1]+padding, pos[2], row_height]
    gain_slider, gain_text = _slider_with_text(fig,
                                               gain_pos,
                                               'Gain',
                                               gain_min,
                                               gain_max,
                                               gain_default,
                                               padding)

    return {'image_axes': image_axes,
            'hist_axes': hist_axes,
            'setup_button': setup_button,
            'setup_text': setup_text,
            'start_stream_button': start_stream_button,
            'stop_stream_button': stop_stream_button,
            'gain_slider': gain_slider,
            'gain_text': gain_text}


def _multi_fig(fig, num_cams, gain_min, gain_max, gain_default, exposure_min, exposure_max, exposure_default, fps_min, fps_max, fps_default):
    """ Creates multi cam GUI figure """

    # Position params
    padding = 0.01
    row_height = 0.02
    num_top_rows = 1
    num_bottom_rows = 4
    num_cams_width = (1-3*padding)/2
    cam_plot_height_offset = num_bottom_rows*row_height + num_bottom_rows*padding
    cam_plot_width = (1-(num_cams+1)*padding)/num_cams + 2*padding
    cam_plot_height = 1 - cam_plot_height_offset - (num_top_rows*row_height + num_top_rows*padding)
    name_format_width = (1 - 3*padding)/2
    save_width = (0.5 - (num_cams+1.5)*padding)/(num_cams+1)
    num_images_width = (((1 - 3*padding)/2) - 3*padding)/8
    delay_width = (((1 - 3*padding)/2) - 3*padding)/8
    num_bursts_width = (((1 - 3*padding)/2) - 3*padding)/8
    counter_width = (((1 - 3*padding)/2) - 3*padding)/8

    # num cams button
    num_cams_button_pos = [padding,
                           1-row_height-padding,
                           num_cams_width,
                           row_height]
    num_cams_button_axes = fig.add_axes(num_cams_button_pos)
    num_cams_button = Button(num_cams_button_axes, 'Set # Cams')
    num_cams_button.label.set_fontsize(7)

    # num cams text
    num_cams_text_pos = [num_cams_button_pos[0] + num_cams_button_pos[2] + padding,
                         num_cams_button_pos[1],
                         num_cams_width,
                         row_height]
    num_cams_text_axes = fig.add_axes(num_cams_text_pos)
    num_cams_text = TextBox(num_cams_text_axes, '')
    num_cams_text.set_val(str(num_cams))

    # cam plots
    cam_plot_dicts = []
    for i in range(num_cams):
        # Set camera string; note that first camera is considered "primary"
        cam_str = 'Cam ' + str(i + 1)
        if i == 0:
            cam_str = cam_str + " (primary)"
        else:
            cam_str = cam_str + " (secondary)"

        cam_plot_pos = [i*(cam_plot_width-padding),
                        cam_plot_height_offset,
                        cam_plot_width,
                        cam_plot_height]
        cam_plot_dict = _cam_plot(fig,
                                  cam_plot_pos,
                                  cam_str,
                                  row_height,
                                  gain_min,
                                  gain_max,
                                  gain_default,
                                  padding)
        # Append
        cam_plot_dicts.append(cam_plot_dict)

    # exposure slider
    exposure_pos = [0, cam_plot_height_offset-row_height, 1, row_height]
    exposure_slider, exposure_text = _slider_with_text(fig,
                                                       exposure_pos,
                                                       'Exposure',
                                                       exposure_min,
                                                       exposure_max,
                                                       exposure_default,
                                                       padding)

    # FPS slider
    fps_pos = [exposure_pos[0], exposure_pos[1]-row_height-padding, 1, row_height]
    fps_slider, fps_text = _slider_with_text(fig,
                                             fps_pos,
                                             'FPS',
                                             fps_min,
                                             fps_max,
                                             fps_default,
                                             padding)

    # name format
    name_format_pos = [name_format_width + 2*padding,
                       fps_pos[1]-row_height-padding,
                       name_format_width,
                       row_height]
    name_format_axes = fig.add_axes(name_format_pos)
    name_format_text = TextBox(name_format_axes, 'Name format')
    name_format_text.label.set_fontsize(7)
    name_format_text.set_val('{serial}_{datetime}_{cam}_{frameid}_{counter}')

    # save cam buttons
    save_cam_buttons = []
    for i in range(num_cams):
        # save button
        save_cam_button_pos = [i*save_width + (i+1)*padding,
                               padding,
                               save_width,
                               row_height]
        save_cam_button_axes = fig.add_axes(save_cam_button_pos)
        save_cam_button = Button(save_cam_button_axes, 'Save Cam "' + str(i+1) + '"')
        save_cam_button.label.set_fontsize(7)
        # Append
        save_cam_buttons.append(save_cam_button)

    # multi save button
    save_multi_button_pos = [num_cams*save_width + (num_cams+1)*padding,
                             padding,
                             save_width,
                             row_height]
    save_multi_button_axes = fig.add_axes(save_multi_button_pos)
    save_multi_button = Button(save_multi_button_axes, 'Save Multi')
    save_multi_button.label.set_fontsize(7)

    # num images text
    num_images_text_pos = [save_multi_button_pos[0] + save_multi_button_pos[2] + num_images_width + padding,
                           save_multi_button_pos[1],
                           num_images_width,
                           row_height]
    num_images_text_axes = fig.add_axes(num_images_text_pos)
    num_images_text = TextBox(num_images_text_axes, '# Images')
    num_images_text.label.set_fontsize(7)
    num_images_text.set_val(1)

    # delay
    delay_pos = [num_images_text_pos[0] + num_images_text_pos[2] + delay_width + padding,
                 num_images_text_pos[1],
                 delay_width,
                 row_height]
    delay_axes = fig.add_axes(delay_pos)
    delay_text = TextBox(delay_axes, 'Delay')
    delay_text.label.set_fontsize(7)
    delay_text.set_val(1)

    # num burst
    num_bursts_pos = [delay_pos[0] + delay_pos[2] + num_bursts_width + padding,
                      delay_pos[1],
                      num_bursts_width,
                      row_height]
    num_bursts_axes = fig.add_axes(num_bursts_pos)
    num_bursts_text = TextBox(num_bursts_axes, '# Burst')
    num_bursts_text.label.set_fontsize(7)
    num_bursts_text.set_val(1)

    # counter
    counter_pos = [num_bursts_pos[0] + num_bursts_pos[2] + counter_width + padding,
                   num_bursts_pos[1],
                   counter_width,
                   row_height]
    counter_axes = fig.add_axes(counter_pos)
    counter_text = TextBox(counter_axes, 'Counter')
    counter_text.label.set_fontsize(7)
    counter_text.set_val(1)

    return {'num_cams_button': num_cams_button,
            'num_cams_text': num_cams_text,
            'cam_plot_dicts': cam_plot_dicts,
            'exposure_slider': exposure_slider,
            'exposure_text': exposure_text,
            'fps_slider': fps_slider,
            'fps_text': fps_text,
            'name_format_text': name_format_text,
            'save_cam_buttons': save_cam_buttons,
            'save_multi_button': save_multi_button,
            'num_images_text': num_images_text,
            'delay_text': delay_text,
            'num_bursts_text': num_bursts_text,
            'counter_text': counter_text}


def _plot_image(image, max_val, image_axes, imshow_dict):
    """ plots image somewhat fast """

    # If image hasn't been plotted yet, or if image size changes or if max val changes, then we must replot imshow
    if not imshow_dict or (image.shape != imshow_dict['imshow_size'] or max_val != imshow_dict['max_val']):
        # Must reset axes and re-imshow()
        image_axes.cla()
        imshow_dict['imshow'] = image_axes.imshow(image, cmap='gray', vmin=0, vmax=max_val)
        imshow_dict['imshow_size'] = image.shape
        imshow_dict['max_val'] = max_val
        image_axes.set_xticklabels([])
        image_axes.set_yticklabels([])
        image_axes.set_xticks([])
        image_axes.set_yticks([])
    else:
        # Can just "set_data" since data is the same size and has the same max val
        imshow_dict['imshow'].set_data(image)

    return imshow_dict


def _plot_hist(image, max_val, num_bins, hist_axes, hist_dict):
    """ plots histogram somewhat fast """

    # Calculate histogram
    hist, bins = np.histogram(image.ravel(), density=True, bins=num_bins, range=(0, max_val))

    # If histogram hasn't been plotted yet, or if number of bins changes or max_val changes, then we must replot histogram
    if not hist_dict or (hist_dict['num_bins'] != num_bins or hist_dict['max_val'] != max_val):
        # Must reset axes and plot hist
        hist_axes.cla()
        hist_dict['bar'] = hist_axes.bar(bins[:-1], hist, color='k', width=(max_val+1)/num_bins)
        hist_dict['num_bins'] = num_bins
        hist_dict['max_val'] = max_val
        hist_axes.set_ylim(0, num_bins/max_val)  # Note that density=True makes it a probability density function
        hist_axes.set_xticklabels([])
        hist_axes.set_yticklabels([])
        hist_axes.set_xticks([])
        hist_axes.set_yticks([])
    else:
        # Just reset height
        for i, bar in enumerate(hist_dict['bar']):
            bar.set_height(hist[i])

    return hist_dict


# ------------------- #
# "private" methods   #
# ------------------- #


def _get_and_validate_serial(cam_num):
    """ Validates serial then returns it """

    serial = _SERIALS[cam_num]
    if serial is None:
        raise RuntimeError('Cam ' + str(cam_num + 1) + ' has not been setup yet!')

    return serial


def _start_stream(cam_num):
    """ starts cam_num's stream """

    # Make sure cam_num isn't already streaming
    if not _STREAMS[cam_num]:
        serial = _get_and_validate_serial(cam_num)

        # Set buffer to newest only and acquisition mode to continuous
        multi_pyspin.node_cmd(serial, 'TLStream.StreamBufferHandlingMode', 'SetValue', 'RW', 'PySpin.StreamBufferHandlingMode_NewestOnly')
        multi_pyspin.node_cmd(serial, 'AcquisitionMode', 'SetValue', 'RW', 'PySpin.AcquisitionMode_Continuous')

        # Start acquisition
        multi_pyspin.start_acquisition(serial)

        # Set stream to true; do this last
        _STREAMS[cam_num] = True

        print(serial + ' - stream started')


def _stop_stream(cam_num):
    """ stops cam_num's stream """

    # Make sure cam_num is streaming
    if _STREAMS[cam_num]:
        # Set stream to false; do this first
        _STREAMS[cam_num] = False

        # Stop acquisition
        serial = _get_and_validate_serial(cam_num)
        multi_pyspin.end_acquisition(serial)

        print(serial + ' - stream stopped')


def _stop_streams():
    """ attempts to stop all streams """

    for cam_num in range(_NUM_CAMS):
        _stop_stream(cam_num)


def _set_gain_text(cam_num, gain):
    """ sets gain for text """

    # Get gain text
    gain_text = _GUI_DICT['cam_plot_dicts'][cam_num]['gain_text']

    # Update text
    gain_text.eventson = False
    gain_text.set_val(gain)
    gain_text.eventson = True


def _set_gain_slider(cam_num, gain):
    """ sets gain for slider """

    # Get gain slider
    gain_slider = _GUI_DICT['cam_plot_dicts'][cam_num]['gain_slider']

    # Update slider
    gain_slider.eventson = False
    gain_slider.set_val(gain)
    gain_slider.eventson = True


def _set_exposure_text(exposure):
    """ sets exposure for text """

    # Get exposure text
    exposure_text = _GUI_DICT['exposure_text']

    # Update text
    exposure_text.eventson = False
    exposure_text.set_val(exposure)
    exposure_text.eventson = True


def _set_exposure_slider(exposure):
    """ sets exposure for slider """

    # Get exposure slider
    exposure_slider = _GUI_DICT['exposure_slider']

    # Update slider
    exposure_slider.eventson = False
    exposure_slider.set_val(exposure)
    exposure_slider.eventson = True


def _set_fps_text(fps):
    """ sets fps for text """

    # Get fps text
    fps_text = _GUI_DICT['fps_text']

    # Update text
    fps_text.eventson = False
    fps_text.set_val(fps)
    fps_text.eventson = True


def _set_fps_slider(fps):
    """ sets fps for slider """

    # Get fps slider
    fps_slider = _GUI_DICT['fps_slider']

    # Update slider
    fps_slider.eventson = False
    fps_slider.set_val(fps)
    fps_slider.eventson = True


def _set_image_timeout(cam_num):
    """ sets image timeout """
    global _IMAGE_TIMEOUT

    serial = _get_and_validate_serial(cam_num)

    # Get resulting FPS which is like the "effective" fps
    fps = multi_pyspin.node_cmd(serial, 'AcquisitionResultingFrameRate', 'GetValue')

    # Set timeout in ms
    _IMAGE_TIMEOUT = max(int(_IMAGE_TIMEOUT_FACTOR*((1/fps)*1e3)), _IMAGE_TIMEOUT_MIN)
    print(serial + ' - effective framerate: ' + str(fps) + '; image timeout set to: ' + str(_IMAGE_TIMEOUT))


def _set_exposure(exposure):
    """ Tries to set exposure for all cameras """

    for cam_num in range(_NUM_CAMS):
        # noinspection PyBroadException
        try:
            serial = _get_and_validate_serial(cam_num)
        except:
            continue

        # Set exposure
        multi_pyspin.set_exposure(serial, exposure)

        # Update image timeout
        _set_image_timeout(cam_num)


def _set_fps(fps):
    """ Tries to set fps for all cameras """

    for cam_num in range(_NUM_CAMS):
        # noinspection PyBroadException
        try:
            serial = _get_and_validate_serial(cam_num)
        except:
            continue

        # Set fps
        multi_pyspin.set_frame_rate(serial, fps)

        # Update image timeout
        _set_image_timeout(cam_num)


def _save_images(cam_nums):
    """ Saves images """

    # Get info
    name_format = _GUI_DICT['name_format_text'].text
    num_images = _GUI_DICT['num_images_text'].text
    delay = float(_GUI_DICT['delay_text'].text)
    num_bursts = int(_GUI_DICT['num_bursts_text'].text)
    counter = int(_GUI_DICT['counter_text'].text)

    if num_images == 'c':         # "c" for continuous
        num_images = sys.maxsize  # Just set a very large number
    else:
        num_images = int(num_images)

    # Cache streams
    streams = copy.deepcopy(_STREAMS)

    # Disable all active streams
    _stop_streams()

    # Set StreamBufferCount (queue buffer on PC RAM). Note that for linux and usb cameras you must set usbfs to an
    # appropriate size
    for cam_num in cam_nums:
        serial = _get_and_validate_serial(cam_num)
        multi_pyspin.node_cmd(serial, 'TLStream.StreamBufferCountMode', 'SetValue', 'RW', 'PySpin.StreamBufferCountMode_Manual')
        multi_pyspin.node_cmd(serial, 'TLStream.StreamBufferCountManual', 'SetValue', 'RW', _STREAM_BUFFER_COUNT)

    # Set buffer to oldest first, and set acquisition mode and acquisition frame count
    for cam_num in cam_nums:
        serial = _get_and_validate_serial(cam_num)
        multi_pyspin.node_cmd(serial, 'TLStream.StreamBufferHandlingMode', 'SetValue', 'RW', 'PySpin.StreamBufferHandlingMode_OldestFirst')
        # Setting a multiframe for a single image returns an error, so dispatch
        if num_bursts == 1:
            multi_pyspin.node_cmd(serial, 'AcquisitionMode', 'SetValue', 'RW', 'PySpin.AcquisitionMode_SingleFrame')
        elif num_bursts > 1:
            multi_pyspin.node_cmd(serial, 'AcquisitionMode', 'SetValue', 'RW', 'PySpin.AcquisitionMode_MultiFrame')
            multi_pyspin.node_cmd(serial, 'AcquisitionFrameCount', 'SetValue', 'RW', num_bursts)
        else:
            raise RuntimeError('Invalid value for burst #: ' + str(num_bursts))

    # Update all timestamps before collecting images
    for cam_num in cam_nums:
        serial = _get_and_validate_serial(cam_num)
        multi_pyspin.update_timestamp_offset(serial)

    # Grab number of images
    time_begin = datetime.now()
    total_delay = 0
    for num_image in range(num_images):
        # Delay acquisition based on delay
        while total_delay < num_image*delay:
            total_delay = (datetime.now() - time_begin).total_seconds()

        # Make sure delay is not too off
        if (total_delay - num_image*delay) > _DELAY_WARNING_TOLERANCE:
            print('WARNING! Delay off by more than ' + str(_DELAY_WARNING_TOLERANCE) + '! Delay is probably too short...')

        # Start acquisition
        for cam_num in cam_nums:
            serial = _get_and_validate_serial(cam_num)
            multi_pyspin.start_acquisition(serial)
            print(serial + ' - acquisition started')

        # Grab burst of images
        try:
            for num_burst in range(num_bursts):
                # Get images
                image_dicts = [{} for _ in range(_NUM_CAMS)]
                for cam_num in cam_nums:
                    serial = _get_and_validate_serial(cam_num)
                    image_dicts[cam_num] = multi_pyspin.get_image(serial, _IMAGE_TIMEOUT)  # Use timeout to be safe

                # Make sure no frameids get skipped... once frames get dropped things can get ugly, so just skip the rest
                frameids = [image_dicts[cam_num]['frameid'] for cam_num in cam_nums]
                if frameids.count(num_burst) != len(frameids):
                    print('WARNING! Dropped frames detected. Current frameid is ' + str(num_burst) + '. Returned ' +
                          'frameids are ' + str(frameids) + '. FPS probably too high. Skipping...')
                    break

                # Save images
                for cam_num in cam_nums:
                    serial = _get_and_validate_serial(cam_num)
                    image_dict = image_dicts[cam_num]

                    # Make sure image is complete
                    if image_dict:
                        # Get image name
                        image_name = name_format.format(serial='SERIAL_' + serial,
                                                        datetime='DATETIME_' + str(datetime.fromtimestamp(image_dict['timestamp'])).replace('.', '-').replace(' ', '-').replace('_', '-'),
                                                        cam='CAM_' + str(cam_num+1),
                                                        frameid='FRAMEID_' + str(image_dict['frameid']),
                                                        counter='COUNTER_' + str(counter))

                        # Save image - for now only png is supported
                        image_name = image_name + '.png'
                        image_dict['image'].Save(image_name, PySpin.PNG)
                        print(serial + ' - saved: ' + image_name)

                # Release image buffers - do this at the same time so queue buffer remains relatively synchronized
                for cam_num in cam_nums:
                    image_dicts[cam_num]['image'].Release()
        finally:
            # End acquisition
            for cam_num in cam_nums:
                serial = _get_and_validate_serial(cam_num)
                multi_pyspin.end_acquisition(serial)
                print(serial + ' - acquisition ended')

        # Update counter
        counter += 1

        # Update GUI real quick so it doesnt appear frozen
        _update_fig(_FIG)

        # Check if num_images has been cleared out; if so, stop acquisition
        if _GUI_DICT['num_images_text'].text == '':
            break

    # Set counter
    _GUI_DICT['counter_text'].set_val(str(counter))

    # Restart streams
    for cam_num in cam_nums:
        if streams[cam_num]:  # Used cached streams
            _start_stream(cam_num)


# ------------------- #
# Wrapped stuff       #
# ------------------- #


def _queue_wrapper(func):
    """ wraps function such that it gets inserted into the queue when called """

    @functools.wraps(func)
    def _wrapped_func(*args, **kwargs):
        """ wrapped function """

        _QUEUE.put((func, args, kwargs))

    return _wrapped_func


@_queue_wrapper
def _num_cams_wrapped():
    """ Handles changing the number of cameras """
    global _NUM_CAMS, _SERIALS, _STREAMS, _IMSHOW_DICTS, _HIST_DICTS, _GUI_DICT

    # Get num_cams_text
    num_cams_text = _GUI_DICT['num_cams_text']

    # Get number of cams
    num_cams = int(num_cams_text.text)

    # Make sure its greater than or equal to 1
    if not num_cams >= 1:
        # Set to previous value before raising error
        num_cams_text.set_val(_NUM_CAMS)
        raise RuntimeError('Number of cameras must be greater than or equal to 1!')

    # Stop all streams
    _stop_streams()

    # Set num cams
    _NUM_CAMS = num_cams

    # Reset camera related lists; DO NOT do "[{}] * _NUM_CAMS", as this makes a duplicate reference
    _SERIALS = [None for _ in range(_NUM_CAMS)]
    _STREAMS = [False for _ in range(_NUM_CAMS)]
    _IMSHOW_DICTS = [{} for _ in range(_NUM_CAMS)]
    _HIST_DICTS = [{} for _ in range(_NUM_CAMS)]

    # Clear figure
    _FIG.clf()

    # Re-set GUI
    _GUI_DICT = _multi_fig(_FIG,
                           _NUM_CAMS,
                           _GAIN_MIN,
                           _GAIN_MAX,
                           _GAIN_MIN,
                           _EXPOSURE_MIN,
                           _EXPOSURE_MAX,
                           _EXPOSURE_MIN,
                           _FPS_MIN,
                           _FPS_MAX,
                           _FPS_MIN)
    # Set callbacks
    _set_multi_fig_callbacks()


@_queue_wrapper
def _setup_wrapped(cam_num_new):
    """ Sets up camera """

    # Get yaml path
    yaml_path_new = _GUI_DICT['cam_plot_dicts'][cam_num_new]['setup_text'].text

    # Setup camera
    serial_new = multi_pyspin.setup(yaml_path_new)

    # Set Gain
    gain_new = multi_pyspin.get_gain(serial_new)
    _set_gain_text(cam_num_new, gain_new)
    _set_gain_slider(cam_num_new, gain_new)

    # Set Exposure
    exposure_new = multi_pyspin.get_exposure(serial_new)
    for cam_num in range(_NUM_CAMS):
        # noinspection PyBroadException
        try:
            serial = _get_and_validate_serial(cam_num)
        except:
            continue

        exposure = multi_pyspin.get_exposure(serial)
        if exposure_new != exposure:
            print(serial + ' - different exposure found already set, changing to: ' + str(exposure))
            exposure_new = exposure
            multi_pyspin.set_exposure(serial_new, exposure_new)
            break
    _set_exposure_text(exposure_new)
    _set_exposure_slider(exposure_new)

    # Set FPS
    fps_new = multi_pyspin.get_frame_rate(serial_new)
    for cam_num in range(_NUM_CAMS):
        # noinspection PyBroadException
        try:
            serial = _get_and_validate_serial(cam_num)
        except:
            continue

        fps = multi_pyspin.get_frame_rate(serial)
        if fps_new != fps:
            print(serial + ' - different fps found already set, changing to: ' + str(fps))
            fps_new = fps
            multi_pyspin.set_frame_rate(serial_new, fps_new)
            break
    _set_fps_text(fps_new)
    _set_fps_slider(fps_new)

    # Store serial
    _SERIALS[cam_num_new] = serial_new

    # Set image timeout
    _set_image_timeout(cam_num_new)


@_queue_wrapper
def _start_stream_wrapped(cam_num):
    """ Starts stream of camera """

    _start_stream(cam_num)


@_queue_wrapper
def _stop_stream_wrapped(cam_num):
    """ Stops stream of camera """

    _stop_stream(cam_num)


@_queue_wrapper
def _gain_slider_wrapped(cam_num):
    """ gain slider callback """

    # Get gain value
    gain = _GUI_DICT['cam_plot_dicts'][cam_num]['gain_slider'].val

    try:
        # Set gain for camera
        serial = _get_and_validate_serial(cam_num)
        multi_pyspin.set_gain(serial, gain)
    except:
        # Set value back to text value
        gain = _GUI_DICT['cam_plot_dicts'][cam_num]['gain_text'].text
        if not gain:
            gain = _GAIN_MIN
        else:
            gain = float(gain)
        _set_gain_slider(cam_num, gain)
        raise  # Reraise

    # set gain text
    _set_gain_text(cam_num, gain)


@_queue_wrapper
def _gain_text_wrapped(cam_num):
    """ gain text callback """

    # Get gain value
    gain = _GUI_DICT['cam_plot_dicts'][cam_num]['gain_text'].text
    if not gain:
        return
    gain = float(gain)

    try:
        # Set gain for camera
        serial = _get_and_validate_serial(cam_num)
        multi_pyspin.set_gain(serial, gain)
    except:
        # Set value back to slider value
        gain = _GUI_DICT['cam_plot_dicts'][cam_num]['gain_slider'].val
        _set_gain_text(cam_num, gain)
        raise  # Reraise

    # set gain slider
    _set_gain_slider(cam_num, gain)


@_queue_wrapper
def _exposure_slider_wrapped():
    """ exposure slider callback """

    exposure = _GUI_DICT['exposure_slider'].val

    try:
        # Set exposure for cameras
        _set_exposure(exposure)
    except:
        # Set value back to text value
        exposure = _GUI_DICT['exposure_text'].text
        if not exposure:
            exposure = _EXPOSURE_MIN
        else:
            exposure = float(exposure)
        _set_exposure_slider(exposure)
        raise  # Reraise

    # set exposure text
    _set_exposure_text(exposure)


@_queue_wrapper
def _exposure_text_wrapped():
    """ exposure text callback """

    # Get exposure value
    exposure = _GUI_DICT['exposure_text'].text
    if not exposure:
        return
    exposure = float(exposure)

    try:
        # Set exposure for cameras
        _set_exposure(exposure)
    except:
        # Set value back to slider value
        exposure = _GUI_DICT['exposure_slider'].val
        _set_exposure_text(exposure)
        raise  # Reraise

    # set exposure slider
    _set_exposure_slider(exposure)


@_queue_wrapper
def _fps_slider_wrapped():
    """ fps slider callback """

    fps = _GUI_DICT['fps_slider'].val

    try:
        # Set fps for cameras
        _set_fps(fps)
    except:
        # Set value back to text value
        fps = _GUI_DICT['fps_text'].text
        if not fps:
            fps = _FPS_MIN
        else:
            fps = float(fps)
        _set_fps_slider(fps)
        raise  # Reraise

    # set fps text
    _set_fps_text(fps)


@_queue_wrapper
def _fps_text_wrapped():
    """ fps text callback """

    # Get fps value
    fps = _GUI_DICT['fps_text'].text
    if not fps:
        return
    fps = float(fps)

    try:
        # Set fps for cameras
        _set_fps(fps)
    except:
        # Set value back to slider value
        fps = _GUI_DICT['fps_slider'].val
        _set_fps_text(fps)
        raise  # Reraise

    # set fps slider
    _set_fps_slider(fps)


@_queue_wrapper
def _save_single_image_wrapped(cam_num):
    """ Saves single image """

    _save_images([cam_num])


@_queue_wrapper
def _save_multi_image_wrapped():
    """ Saves multi image """

    # Set primary camera last (assumed to be first camera); this ensures secondary cameras begin acquisition before the
    # primary camera, in case a trigger is set on the secondary cameras.
    _save_images(list(range(1, _NUM_CAMS)) + [0])


@_queue_wrapper
def _stream_images_wrapped():
    """ stream update of images """

    # Get image dicts
    image_dicts = [{} for _ in range(_NUM_CAMS)]
    for cam_num in range(_NUM_CAMS):
        if _STREAMS[cam_num]:
            try:
                # Get image dict
                serial = _get_and_validate_serial(cam_num)
                image_dicts[cam_num] = multi_pyspin.get_image(serial, _IMAGE_TIMEOUT)
            except:
                # If exception occurs, disable this stream
                _stop_stream(cam_num)
                raise  # Reraise error

    # Plot images
    for cam_num in range(_NUM_CAMS):
        if _STREAMS[cam_num]:
            if image_dicts[cam_num]:
                # Get image as numpy array
                image = image_dicts[cam_num]['image'].GetNDArray()

                # Plot image
                _IMSHOW_DICTS[cam_num] = _plot_image(image,
                                                     2**image_dicts[cam_num]['bitsperpixel'] - 1,
                                                     _GUI_DICT['cam_plot_dicts'][cam_num]['image_axes'],
                                                     _IMSHOW_DICTS[cam_num])

                # Plot histogram
                _HIST_DICTS[cam_num] = _plot_hist(image,
                                                  2**image_dicts[cam_num]['bitsperpixel'] - 1,
                                                  _NUM_HISTOGRAM_BINS,
                                                  _GUI_DICT['cam_plot_dicts'][cam_num]['hist_axes'],
                                                  _HIST_DICTS[cam_num])

    # Release images
    for cam_num in range(_NUM_CAMS):
        if _STREAMS[cam_num]:
            image_dicts[cam_num]['image'].Release()


# ------------------- #
# Set callbacks       #
# ------------------- #


def _set_multi_fig_callbacks():
    """ Sets multi fig callbacks """

    # All callbacks are wrapped so they get inserted into a queue first before running

    # num cams
    _GUI_DICT['num_cams_button'].on_clicked(lambda _: _num_cams_wrapped())

    # cam plots
    for i in range(len(_GUI_DICT['cam_plot_dicts'])):
        _GUI_DICT['cam_plot_dicts'][i]['setup_button'].on_clicked(lambda _, i=i: _setup_wrapped(i))
        _GUI_DICT['cam_plot_dicts'][i]['start_stream_button'].on_clicked(lambda _, i=i: _start_stream_wrapped(i))
        _GUI_DICT['cam_plot_dicts'][i]['stop_stream_button'].on_clicked(lambda _, i=i: _stop_stream_wrapped(i))
        _GUI_DICT['cam_plot_dicts'][i]['gain_slider'].on_changed(lambda _, i=i: _gain_slider_wrapped(i))
        _GUI_DICT['cam_plot_dicts'][i]['gain_text'].on_submit(lambda _, i=i: _gain_text_wrapped(i))

    # exposure
    _GUI_DICT['exposure_slider'].on_changed(lambda _: _exposure_slider_wrapped())
    _GUI_DICT['exposure_text'].on_submit(lambda _: _exposure_text_wrapped())

    # fps
    _GUI_DICT['fps_slider'].on_changed(lambda _: _fps_slider_wrapped())
    _GUI_DICT['fps_text'].on_submit(lambda _: _fps_text_wrapped())

    # save cam buttons
    for i in range(len(_GUI_DICT['save_cam_buttons'])):
        _GUI_DICT['save_cam_buttons'][i].on_clicked(lambda _, i=i: _save_single_image_wrapped(i))

    # save multi button
    _GUI_DICT['save_multi_button'].on_clicked(lambda _: _save_multi_image_wrapped())


# ------------------- #
# "public" methods    #
# ------------------- #


def main():
    """ Main program """
    global _NUM_CAMS, _SERIALS, _IMAGE_TIMEOUT, _FIG, _QUEUE, _STREAMS, _IMSHOW_DICTS, _HIST_DICTS, _GUI_DICT

    # Create figure
    _FIG = plt.figure()
    _FIG.show()  # Display it

    # Set GUI
    _GUI_DICT = _multi_fig(_FIG,
                           _NUM_CAMS,
                           _GAIN_MIN,
                           _GAIN_MAX,
                           _GAIN_MIN,
                           _EXPOSURE_MIN,
                           _EXPOSURE_MAX,
                           _EXPOSURE_MIN,
                           _FPS_MIN,
                           _FPS_MAX,
                           _FPS_MIN)
    # Set callbacks
    _set_multi_fig_callbacks()

    # Update plot while figure exists
    # noinspection PyBroadException
    try:
        while plt.fignum_exists(_FIG.number):
            # Handle streams
            if any(_STREAMS):
                _stream_images_wrapped()

            # Handle queue
            while not _QUEUE.empty():
                func, args, kwargs = _QUEUE.get()

                # Attempt to run function, if it fails, display an error message box and continue
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    messagebox.showerror("Error", str(e))

                # Update fig
                _update_fig(_FIG)

            # Update fig
            _update_fig(_FIG)
    except:
        # Only re-raise error if figure is still open
        time.sleep(1)  # I think this will let figure actually close
        if plt.fignum_exists(_FIG.number):
            raise

    print('Cleaning up multi_pyspin_gui...')

    # Stop all streams
    _stop_streams()

    # Clean up
    _NUM_CAMS = 1
    _SERIALS = [None]
    _IMAGE_TIMEOUT = None
    _FIG = None
    _QUEUE = queue.Queue()
    _STREAMS = [False]
    _IMSHOW_DICTS = [{}]
    _HIST_DICTS = [{}]
    _GUI_DICT = None

    return 0


if __name__ == '__main__':
    sys.exit(main())
