# -*- coding: utf-8 -*-
#!/usr/bin/python
#
# Written by Arjun Sarwal <arjun@laptop.org>
# Copyright (C) 2007, Arjun Sarwal
# Copyright (C) 2009-11 Walter Bender
# Copyright (C) 2009, Benjamin Berg, Sebastian Berg
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# You should have received a copy of the GNU General Public License
# along with this library; if not, write to the Free Software
# Foundation, 51 Franklin Street, Suite 500 Boston, MA 02110-1335 USA


import pygst
pygst.require("0.10")
import gtk
import pango
import os
import csv
import time

from gettext import gettext as _

from sugar.activity import activity
try:  # 0.86+ toolbar widgets
    from sugar.graphics.toolbarbox import ToolbarBox
    _has_toolbarbox = True
except ImportError:
    _has_toolbarbox = False

if _has_toolbarbox:
    from sugar.activity.widgets import ActivityToolbarButton
    from sugar.activity.widgets import StopButton
    from sugar.graphics.toolbarbox import ToolbarButton
else:
    from sugar.activity.activity import ActivityToolbox
from sugar.graphics import style
from sugar.datastore import datastore
from sugar.graphics.toolbutton import ToolButton

try:
    from sugar import profile
    _using_gconf = False
except ImportError:
    _using_gconf = True
try:
    import gconf
except ImportError:
    _using_gconf = False

from journal import DataLogger
from audiograb import AudioGrab_XO175, AudioGrab_XO15, AudioGrab_XO1, \
    AudioGrab_Unknown
from drawwaveform import DrawWaveform
from toolbar_side import SideToolbar
from sensor_toolbar import SensorToolbar
#Added by Butia
from butia_toolbar import ButiaToolbar
from ringbuffer import RingBuffer1d
#Butia end
from tuning_toolbar import TuningToolbar, InstrumentToolbar
from config import ICONS_DIR, XO1, XO15, XO175, UNKNOWN, INSTRUMENT_DICT

import logging

log = logging.getLogger('measure-activity')
log.setLevel(logging.DEBUG)
logging.basicConfig()

# Added by BUTIA
# agrego un handler para loguee a un archivo solo, tuve que descartivar el otro 
logfile = logging.getLogger()
file_name = 'measure.log'
handler = logging.handlers.RotatingFileHandler(file_name, backupCount=0)
logfile.addHandler(handler)
bobot_cmd_on = './bobot.sh on &'
bobot_cmd_off = './bobot.sh off &'
bobot_delay_start = 5
#Butia end



PREFIX = '♬'


def _get_hardware():
    ''' Determine whether we are using XO 1.0, 1.5, or "unknown" hardware '''
    product = _get_dmi('product_name')
    if product is None:
        if os.path.exists('/sys/devices/platform/lis3lv02d/position'):
            return XO175
        elif os.path.exists('/etc/olpc-release') or \
             os.path.exists('/sys/power/olpc-pm'):
            return XO1
        else:
            return UNKNOWN
    if product != 'XO':
        return UNKNOWN
    version = _get_dmi('product_version')
    if version == '1' or version == '1.0':
        return XO1
    elif version == '1.5':
        return XO15
    elif version == '1.75':
        return XO175
    else:
        return UNKNOWN


def _get_dmi(node):
    ''' The desktop management interface should be a reliable source
    for product and version information. '''
    path = os.path.join('/sys/class/dmi/id', node)
    try:
        return open(path).readline().strip()
    except:
        return None


class MeasureActivity(activity.Activity):
    ''' Oscilloscope Sugar activity '''

    def __init__(self, handle):
        ''' Init canvas, toolbars, etc.
        The toolbars are in sensor_toolbar.py and toolbar_side.py
        The audio controls are in audiograb.py
        The rendering happens in drawwaveform.py
        Logging is in journal.py '''

        activity.Activity.__init__(self, handle)

        self.mode_images = {}
        self.mode_images['sound'] = gtk.gdk.pixbuf_new_from_file_at_size(
            os.path.join(ICONS_DIR, 'media-audio.svg'), 45, 45)
        self.mode_images['resistance'] = gtk.gdk.pixbuf_new_from_file_at_size(
            os.path.join(ICONS_DIR, 'resistance.svg'), 45, 45)
        self.mode_images['voltage'] = gtk.gdk.pixbuf_new_from_file_at_size(
            os.path.join(ICONS_DIR, 'voltage.svg'), 45, 45)

        self._using_gconf = _using_gconf
        self.icon_colors = self.get_icon_colors_from_sugar()
        self.stroke_color, self.fill_color = self.icon_colors.split(',')
        self.nick = self.get_nick_from_sugar()
        self.CONTEXT = ''
        self.adjustmentf = None  # Freq. slider control
        self.hw = _get_hardware()
        self.new_recording = False
        self.session_id = 0
        self.read_metadata()

        self._active = True
        self._dsobject = None

        self.connect('notify::active', self._notify_active_cb)
        self.connect('destroy', self.on_quit)

        self.data_logger = DataLogger(self)

        self.hw = _get_hardware()
        log.debug('running on %s hardware' % (self.hw))
        self.wave = DrawWaveform(self)
        if self.hw == XO15:
            self.audiograb = AudioGrab_XO15(self.wave.new_buffer, self)
        elif self.hw == XO175:
            self.audiograb = AudioGrab_XO175(self.wave.new_buffer, self)
        elif self.hw == XO1:
            self.audiograb = AudioGrab_XO1(self.wave.new_buffer, self)
        else:
            self.audiograb = AudioGrab_Unknown(self.wave.new_buffer, self)

        # no sharing
        self.max_participants = 1

        self.has_toolbarbox = _has_toolbarbox

        box3 = gtk.HBox(False, 0)
        box3.pack_start(self.wave, True, True, 0)

        # We need event boxes in order to set the background color.
        side_eventboxes = []
        self.side_toolbars = []
        for i in range(self.audiograb.channels):
            side_eventboxes.append(gtk.EventBox())
            side_eventboxes[i].modify_bg(
                gtk.STATE_NORMAL, style.COLOR_TOOLBAR_GREY.get_gdk_color())
            self.side_toolbars.append(SideToolbar(self, channel=i))
            side_eventboxes[i].add(self.side_toolbars[i].box1)
            box3.pack_start(side_eventboxes[i], False, True, 0)

        event_box = gtk.EventBox()
        self.text_box = gtk.Label()
        self.text_box.set_justify(gtk.JUSTIFY_LEFT)
        alist = pango.AttrList()
        alist.insert(pango.AttrForeground(65535, 65535, 65535, 0, -1))
        self.text_box.set_attributes(alist)
        event_box.add(self.text_box)
        event_box.modify_bg(
            gtk.STATE_NORMAL, style.COLOR_TOOLBAR_GREY.get_gdk_color())

        box1 = gtk.VBox(False, 0)
        box1.pack_start(box3, True, True, 0)
        box1.pack_start(event_box, False, True, 0)

        self.set_canvas(box1)

        if self.has_toolbarbox:
            toolbox = ToolbarBox()

            activity_button = ActivityToolbarButton(self)
            toolbox.toolbar.insert(activity_button, 0)
            activity_button.show()
        else:
            toolbox = ActivityToolbox(self)

            # no sharing
            if hasattr(toolbox, 'share'):
                toolbox.share.hide()
            elif hasattr(toolbox, 'props'):
                toolbox.props.visible = False
            self.set_toolbox(toolbox)

        self.sensor_toolbar = SensorToolbar(self, self.audiograb.channels)
        #Added by Butia
        # Enciendo el bobot Server
        log.debug('Starting Bobot-Server...')
        os.system(bobot_cmd_on)
        log.debug("Start : %s" % time.ctime())
        time.sleep(bobot_delay_start)        
        log.debug("Started : %s" % time.ctime())
        self.butia_toolbar = ButiaToolbar(self, self.audiograb.channels)        
        #Butia end
        self.tuning_toolbar = TuningToolbar(self)
        self.new_instrument_toolbar = InstrumentToolbar(self)
        self.control_toolbar = gtk.Toolbar()
        if self.has_toolbarbox:
            sensor_button = ToolbarButton(
                label=_('Sensors'),
                page=self.sensor_toolbar,
                icon_name='sensor-tools')
            toolbox.toolbar.insert(sensor_button, -1)
            #Added by Butia
            sensor_button.connect('clicked', self._sensor_toolbar_cb)
            #Butia end
            sensor_button.show()
			#Added by Butia
            butia_button = ToolbarButton(
                label=_('Butia'),
                page=self.butia_toolbar,
                icon_name='butia-tools')
            toolbox.toolbar.insert(butia_button, -1)
            butia_button.connect('clicked', self._butia_toolbar_cb)            
            butia_button.show()
            #Butia end
            tuning_button = ToolbarButton(
                # TRANS: Tuning insruments
                label=_('Tuning'),
                page=self.tuning_toolbar,
                icon_name='tuning-tools')
            toolbox.toolbar.insert(tuning_button, -1)
            tuning_button.show()
            new_instrument_button = ToolbarButton(
                label=_('Add instrument'),
                page=self.new_instrument_toolbar,
                icon_name='view-source')
            toolbox.toolbar.insert(new_instrument_button, -1)
            new_instrument_button.show()
        else:
            toolbox.add_toolbar(_('Sensors'), self.sensor_toolbar)
            #Added by butia
            toolbox.add_toolbar(_('Butia'), self.butia_toolbar)
            #Butia end
            # TRANS: Tuning insruments
            toolbox.add_toolbar(_('Tuning'), self.tuning_toolbar)
            toolbox.add_toolbar(_('Add instrument'),
                                self.new_instrument_toolbar)
            toolbox.add_toolbar(_('Controls'), self.control_toolbar)
        self.sensor_toolbar.show()
        #Added by butia
        self.butia_toolbar.show()
        #Butia end

        if self.has_toolbarbox:
            # Set up Frequency-domain Button
            self.freq = ToolButton('domain-time')
            toolbox.toolbar.insert(self.freq, -1)
            self.freq.show()
            self.freq.set_tooltip(_('Time Base'))
            self.freq.connect('clicked', self.timefreq_control)

            self.sensor_toolbar.add_frequency_slider(toolbox.toolbar)
            self._pause = ToolButton('media-playback-pause')
            toolbox.toolbar.insert(self._pause, -1)
            self._pause.set_tooltip(_('Freeze the display'))
            self._pause.connect('clicked', self._pause_play_cb)

            self._capture = ToolButton('image-saveoff')
            toolbox.toolbar.insert(self._capture, -1)
            self._capture.set_tooltip(_('Capture sample now'))
            self._capture.connect('clicked', self._capture_cb)

            separator = gtk.SeparatorToolItem()
            separator.props.draw = False
            separator.set_expand(True)
            toolbox.toolbar.insert(separator, -1)
            separator.show()

            stop_button = StopButton(self)
            stop_button.props.accelerator = _('<Ctrl>Q')
            toolbox.toolbar.insert(stop_button, -1)
            stop_button.show()

            self.set_toolbox(toolbox)
            sensor_button.set_expanded(True)

        else:
            # Set up Frequency-domain Button
            self.freq = ToolButton('domain-time')
            self.control_toolbar.insert(self.freq, -1)
            self.freq.show()
            self.freq.set_tooltip(_('Time Base'))
            self.freq.connect('clicked', self.timefreq_control)

            self.sensor_toolbar.add_frequency_slider(self.control_toolbar)

            separator = gtk.SeparatorToolItem()
            separator.props.draw = True
            self.control_toolbar.insert(separator, -1)
            separator.show()

            self._pause = ToolButton('media-playback-pause')
            self.control_toolbar.insert(self._pause, -1)
            self._pause.set_tooltip(_('Freeze the display'))
            self._pause.connect('clicked', self._pause_play_cb)

            self._capture = ToolButton('image-saveoff')
            self.control_toolbar.insert(self._capture, -1)
            self._capture.set_tooltip(_('Capture sample now'))
            self._capture.connect('clicked', self._capture_cb)

            toolbox.set_current_toolbar(1)

        toolbox.show()
        self.sensor_toolbar.update_page_size()

        self.show_all()

        self._first = True

        # Always start in 'sound' mode.
        self.sensor_toolbar.set_mode('sound')
        self.sensor_toolbar.set_sound_context()
        self.sensor_toolbar.set_show_hide_windows()
        self.wave.set_active(True)
        self.wave.set_context_on()

    #Added by Butia
    def _sensor_toolbar_cb(self, button=None):
        '''Callback al hacer clic en sensor toolbar'''
        log.debug('Click en sensor toolbar')        
        self.sensor_toolbar.set_mode('sound')
        self.sensor_toolbar.set_sound_context()
        self.sensor_toolbar.set_show_hide_windows()
        self.limpiar_canales()
        #sensor_button.set_expanded(True)
        #TODO que aparezca seleccionado el mic por defecto
        self.CONTEXT = 'sound'        
        
    #Added by Butia            
    def _butia_toolbar_cb(self, button=None):
        '''Callback al hacer clic en butia toolbar'''
        log.debug('Click en butia toolbar')    
        self.audiograb.stop_grabbing()
        
        self.limpiar_canales()                                                
        log.debug('CONTEXTO ANTERIOR: %s' % self.CONTEXT)
        self.CONTEXT = 'butia'
        
        #El metodo update_string_for_textbox() esta muy acoplado con SensorToolbar,
        #por ese se utiliza desde esa clase.
        self.sensor_toolbar.update_string_for_textbox()        

    #Added by butia
    def limpiar_canales(self):
        for i in range(self.audiograb.channels):
            self.wave.ringbuffer[i] = RingBuffer1d(self.wave.max_samples,
                                            dtype='int16')
            self.wave.new_buffer([0], i) 

    def on_quit(self, data=None):
        '''Clean up, close journal on quit'''
        log.debug('Killing Bobot-Server...')
        os.system(bobot_cmd_off)
        self.audiograb.on_activity_quit()

    def _notify_active_cb(self, widget, pspec):
        ''' Callback to handle starting/pausing capture when active/idle '''
        if self._first:
            log.debug('_notify_active_cb: start grabbing')
            self.audiograb.start_grabbing()
            self._first = False
        elif not self.props.active:
            log.debug('_notify_active_cb: pause grabbing')
            self.audiograb.pause_grabbing()
        elif self.props.active:
            log.debug('_notify_active_cb: resume grabbing')
            self.audiograb.resume_grabbing()

        self._active = self.props.active
        self.wave.set_active(self._active)

    def read_metadata(self):
        ''' Any saved instruments? '''
        for data in self.metadata.keys():
            if data[0] == PREFIX:  # instrument
                log.debug('found an instrument: %s' % (data[1:]))
                instrument = data[1:]
                log.debug(self.metadata[data])
                INSTRUMENT_DICT[instrument] = []
                for note in self.metadata[data].split(' '):
                    INSTRUMENT_DICT[instrument].append(float(note))

    def write_file(self, file_path):
        ''' Write data to journal, if there is any data to write '''
        # Check to see if there are any new instruments to save
        if hasattr(self, 'new_instrument_toolbar'):
            for i, instrument in enumerate(
                self.new_instrument_toolbar.new_instruments):
                log.debug('saving %s' % (instrument))
                notes = ''
                for i, note in enumerate(INSTRUMENT_DICT[instrument]):
                    notes += '%0.3f' % note
                    if i < len(INSTRUMENT_DICT[instrument]) - 1:
                        notes += ' '
                self.metadata['%s%s' % (PREFIX, instrument)] = notes

        # FIXME: Don't use ""s around data
        if hasattr(self, 'data_logger') and \
                self.new_recording and \
                len(self.data_logger.data_buffer) > 0:
            # Append new data to Journal entry
            fd = open(file_path, 'ab')
            writer = csv.writer(fd)
            # Also output to a separate file as a workaround to Ticket 2127
            # (the assumption being that this file will be opened by the user)
            tmp_data_file = os.path.join(os.environ['SUGAR_ACTIVITY_ROOT'],
                                 'instance', 'sensor_data' + '.csv')
            log.debug('saving sensor data to %s' % (tmp_data_file))
            if self._dsobject is None:  # first time, so create
                fd2 = open(tmp_data_file, 'wb')
            else:  # we've been here before, so append
                fd2 = open(tmp_data_file, 'ab')
            writer2 = csv.writer(fd2)
            # Pop data off start of buffer until it is empty
            for i in range(len(self.data_logger.data_buffer)):
                datum = self.data_logger.data_buffer.pop(0)
                writer.writerow([datum])
                writer2.writerow([datum])
            fd.close()
            fd2.close()

            # Set the proper mimetype
            self.metadata['mime_type'] = 'text/csv'

            if os.path.exists(tmp_data_file):
                if self._dsobject is None:
                    self._dsobject = datastore.create()
                    self._dsobject.metadata['title'] = _('Measure Log')
                    self._dsobject.metadata['icon-color'] = self.icon_colors
                    self._dsobject.metadata['mime_type'] = 'text/csv'
                self._dsobject.set_file_path(tmp_data_file)
                datastore.write(self._dsobject)
                # remove(tmp_data_file)

    def read_file(self, file_path):
        ''' Read csv data from journal on start '''
        reader = csv.reader(open(file_path, "rb"))
        # Count the number of sessions.
        for row in reader:
            if len(row) > 0:
                if row[0].find(_('Session')) != -1:
                    # log.debug('found a previously recorded session')
                    self.session_id += 1
                elif row[0].find('abiword') != -1:
                    # File has been opened by Write cannot be read by Measure
                    # See Ticket 2127
                    log.error('File was opened by Write: Measure cannot read')
                    self.data_logger.data_buffer = []
                    return
                self.data_logger.data_buffer.append(row[0])
        if self.session_id == 0:
            # log.debug('setting data_logger buffer to []')
            self.data_logger.data_buffer = []

    def _pause_play_cb(self, button=None):
        ''' Callback for Pause Button '''
        if self.audiograb.get_freeze_the_display():
            self.audiograb.set_freeze_the_display(False)
            self._pause.set_icon('media-playback-start')
            self._pause.set_tooltip(_('Unfreeze the display'))
            self._pause.show()
        else:
            self.audiograb.set_freeze_the_display(True)
            self._pause.set_icon('media-playback-pause')
            self._pause.set_tooltip(_('Freeze the display'))
            self._pause.show()
        return False

    def _capture_cb(self, button=None):
        ''' Callback for screen capture '''
        if self.CONTEXT == 'butia':
            self.butia_toolbar.take_screenshot()
        else:
            self.audiograb.take_screenshot()

    def timefreq_control(self, button=None):
        ''' Callback for Freq. Button '''
        # Turn off logging when switching modes
        if self.audiograb.we_are_logging:
            self.sensor_toolbar.record_control_cb()
            #Added by Butia
            self.butia_toolbar.set_sound_context()
            #Butia end
        if self.wave.get_fft_mode():
            self.wave.set_fft_mode(False)
            self.freq.set_icon('domain-time')
            self.freq.set_tooltip(_('Time Base'))
        else:
            self.wave.set_fft_mode(True)
            self.freq.set_icon('domain-freq')
            self.freq.set_tooltip(_('Frequency Base'))
            # Turn off triggering in Frequencey Base
            self.sensor_toolbar.trigger_combo.set_active(
                self.wave.TRIGGER_NONE)
            #Added by Butia
            self.butia_toolbar.trigger_combo.set_active(
                self.wave.TRIGGER_NONE)    
            #Butia end    
            self.wave.set_trigger(self.wave.TRIGGER_NONE)
            # Turn off invert in Frequencey Base
            for i in range(self.audiograb.channels):
                if self.wave.get_invert_state(channel=i):
                    self.side_toolbars[i].invert_control_cb()
        self.sensor_toolbar.update_string_for_textbox()
        #Added by Butia
        self.butia_toolbar.update_string_for_textbox()
        #Butia end
        return False

    def get_icon_colors_from_sugar(self):
        ''' Returns the icon colors from the Sugar profile '''
        if self._using_gconf:
            client = gconf.client_get_default()
            return client.get_string('/desktop/sugar/user/color')
        else:
            return profile.get_color().to_string()

    def get_nick_from_sugar(self):
        ''' Returns nick from Sugar '''
        if self._using_gconf:
            client = gconf.client_get_default()
            return client.get_string('/desktop/sugar/user/nick')
        else:
            return profile.get_nick_name()

gtk.gdk.threads_init()
