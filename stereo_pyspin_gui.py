#!/usr/bin/env python

""" GUI for setting up stereo cameras with PySpin library """

# NOTE: As of May-15-2018, It appears basically nothing in matplotlib and
# PySpin is thread safe.

# pylint: disable=global-statement

import sys
import queue
from datetime import datetime
from tkinter import messagebox

import numpy as np

import matplotlib.pyplot as plt
from matplotlib.widgets import TextBox
from matplotlib.widgets import Button
from matplotlib.widgets import Slider

from PIL import Image

import stereo_pyspin

# These are min/max values for BFS-U3-32S4M camera
__FPS_MIN = 1
__FPS_MAX = 60              # Manual says 118, but tests indicate its 60
__GAIN_MIN = 0              # Units are dB
__GAIN_MAX = 47             # Units are dB
__EXPOSURE_MIN = 6          # units must be micro seconds
__EXPOSURE_MAX = 29999999   # units must be micro seconds

# Set up GUI params
__QUEUE = queue.Queue()
__STREAM_PRIMARY = False
__STREAM_SECONDARY = False
__IMSHOW_PRIMARY_DICT = {'imshow': None, 'imshow_size': None, 'max_val': None}
__IMSHOW_SECONDARY_DICT = {'imshow': None, 'imshow_size': None, 'max_val': None}
__HIST_PRIMARY_DICT = {'bar': None, 'max_val': None}
__HIST_SECONDARY_DICT = {'bar': None, 'max_val': None}
__GUI_DICT = None

# -------------- #
# Callbacks      #
# -------------- #

def __queue_wrapper(func):
    """ wraps function such that it gets inserted into the queue when called """

    def __wrapped_func(*args, **kwargs):
        """ wrapped function """

        __QUEUE.put((func, args, kwargs))
    return __wrapped_func

def __message_box_wrapper(func):
    """ wraps function in try/except and pops up message box with exception """

    def __wrapped_func(*args, **kwargs):
        """ wrapped function """

        try:
            func(*args, **kwargs)
        except Exception as e: # pylint: disable=broad-except,invalid-name
            messagebox.showerror("Error", str(e))
    return __wrapped_func

@__queue_wrapper
@__message_box_wrapper
def __find_and_init_primary(_=None):
    """ Finds and initializes primary camera """

    find_and_init_text = __GUI_DICT['cam_plot_primary_dict']['find_and_init_text'].text

    print('Finding primary camera...')
    stereo_pyspin.find_primary(find_and_init_text)

    print('Initializing primary camera...')
    stereo_pyspin.init_primary(find_and_init_text)

@__queue_wrapper
@__message_box_wrapper
def __find_and_init_secondary(_=None):
    """ Finds and initializes secondary camera """

    find_and_init_text = __GUI_DICT['cam_plot_secondary_dict']['find_and_init_text'].text

    print('Finding secondary camera...')
    stereo_pyspin.find_secondary(find_and_init_text)

    print('Initializing secondary camera...')
    stereo_pyspin.init_secondary(find_and_init_text)

@__queue_wrapper
@__message_box_wrapper
def __start_acquisition_primary(_=None):
    """ Starts acquisition of primary camera """
    global __STREAM_PRIMARY

    # Make sure it isn't already streaming
    if not __STREAM_PRIMARY:
        # Start streaming on camera
        print('Starting primary camera acquisition...')

        # Set buffer to newest only
        stereo_pyspin.primary_node_cmd('TLStream.StreamBufferHandlingMode',
                                       'SetValue',
                                       'RW',
                                       'PySpin.StreamBufferHandlingMode_NewestOnly')

        # Set acquisition mode to continuous
        stereo_pyspin.primary_node_cmd('AcquisitionMode',
                                       'SetValue',
                                       'RW',
                                       'PySpin.AcquisitionMode_Continuous')

        # Start acqusition
        stereo_pyspin.start_acquisition_primary()

        # Enable stream
        __STREAM_PRIMARY = True

@__queue_wrapper
@__message_box_wrapper
def __start_acquisition_secondary(_=None):
    """ Starts acquisition of secondary camera """
    global __STREAM_SECONDARY

    # Make sure it isn't already streaming
    if not __STREAM_SECONDARY:
        # Start streaming on camera
        print('Starting secondary camera acquisition...')

        # Set buffer to newest only
        stereo_pyspin.secondary_node_cmd('TLStream.StreamBufferHandlingMode',
                                         'SetValue',
                                         'RW',
                                         'PySpin.StreamBufferHandlingMode_NewestOnly')

        # Set acquisition mode to continuous
        stereo_pyspin.secondary_node_cmd('AcquisitionMode',
                                         'SetValue',
                                         'RW',
                                         'PySpin.AcquisitionMode_Continuous')

        # Start acqusition
        stereo_pyspin.start_acquisition_secondary()

        # Enable stream
        __STREAM_SECONDARY = True

@__queue_wrapper
@__message_box_wrapper
def __stop_acquisition_primary(_=None):
    """ Stops acquisition of primary camera """
    global __STREAM_PRIMARY

    # Make sure we're actually streaming
    if __STREAM_PRIMARY:
        # Stop streaming on camera
        print('Stopping primary camera acquisition...')
        stereo_pyspin.end_acquisition_primary()

        # End stream
        __STREAM_PRIMARY = False

@__queue_wrapper
@__message_box_wrapper
def __stop_acquisition_secondary(_=None):
    """ Stops acquisition of secondary camera """
    global __STREAM_SECONDARY

    # Make sure we're actually streaming
    if __STREAM_SECONDARY:
        # Stop streaming on camera
        print('Stopping secondary camera acquisition...')
        stereo_pyspin.end_acquisition_secondary()

        # End stream
        __STREAM_SECONDARY = False

@__queue_wrapper
@__message_box_wrapper
def __fps_slider(_=None):
    """ FPS slider callback """

    fps = __GUI_DICT['fps_slider'].val

    # Update text to match slider
    __GUI_DICT['fps_text'].eventson = False
    __GUI_DICT['fps_text'].set_val(fps)
    __GUI_DICT['fps_text'].eventson = True

    # Set frame rate for cameras
    stereo_pyspin.set_frame_rate(fps)

@__queue_wrapper
@__message_box_wrapper
def __fps_text(_=None):
    """ FPS text callback """

    fps_text = __GUI_DICT['fps_text'].text
    if not fps_text:
        return

    fps = float(fps_text)

    # Update slider to match text
    __GUI_DICT['fps_slider'].eventson = False
    __GUI_DICT['fps_slider'].set_val(fps)
    __GUI_DICT['fps_slider'].eventson = True

    # Set frame rate for cameras
    stereo_pyspin.set_frame_rate(fps)

@__queue_wrapper
@__message_box_wrapper
def __gain_slider(_=None):
    """ Gain slider callback """

    gain = __GUI_DICT['gain_slider'].val

    # Update text to match slider
    __GUI_DICT['gain_text'].eventson = False
    __GUI_DICT['gain_text'].set_val(gain)
    __GUI_DICT['gain_text'].eventson = True

    # Set gain for cameras
    stereo_pyspin.set_gain(gain)

@__queue_wrapper
@__message_box_wrapper
def __gain_text(_=None):
    """ gain text callback """

    gain_text = __GUI_DICT['gain_text'].text
    if not gain_text:
        return

    gain = float(gain_text)

    # Update slider to match text
    __GUI_DICT['gain_slider'].eventson = False
    __GUI_DICT['gain_slider'].set_val(gain)
    __GUI_DICT['gain_slider'].eventson = True

    # Set gain for cameras
    stereo_pyspin.set_gain(gain)

@__queue_wrapper
@__message_box_wrapper
def __exposure_slider(_=None):
    """ Exposure slider callback """

    exposure = __GUI_DICT['exposure_slider'].val

    # Update text to match slider
    __GUI_DICT['exposure_text'].eventson = False
    __GUI_DICT['exposure_text'].set_val(exposure)
    __GUI_DICT['exposure_text'].eventson = True

    # Set exposure for cameras
    stereo_pyspin.set_exposure(exposure)

@__queue_wrapper
@__message_box_wrapper
def __exposure_text(_=None):
    """ exposure text callback """

    exposure_text = __GUI_DICT['exposure_text'].text
    if not exposure_text:
        return

    exposure = float(exposure_text)

    # Update slider to match text
    __GUI_DICT['exposure_slider'].eventson = False
    __GUI_DICT['exposure_slider'].set_val(exposure)
    __GUI_DICT['exposure_slider'].eventson = True

    # Set exposure for cameras
    stereo_pyspin.set_exposure(exposure)

@__queue_wrapper
@__message_box_wrapper
def __save_images(_=None):
    """ Care is taken here to ensure images are taken close to each other in time """

    # Get name format, counter, and number of images
    name_format = __GUI_DICT['name_format_text'].text
    counter = int(__GUI_DICT['counter_text'].text)
    num_images = int(__GUI_DICT['save_images_text'].text)

    # Stop Acquisition to make sure both streams start at the same time
    if __STREAM_PRIMARY:
        __stop_acquisition_primary()
    if __STREAM_SECONDARY:
        __stop_acquisition_secondary()

    # Grab images
    for i in range(num_images):
        # Set buffer to newest only
        stereo_pyspin.primary_node_cmd('TLStream.StreamBufferHandlingMode',
                                       'SetValue',
                                       'RW',
                                       'PySpin.StreamBufferHandlingMode_NewestOnly')

        stereo_pyspin.secondary_node_cmd('TLStream.StreamBufferHandlingMode',
                                         'SetValue',
                                         'RW',
                                         'PySpin.StreamBufferHandlingMode_NewestOnly')

        # Set acquisition mode to continuous
        stereo_pyspin.primary_node_cmd('AcquisitionMode',
                                       'SetValue',
                                       'RW',
                                       'PySpin.AcquisitionMode_SingleFrame')

        stereo_pyspin.secondary_node_cmd('AcquisitionMode',
                                         'SetValue',
                                         'RW',
                                         'PySpin.AcquisitionMode_SingleFrame')

        # Start acquisition - Must start secondary acquisition first due to trigger mode!
        stereo_pyspin.start_acquisition_secondary()
        stereo_pyspin.start_acquisition_primary()

        # Get image dicts
        image_primary_dict = stereo_pyspin.get_image_primary()
        print('here primary')
        image_secondary_dict = stereo_pyspin.get_image_secondary()
        print('here secondary')

        # Save images
        primary_name = name_format.format(serial=stereo_pyspin.get_serial_primary(),
                                          datetime=str(datetime.fromtimestamp(image_primary_dict['timestamp']/1e6)),
                                          counter=counter+i,
                                          L_R='L')
        # Remove spaces and dots; for now, only png is supported
        primary_name = primary_name.replace(' ', '_').replace('.', '_') + '.png'
        print(primary_name)
        Image.fromarray(image_primary_dict['data'].astype(np.uint32)).save(primary_name,
                                                                           optimize=False,
                                                                           compress_level=0,
                                                                           bits=image_primary_dict['bitsperpixel'])

        secondary_name = name_format.format(serial=stereo_pyspin.get_serial_secondary(),
                                            datetime=str(datetime.fromtimestamp(image_secondary_dict['timestamp']/1e6)),
                                            counter=counter+i,
                                            L_R='R')
        # Remove spaces and dots; for now, only png is supported
        secondary_name = secondary_name.replace(' ', '_').replace('.', '_') + '.png'
        print(secondary_name)
        Image.fromarray(image_secondary_dict['data'].astype(np.uint32)).save(secondary_name,
                                                                             optimize=False,
                                                                             compress_level=0,
                                                                             bits=image_secondary_dict['bitsperpixel'])

        # Stop acquisition
        stereo_pyspin.end_acquisition_primary()
        stereo_pyspin.end_acquisition_secondary()

    # Update counter
    __GUI_DICT['counter_text'].set_val(str(counter+num_images))

    # Start acquisition if streaming was enabled
    if __STREAM_PRIMARY:
        __start_acquisition_primary()
    if __STREAM_SECONDARY:
        __start_acquisition_secondary()

# -------------- #
# GUI            #
# -------------- #

def __cam_plot(fig, pos, cam_str, options_height, padding): # pylint: disable=too-many-locals
    """ Creates 'camera' plot; make one of these per camera """

    # Set position params
    num_options = 2
    residual_height = pos[3]-(3+num_options)*padding-num_options*options_height
    image_height = residual_height*0.85
    image_width = pos[2]-2*padding
    hist_height = residual_height-image_height

    # Set axes
    image_pos = [pos[0]+padding, pos[1]+pos[3]-image_height-padding, image_width, image_height]
    image_axes = fig.add_axes(image_pos)
    image_axes.set_xticklabels([])
    image_axes.set_yticklabels([])
    image_axes.set_xticks([])
    image_axes.set_yticks([])

    hist_pos = [image_pos[0], image_pos[1]-hist_height-padding, image_width, hist_height]
    hist_axes = fig.add_axes(hist_pos)
    hist_axes.set_xticklabels([])
    hist_axes.set_yticklabels([])
    hist_axes.set_xticks([])
    hist_axes.set_yticks([])

    find_and_init_button_pos = [image_pos[0],
                                hist_pos[1]-options_height-padding,
                                (image_width-padding)*0.5,
                                options_height]
    find_and_init_button_axes = fig.add_axes(find_and_init_button_pos)

    find_and_init_text_pos = [find_and_init_button_pos[0]+find_and_init_button_pos[2]+padding,
                              find_and_init_button_pos[1],
                              (image_width-padding)*0.5,
                              options_height]
    find_and_init_text_axes = fig.add_axes(find_and_init_text_pos)

    start_acquisition_pos = [find_and_init_button_pos[0],
                             find_and_init_button_pos[1]-options_height-padding,
                             (image_width-padding)*0.5,
                             options_height]
    start_acquisition_axes = fig.add_axes(start_acquisition_pos)

    stop_acquisition_pos = [start_acquisition_pos[0]+start_acquisition_pos[2]+padding,
                            start_acquisition_pos[1],
                            (image_width-padding)*0.5,
                            options_height]
    stop_acquisition_axes = fig.add_axes(stop_acquisition_pos)

    # Set widgets
    find_and_init_button = Button(find_and_init_button_axes, 'Find and Init ' + cam_str)
    find_and_init_button.label.set_fontsize(7)
    find_and_init_text = TextBox(find_and_init_text_axes, '')
    start_acquisition_button = Button(start_acquisition_axes, 'Start Acquisition')
    start_acquisition_button.label.set_fontsize(7)
    stop_acquisition_button = Button(stop_acquisition_axes, 'Stop Acquisition')
    stop_acquisition_button.label.set_fontsize(8)

    return {'image_axes': image_axes,
            'hist_axes': hist_axes,
            'find_and_init_button': find_and_init_button,
            'find_and_init_text': find_and_init_text,
            'start_acquisition_button': start_acquisition_button,
            'stop_acquisition_button': stop_acquisition_button}

def __slider_with_text(fig, pos, slider_str, val_min, val_max, val_default, padding): # pylint: disable=too-many-arguments
    """ Creates a slider with text box given a position """

    # Set position params
    slider_padding = 0.1
    slider_text_width = 0.2

    # Slider
    slider_pos = [pos[0]+slider_padding+padding,
                  pos[1],
                  pos[2]-slider_padding-3*padding-slider_text_width,
                  pos[3]]
    slider_axes = fig.add_axes(slider_pos)
    slider = Slider(slider_axes,
                    slider_str,
                    val_min,
                    val_max,
                    valinit=val_default,
                    dragging=False)
    slider.label.set_fontsize(7)
    slider.valtext.set_visible(False)

    # Text
    text_pos = [slider_pos[0]+slider_pos[2]+padding,
                slider_pos[1],
                slider_text_width,
                pos[3]]
    text_axes = fig.add_axes(text_pos)
    text = TextBox(text_axes, '')

    return (slider, text)

def __stereo_gui(): # pylint: disable=too-many-locals,too-many-statements
    """ Main function for GUI for setting up stereo cameras with PySpin library """

    # Get figure
    fig = plt.figure()

    # Set position params
    padding = 0.01
    options_height = 0.02
    num_options = 6
    cam_plot_height_offset = num_options*options_height+num_options*padding
    cam_plot_width = 0.5
    cam_plot_height = 1-cam_plot_height_offset

    # Primary camera plot
    cam_primary_pos = [0,
                       cam_plot_height_offset,
                       cam_plot_width,
                       cam_plot_height]
    cam_plot_primary_dict = __cam_plot(fig,
                                       cam_primary_pos,
                                       'Primary',
                                       options_height,
                                       padding)
    # Set initial values
    cam_plot_primary_dict['find_and_init_text'].set_val('primary.yaml')
    # Set callbacks
    cam_plot_primary_dict['find_and_init_button'].on_clicked(__find_and_init_primary)
    cam_plot_primary_dict['start_acquisition_button'].on_clicked(__start_acquisition_primary)
    cam_plot_primary_dict['stop_acquisition_button'].on_clicked(__stop_acquisition_primary)

    # Secondary camera plot
    cam_secondary_pos = [cam_primary_pos[0]+cam_primary_pos[2],
                         cam_plot_height_offset,
                         cam_plot_width,
                         cam_plot_height]
    cam_plot_secondary_dict = __cam_plot(fig,
                                         cam_secondary_pos,
                                         'Secondary',
                                         options_height,
                                         padding)
    # Set initial values
    cam_plot_secondary_dict['find_and_init_text'].set_val('secondary.yaml')
    # Set callbacks
    cam_plot_secondary_dict['find_and_init_button'].on_clicked(__find_and_init_secondary)
    cam_plot_secondary_dict['start_acquisition_button'].on_clicked(__start_acquisition_secondary)
    cam_plot_secondary_dict['stop_acquisition_button'].on_clicked(__stop_acquisition_secondary)

    # FPS
    fps_pos = [0, cam_primary_pos[1]-options_height, 1, options_height]
    (fps_slider, fps_text) = __slider_with_text(fig,
                                                fps_pos,
                                                'FPS',
                                                __FPS_MIN,
                                                __FPS_MAX,
                                                __FPS_MIN,
                                                padding)
    # Set callbacks
    fps_slider.on_changed(__fps_slider)
    fps_text.on_submit(__fps_text)

    # Gain
    gain_pos = [0, fps_pos[1]-options_height-padding, 1, options_height]
    (gain_slider, gain_text) = __slider_with_text(fig,
                                                  gain_pos,
                                                  'Gain',
                                                  __GAIN_MIN,
                                                  __GAIN_MAX,
                                                  __GAIN_MIN,
                                                  padding)
    # Set callbacks
    gain_slider.on_changed(__gain_slider)
    gain_text.on_submit(__gain_text)

    # Exposure
    exposure_pos = [0, gain_pos[1]-options_height-padding, 1, options_height]
    (exposure_slider, exposure_text) = __slider_with_text(fig,
                                                          exposure_pos,
                                                          'Exposure',
                                                          __EXPOSURE_MIN,
                                                          __EXPOSURE_MAX,
                                                          __EXPOSURE_MIN,
                                                          padding)
    # Set callbacks
    exposure_slider.on_changed(__exposure_slider)
    exposure_text.on_submit(__exposure_text)

    # Set name format
    name_format_pos = [(0.5-2*padding)*0.1875+2*padding,
                       exposure_pos[1]-options_height-padding,
                       (0.5-2*padding)*0.8125-padding,
                       options_height]
    name_format_axes = fig.add_axes(name_format_pos)
    name_format_text = TextBox(name_format_axes, 'Name format')
    name_format_text.label.set_fontsize(7)
    name_format_text.set_val('{serial}_{datetime}_{counter}_{L_R}')

    # Set counter
    counter_pos = [name_format_pos[0]+name_format_pos[2]+padding+(0.5-2*padding)*0.1875+2*padding,
                   exposure_pos[1]-options_height-padding,
                   (0.5-2*padding)*0.8125-padding,
                   options_height]
    counter_axes = fig.add_axes(counter_pos)
    counter_text = TextBox(counter_axes, 'Counter')
    counter_text.label.set_fontsize(7)
    counter_text.set_val(1)

    # Set save images button
    save_images_button_pos = [padding,
                              name_format_pos[1]-options_height-padding,
                              0.5-2*padding,
                              options_height]
    save_images_button_axes = fig.add_axes(save_images_button_pos)
    save_images_button = Button(save_images_button_axes, 'Save Image(s)')
    save_images_button.label.set_fontsize(7)
    # Set callback
    save_images_button.on_clicked(__save_images)

    # Set save image text
    save_images_text_pos = [save_images_button_pos[0]+save_images_button_pos[2]+padding+(0.5-2*padding)*0.1875+2*padding, # pylint: disable=line-too-long
                            name_format_pos[1]-options_height-padding,
                            (0.5-2*padding)*0.8125-padding,
                            options_height]
    save_images_text_axes = fig.add_axes(save_images_text_pos)
    save_images_text = TextBox(save_images_text_axes, '#')
    save_images_text.label.set_fontsize(7)
    save_images_text.set_val(1)

    # Set save config button
    save_config_button_pos = [padding,
                              save_images_button_pos[1]-options_height-padding,
                              1-2*padding,
                              options_height]
    save_config_button_axes = fig.add_axes(save_config_button_pos)
    save_config_button = Button(save_config_button_axes, 'Save Config')
    save_config_button.label.set_fontsize(7)

    return {'fig': fig,
            'cam_plot_primary_dict': cam_plot_primary_dict,
            'cam_plot_secondary_dict': cam_plot_secondary_dict,
            'fps_slider': fps_slider,
            'fps_text': fps_text,
            'gain_slider': gain_slider,
            'gain_text': gain_text,
            'exposure_slider': exposure_slider,
            'exposure_text': exposure_text,
            'name_format_text': name_format_text,
            'counter_text': counter_text,
            'save_images_button': save_images_button,
            'save_images_text': save_images_text,
            'save_config_button': save_config_button}

# -------------- #
# Set up streams #
# -------------- #

def __plot_image(image, max_val, image_axes, imshow_dict):
    """ plots image somewhat fast """

    # If image size changes or max val changes, then we must replot imshow
    if image.shape != imshow_dict['imshow_size'] or max_val != imshow_dict['max_val']:
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

def __plot_hist(image, max_val, hist_axes, hist_dict):
    """ plots histogram """

    # Calculate histogram
    num_bins = 100
    hist, bins = np.histogram(image.ravel(), normed=True, bins=num_bins, range=(0, max_val))

    # If histogram hasn't been plotted yet or max val changes, then we must replot histogram
    if hist_dict['bar'] is None or hist_dict['max_val'] != max_val:
        # Must reset axes and plot hist
        hist_axes.cla()
        hist_dict['bar'] = hist_axes.bar(bins[:-1], hist, color='k', width=(max_val+1)/num_bins)
        hist_dict['max_val'] = max_val
        hist_axes.set_xticklabels([])
        hist_axes.set_yticklabels([])
        hist_axes.set_xticks([])
        hist_axes.set_yticks([])
    else:
        # Just reset height
        for i, bar in enumerate(hist_dict['bar']): # pylint: disable=blacklisted-name
            bar.set_height(hist[i])

    return hist_dict

@__queue_wrapper
@__message_box_wrapper
def __stream_image_primary():
    """ stream update of primary image """
    global __IMSHOW_PRIMARY_DICT, __HIST_PRIMARY_DICT

    try:
        # Get image dict
        image_dict = stereo_pyspin.get_image_primary()

        if 'data' in image_dict:
            # Plot image
            __IMSHOW_PRIMARY_DICT = __plot_image(image_dict['data'],
                                                 2**image_dict['bitsperpixel']-1,
                                                 __GUI_DICT['cam_plot_primary_dict']['image_axes'],
                                                 __IMSHOW_PRIMARY_DICT)

            # Plot histogram
            __HIST_PRIMARY_DICT = __plot_hist(image_dict['data'],
                                              2**image_dict['bitsperpixel']-1,
                                              __GUI_DICT['cam_plot_primary_dict']['hist_axes'],
                                              __HIST_PRIMARY_DICT)
    except: # pylint: disable=bare-except
        if __STREAM_PRIMARY:
            # Only re-raise error if stream is enabled
            raise

@__queue_wrapper
@__message_box_wrapper
def __stream_image_secondary():
    """ stream update of secondary image """
    global __IMSHOW_SECONDARY_DICT, __HIST_SECONDARY_DICT

    try:
        # Get image dict
        image_dict = stereo_pyspin.get_image_secondary()

        if 'data' in image_dict:
            # Plot image
            __IMSHOW_SECONDARY_DICT = __plot_image(image_dict['data'],
                                                   2**image_dict['bitsperpixel']-1,
                                                   __GUI_DICT['cam_plot_secondary_dict']['image_axes'], # pylint: disable=line-too-long
                                                   __IMSHOW_SECONDARY_DICT)

            # Plot histogram
            __HIST_SECONDARY_DICT = __plot_hist(image_dict['data'],
                                                2**image_dict['bitsperpixel']-1,
                                                __GUI_DICT['cam_plot_secondary_dict']['hist_axes'],
                                                __HIST_SECONDARY_DICT)
    except: # pylint: disable=bare-except
        if __STREAM_SECONDARY:
            # Only re-raise error if stream is enabled
            raise

# -------------- #
# Start gui      #
# -------------- #

def main():
    """ Main program """
    global __QUEUE
    global __STREAM_PRIMARY, __STREAM_SECONDARY
    global __IMSHOW_PRIMARY_DICT, __IMSHOW_SECONDARY_DICT
    global __HIST_PRIMARY_DICT, __HIST_SECONDARY_DICT
    global __GUI_DICT

    # Set GUI
    __GUI_DICT = __stereo_gui()

    # Update plot while figure exists
    while plt.fignum_exists(__GUI_DICT['fig'].number): # pylint: disable=unsubscriptable-object
        try:
            # Update plot
            plt.pause(sys.float_info.min)

            # Handle streams
            if __STREAM_PRIMARY:
                __stream_image_primary()

            if __STREAM_SECONDARY:
                __stream_image_secondary()

            # Handle queue
            while not __QUEUE.empty():
                func, args, kwargs = __QUEUE.get()
                func(*args, **kwargs)
        except: # pylint: disable=bare-except
            if plt.fignum_exists(__GUI_DICT['fig'].number):
                # Only re-raise error if figure is still open
                raise

    # Clean up
    __QUEUE = queue.Queue()
    __STREAM_PRIMARY = False
    __STREAM_SECONDARY = False
    __IMSHOW_PRIMARY_DICT = {'imshow': None, 'imshow_size': None}
    __IMSHOW_SECONDARY_DICT = {'imshow': None, 'imshow_size': None}
    __HIST_PRIMARY_DICT = {'bar': None}
    __HIST_SECONDARY_DICT = {'bar': None}
    __GUI_DICT = None

    print('Exiting...')

    return 0

if __name__ == '__main__':
    sys.exit(main())
