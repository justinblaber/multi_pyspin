#!/usr/bin/env python

""" GUI for setting up stereo cameras with PySpin library """

# pylint: disable=line-too-long

import sys
import threading
from tkinter import messagebox

import numpy as np

import matplotlib.pyplot as plt
from matplotlib.widgets import TextBox
from matplotlib.widgets import Button
from matplotlib.widgets import Slider

import stereo_pyspin

# -------------- #
# Callbacks      #
# -------------- #

def find_primary(event): # pylint: disable=unused-argument
    """ Finds primary camera """

    try:
        stereo_pyspin.find_pimary(__GUI_DICT['cam_plot_primary_dict']['find_text'].text)
    except Exception as e: # pylint: disable=broad-except,invalid-name
        messagebox.showerror("Error", str(e))

def find_secondary(event): # pylint: disable=unused-argument
    """ Finds secondary camera """

    try:
        stereo_pyspin.find_pimary(__GUI_DICT['cam_plot_secondary_dict']['find_text'].text)
    except Exception as e: # pylint: disable=broad-except,invalid-name
        messagebox.showerror("Error", str(e))

def init_primary(event): # pylint: disable=unused-argument
    """ Initializes primary camera """

    try:
        stereo_pyspin.init_primary(__GUI_DICT['cam_plot_primary_dict']['init_text'].text)
    except Exception as e: # pylint: disable=broad-except,invalid-name
        messagebox.showerror("Error", str(e))

def init_secondary(event): # pylint: disable=unused-argument
    """ Initializes secondary camera """

    try:
        stereo_pyspin.init_secondary(__GUI_DICT['cam_plot_secondary_dict']['init_text'].text)
    except Exception as e: # pylint: disable=broad-except,invalid-name
        messagebox.showerror("Error", str(e))

def start_acquisition_primary(event): # pylint: disable=unused-argument
    """ Starts acquisition of primary camera """
    global __THREAD_PRIMARY, __STREAM_PRIMARY # pylint: disable=global-statement

    __STREAM_PRIMARY = True
    __THREAD_PRIMARY = threading.Thread(target=stream_image_primary)
    __THREAD_PRIMARY.start()

def start_acquisition_secondary(event): # pylint: disable=unused-argument
    """ Starts acquisition of secondary camera """
    global __THREAD_SECONDARY, __STREAM_SECONDARY # pylint: disable=global-statement

    __STREAM_SECONDARY = True
    __THREAD_SECONDARY = threading.Thread(target=stream_image_secondary)
    __THREAD_SECONDARY.start()

def stop_acquisition_primary(event): # pylint: disable=unused-argument
    """ Starts acquisition of primary camera """
    global __THREAD_PRIMARY, __STREAM_PRIMARY # pylint: disable=global-statement

    __STREAM_PRIMARY = False
    __THREAD_PRIMARY.join()
    __THREAD_PRIMARY = None

def stop_acquisition_secondary(event): # pylint: disable=unused-argument
    """ Stops acquisition of secondary camera """
    global __THREAD_SECONDARY, __STREAM_SECONDARY # pylint: disable=global-statement

    __STREAM_SECONDARY = False
    __THREAD_SECONDARY.join()
    __THREAD_SECONDARY = None

# -------------- #
# GUI            #
# -------------- #

def cam_plot(fig, pos, options_height, padding, cam_str): # pylint: disable=too-many-locals
    """ Creates 'camera' plot; make one of these per camera """

    # Set main sizes
    num_options = 3
    residual_height = pos[3]-(3+num_options)*padding-num_options*options_height
    image_height = residual_height*0.85
    image_width = pos[2]-2*padding
    hist_height = residual_height-image_height

    # Set axes
    image_pos = [pos[0]+padding, pos[1]+pos[3]-image_height-padding, image_width, image_height]
    image_axes = fig.add_axes(image_pos)

    hist_pos = [image_pos[0], image_pos[1]-hist_height-padding, image_width, hist_height]
    hist_axes = fig.add_axes(hist_pos)

    find_button_pos = [image_pos[0],
                       hist_pos[1]-options_height-padding,
                       image_width*0.25,
                       options_height]
    find_button_axes = fig.add_axes(find_button_pos)

    find_text_pos = [find_button_pos[0]+find_button_pos[2]+padding,
                     find_button_pos[1],
                     image_width-find_button_pos[2]-padding,
                     options_height]
    find_text_axes = fig.add_axes(find_text_pos)

    init_button_pos = [find_button_pos[0],
                       find_button_pos[1]-options_height-padding,
                       image_width*0.25,
                       options_height]
    init_button_axes = fig.add_axes(init_button_pos)

    init_text_pos = [init_button_pos[0]+init_button_pos[2]+padding,
                     init_button_pos[1],
                     image_width-init_button_pos[2]-padding,
                     options_height]
    init_text_axes = fig.add_axes(init_text_pos)

    start_acquisition_pos = [init_button_pos[0],
                             init_button_pos[1]-options_height-padding,
                             (image_width-padding)*0.5,
                             options_height]
    start_acquisition_axes = fig.add_axes(start_acquisition_pos)

    stop_acquisition_pos = [start_acquisition_pos[0]+start_acquisition_pos[2]+padding,
                            start_acquisition_pos[1],
                            (image_width-padding)*0.5,
                            options_height]
    stop_acquisition_axes = fig.add_axes(stop_acquisition_pos)

    # Set widgets
    find_button = Button(find_button_axes, 'Find ' + cam_str)
    find_button.label.set_fontsize(7)
    find_text = TextBox(find_text_axes, '')
    init_button = Button(init_button_axes, 'Init ' + cam_str)
    init_button.label.set_fontsize(7)
    init_text = TextBox(init_text_axes, '')
    start_acquisition_button = Button(start_acquisition_axes, 'Start Acquisition')
    start_acquisition_button.label.set_fontsize(7)
    stop_acquisition_button = Button(stop_acquisition_axes, 'Stop Acquisition')
    stop_acquisition_button.label.set_fontsize(8)

    return {'image_axes': image_axes,
            'hist_axes': hist_axes,
            'find_button': find_button,
            'find_text': find_text,
            'init_button': init_button,
            'init_text': init_text,
            'start_acquisition_button': start_acquisition_button,
            'stop_acquisition_button': stop_acquisition_button}

def stereo_gui(): # pylint: disable=too-many-locals
    """ Main function for GUI for setting up stereo cameras with PySpin library """

    # Get figure
    fig = plt.figure()

    # Set main sizes
    padding = 0.01
    options_height = 0.02
    num_options = 8
    cam_plot_height_offset = num_options*options_height+num_options*padding
    cam_plot_width = 0.5
    cam_plot_height = 1-cam_plot_height_offset

    # Primary camera plot
    cam_primary_pos = [0,
                       cam_plot_height_offset,
                       cam_plot_width,
                       cam_plot_height]
    cam_plot_primary_dict = cam_plot(fig, cam_primary_pos, options_height, padding, 'Primary')
    # Set initial values
    cam_plot_primary_dict['init_text'].set_val('primary.yaml')
    # Set callbacks
    cam_plot_primary_dict['find_button'].on_clicked(find_primary)
    cam_plot_primary_dict['init_button'].on_clicked(init_primary)
    cam_plot_primary_dict['start_acquisition_button'].on_clicked(start_acquisition_primary)
    cam_plot_primary_dict['stop_acquisition_button'].on_clicked(stop_acquisition_primary)

    # Secondary camera plot
    cam_secondary_pos = [cam_primary_pos[0]+cam_primary_pos[2],
                         cam_plot_height_offset,
                         cam_plot_width,
                         cam_plot_height]
    cam_plot_secondary_dict = cam_plot(fig, cam_secondary_pos, options_height, padding, 'Secondary')
    # Set initial values
    cam_plot_secondary_dict['init_text'].set_val('secondary.yaml')
    # Set callbacks
    cam_plot_secondary_dict['find_button'].on_clicked(find_secondary)
    cam_plot_secondary_dict['init_button'].on_clicked(init_secondary)
    cam_plot_secondary_dict['start_acquisition_button'].on_clicked(start_acquisition_secondary)
    cam_plot_secondary_dict['stop_acquisition_button'].on_clicked(stop_acquisition_secondary)

    # Set slider padding
    slider_padding = 0.1

    # FPS
    fps_pos = [cam_primary_pos[0]+slider_padding+padding,
               cam_primary_pos[1]-options_height-padding,
               1-2*padding-2*slider_padding,
               options_height]
    fps_axes = fig.add_axes(fps_pos)
    fps_slider = Slider(fps_axes, 'FPS', 1, 200)
    fps_slider.label.set_fontsize(7)

    # Gain
    gain_pos = [fps_pos[0],
                fps_pos[1]-options_height-padding,
                1-2*padding-2*slider_padding,
                options_height]
    gain_axes = fig.add_axes(gain_pos)
    gain_slider = Slider(gain_axes, 'Gain', 1, 200)
    gain_slider.label.set_fontsize(7)

    # Exposure
    exposure_pos = [gain_pos[0],
                    gain_pos[1]-options_height-padding,
                    1-2*padding-2*slider_padding,
                    options_height]
    exposure_axes = fig.add_axes(exposure_pos)
    exposure_slider = Slider(exposure_axes, 'Exposure', 1, 200)
    exposure_slider.label.set_fontsize(7)

    return {'fig': fig,
            'cam_plot_primary_dict': cam_plot_primary_dict,
            'cam_plot_secondary_dict': cam_plot_secondary_dict,
            'fps_slider': fps_slider,
            'gain_slider': gain_slider,
            'exposure_slider': exposure_slider}

__GUI_DICT = stereo_gui()

# -------------- #
# Set up streams #
# -------------- #

__THREAD_PRIMARY = None
__THREAD_SECONDARY = None
__STREAM_PRIMARY = False
__STREAM_SECONDARY = False
__IMSHOW_PRIMARY_DICT = {'imshow': None, 'imshow_size': None}
__IMSHOW_SECONDARY_DICT = {'imshow': None, 'imshow_size': None}
__HIST_PRIMARY_DICT = {'bar': None}
__HIST_SECONDARY_DICT = {'bar': None}

def plot_image(image, image_axes, imshow_dict):
    """ plots image somewhat fast """

    if image is not None:
        if image.shape == imshow_dict['imshow_size']:
            # Can just "set_data" since data is the same size
            imshow_dict['imshow'].set_data(image)
        else:
            # Must reset axes and re-imshow()
            image_axes.cla()
            imshow_dict['imshow'] = image_axes.imshow(image, cmap='gray', vmin=0, vmax=256)
            imshow_dict['imshow_size'] = image.shape
            image_axes.set_xticklabels([])
            image_axes.set_yticklabels([])
            image_axes.set_xticks([])
            image_axes.set_yticks([])

    return imshow_dict

def plot_hist(image, hist_axes, hist_dict):
    """ plots histogram """

    hist, bins = np.histogram(image.ravel(), normed=True, bins=100, range=(0, 255))
    if hist_dict['bar'] is not None:
        # Just reset height
        for i, bar in enumerate(hist_dict['bar']): # pylint: disable=blacklisted-name
            bar.set_height(hist[i])
    else:
        # Must reset axes and plot hist
        hist_axes.cla()
        hist_dict['bar'] = hist_axes.bar(bins[:-1], hist, color='k', width=256/100)
        hist_axes.set_xticklabels([])
        hist_axes.set_yticklabels([])
        hist_axes.set_xticks([])
        hist_axes.set_yticks([])

    return hist_dict

def stream_image_primary():
    """ stream update of primary image """
    global __IMSHOW_PRIMARY_DICT, __HIST_PRIMARY_DICT # pylint: disable=global-statement

    while __STREAM_PRIMARY and plt.fignum_exists(__GUI_DICT['fig'].number):
        # Get image
        image = stereo_pyspin.get_image_primary()

        # Plot image
        __IMSHOW_PRIMARY_DICT = plot_image(image,
                                           __GUI_DICT['cam_plot_primary_dict']['image_axes'],
                                           __IMSHOW_PRIMARY_DICT)

        # Plot histogram
        __HIST_PRIMARY_DICT = plot_hist(image,
                                        __GUI_DICT['cam_plot_primary_dict']['hist_axes'],
                                        __HIST_PRIMARY_DICT)

def stream_image_secondary():
    """ stream update of secondary image """
    global __IMSHOW_SECONDARY_DICT, __HIST_SECONDARY_DICT # pylint: disable=global-statement

    while __STREAM_SECONDARY and plt.fignum_exists(__GUI_DICT['fig'].number):
        # Get image
        image = stereo_pyspin.get_image_secondary()

        # Plot image
        __IMSHOW_SECONDARY_DICT = plot_image(image,
                                             __GUI_DICT['cam_plot_secondary_dict']['image_axes'],
                                             __IMSHOW_SECONDARY_DICT)

        # Plot histogram
        __HIST_SECONDARY_DICT = plot_hist(image,
                                          __GUI_DICT['cam_plot_secondary_dict']['hist_axes'],
                                          __HIST_SECONDARY_DICT)

# -------------- #
# Start gui      #
# -------------- #

def main():
    """ Main program """
    global __IMSHOW_PRIMARY_DICT, __IMSHOW_SECONDARY_DICT, __GUI_DICT # pylint: disable=global-statement
    global __STREAM_PRIMARY, __STREAM_SECONDARY # pylint: disable=global-statement

    # Update plot while figure exists
    while plt.fignum_exists(__GUI_DICT['fig'].number):
        try:
            plt.pause(sys.float_info.min)
        except: # pylint: disable=bare-except
            if plt.fignum_exists(__GUI_DICT['fig'].number):
                # Only re-raise error if figure is still open
                raise

    print('Exiting...')

    # Clean up threads
    if __THREAD_PRIMARY is not None and __THREAD_PRIMARY.is_alive():
        __STREAM_PRIMARY = False
        __THREAD_PRIMARY.join()

    if __THREAD_SECONDARY is not None and __THREAD_SECONDARY.is_alive():
        __STREAM_SECONDARY = False
        __THREAD_SECONDARY.join()

    # For some reason manually deleting these prevents an error on figure close.
    # There might be some circular reference issue which is causing destructor(s)
    # to mess up...
    del __IMSHOW_PRIMARY_DICT
    del __IMSHOW_SECONDARY_DICT
    del __GUI_DICT

    return 0

if __name__ == '__main__':
    sys.exit(main())
