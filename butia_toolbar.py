import random
import gtk
import gobject
import os
import sys
import time


from gettext import gettext as _

from config import ICONS_DIR, XO1, XO15, XO175, XO30,\
                   MAX_LOG_ENTRIES

from sugar.graphics.toolbutton import ToolButton
from sugar.graphics.combobox import ComboBox
from sugar.graphics.toolcombobox import ToolComboBox
from sugar.graphics.radiotoolbutton import RadioToolButton
from threading import Timer
import logging
import logging.config
import butiaAPI

from ringbuffer import RingBuffer1d

log = logging.getLogger('measure-activity')
log.setLevel(logging.DEBUG)

file_name = 'measure.log'
handler = logging.handlers.RotatingFileHandler(file_name, backupCount=0)
#log.addHandler(handler)

class ButiaToolbar(gtk.Toolbar):
    ''' The toolbar for specifiying the sensor: temp, distance, 
    light or gray '''

    def __init__(self, activity, channels):
        
        #Se utiliza para contralar que no se ejecute dos veces
        self._butia_context_id = None        
        
        gtk.Toolbar.__init__(self)
        self.activity = activity
        self._channels = channels

        self.mode = 'butia'    
        
        # Set up Sensores Button
        self.time = RadioToolButton(group=None)
        
        # Mantiene la lista de botones (de sensores)
        # agregados a la ButiaToolbar
        self.lista_sensores_button = []
        
        self.we_are_logging = False
        self._log_this_sample = False
        self._logging_timer = None
        self._logging_counter = 0
        self._image_counter = 0
        self._logging_interval = 0
        self._channels_logged = []
        self._busy = False
        self._take_screenshot = True
			
		# BUTIA Se detectan sensores 
        log.debug('se agrega el boton refrescar')
        self.refrescar_button = RadioToolButton(group=None)			
        self.refrescar_button.set_named_icon('recargar')		
        self.refrescar_button.connect('clicked', self.update_buttons)	
        self.insert(self.refrescar_button, -1)        
        
        separator = gtk.SeparatorToolItem()
        separator.props.draw = True
        self.insert(separator, -1)          
        
        self.detect_sensors()
        self.load_buttons()
        
        separator = gtk.SeparatorToolItem()
        separator.props.draw = True
        self.insert(separator, -1)                      
        
        self._log_interval_combo = ComboBox()
        self.interval = [_('1/10 second'), _('1 second'), _('30 seconds'),
                         _('5 minutes'), _('30 minutes')]

        if hasattr(self._log_interval_combo, 'set_tooltip_text'):
            self._log_interval_combo.set_tooltip_text(_('Sampling interval'))

        self._interval_changed_id = self._log_interval_combo.connect('changed',
                                         self.log_interval_cb)

        for i, s in enumerate(self.interval):
            self._log_interval_combo.append_item(i, s, None)
            if s == _('1 second'):
                self._log_interval_combo.set_active(i)

        self._log_interval_tool = ToolComboBox(self._log_interval_combo)
        self.insert(self._log_interval_tool, -1)
        self.logging_interval_status = '1 second'

        
        # Set up Logging/Stop Logging Button
        self._record = ToolButton('media-record')
        self.insert(self._record, -1)
        self._record.set_tooltip(_('Start Recording'))
        self._record.connect('clicked', self.record_control_cb)

        self.show_all()
    

	# BUTIA Busca modulos conectados y pregunta si son sensores
    def detect_sensors(self):
        self.robot = butiaAPI.robot() 
        log.debug('listando modulos detectados:')
        modules = self.robot.get_modules_list()
        self.sensores = []
        log.debug(modules)
        for i in range(len(modules)):
			if self.is_sensor(modules[i]) :
				log.debug(modules[i] +' es sensor!')
				self.sensores.append(modules[i])
			else :
				log.debug(modules[i] +' no es sensor!')
        self.sensores.sort()
        log.debug('sensores: ')
        log.debug(self.sensores)
    
    # BUTIA determina si el modulo que le pasan es sensor! ! 
    def is_sensor(self, module):
		is_sensor = 0
		descripcion = 'A'
		#log.debug('DESCRIBIENDO: '+ module)		
		descripcion = self.robot.doCommand('DESCRIBE '+ module )
		if descripcion == -1:
			return 0
		#log.debug(descripcion)		
		is_sensor = descripcion.count('returns={[1]') and module != 'display' and module != 'butia' 
		return is_sensor
	
	#BUTIA Cargo los botones para cada sensor detectado
    def load_buttons(self):	
        self.lista_sensores_button = []
        for i in range(len(self.sensores)):
			self.sensor = self.sensores[i]
			log.debug('agregando boton para : '+ self.sensor)
			#radio_tool_button = 0
			radio_tool_button = RadioToolButton(group=self.time)			
			icono = self.sensor.strip('0123456789:')
			radio_tool_button.set_named_icon(icono)			
			radio_tool_button.set_tooltip(_(self.sensor))
			if self.sensor.count('temp'):
				#determino el numero de sensor y lo paso por parametro.					
				#log.debug('el sensor  '+ self.sensor + 'es el numero '+ self.get_sensor_number(self.sensor) )
				radio_tool_button.connect('clicked',self.click_temp_button,self.get_sensor_number(self.sensor))				
			elif self.sensor.count('dist'):
				#log.debug('el sensor  '+ self.sensor + 'es el numero '+ self.get_sensor_number(self.sensor) )
				radio_tool_button.connect('clicked',self.click_dist_button,self.get_sensor_number(self.sensor))				
			elif self.sensor.count('grey'):
				#log.debug('el sensor  '+ self.sensor + 'es el numero '+ self.get_sensor_number(self.sensor) )
				radio_tool_button.connect('clicked',self.click_grises_button,self.get_sensor_number(self.sensor))
			elif self.sensor.count('light'):
				#log.debug('el sensor  '+ self.sensor + 'es el numero '+ self.get_sensor_number(self.sensor) )
				radio_tool_button.connect('clicked',self.click_luz_button,self.get_sensor_number(self.sensor))
			self.insert(radio_tool_button, 2)    
			self.lista_sensores_button.append(radio_tool_button)                    							

    def update_buttons(self, button=None):   
		for s in self.lista_sensores_button:
			self.remove(s)
    
		self.detect_sensors()
		self.load_buttons()    
        
		self.show_all()
    
    def get_sensor_number(self, sensor):
		number = 0		
		sensor_trunked = sensor.strip('0123456789')
		number = sensor.strip(sensor_trunked)
		log.debug('sensor number :' +  sensor.strip(sensor))
		return number
		
    # BUTIA metodos para leen sensores     
    def read_temp_from_bobot_server(self,num=0 ):
		#log.debug('**********Sensando temperature' + str(num)+ '***********')
		value = 0
		value = self.robot.callModule('temp:'+ str(num),'getValue')
		#log.debug('temperature : ' + value)					
		return value
		
    def read_dist_from_bobot_server(self,num=0 ):
		#log.debug('**********Sensando distance'+ str(num) + '******************')
		value = 0
		#value = self.robot.getDistance(num)
		value = self.robot.callModule('distanc:'+ str(num),'getValue')
		#log.debug('distance = ' + str(value))	
		return value
	
    def read_grises_from_bobot_server(self,num=0):
		#log.debug('**********Sensando grises'+ str(num) + '******************')
		value = '0'
		value = self.robot.callModule('grey:'+ str(num),'getValue')
		#log.debug('grey = ' + str(value))	
		return value

    def read_luz_from_bobot_server(self,num=0):
		#log.debug('**********Sensando luz '+ str(num) + '******************')
		value = '0'
		value = self.robot.callModule('ligth:'+ str(num),'getValue')
		#log.debug('grey = ' + str(value))	
		return value
    
    def read_sensor_from_bobot_server(self,num):
		log.debug('**********Read Sensor ***********')
		return 0

    def click_button(self,button=None):
		log.debug('********** clicka botton ***********')
		self.set_butia_context()								
		return False
				
    def click_temp_button (self, button=None,num='0'):
		log.debug('********** clickea botton temp ***********')
		self.mode = 'temperatura'
		self.read_sensor_from_bobot_server = self.read_temp_from_bobot_server
		self.set_butia_context(num)								
		return False

    def click_dist_button (self, button=None,num='0'):
		log.debug('********** clickea botton dist ***********')
		self.mode = 'distancia'
		self.read_sensor_from_bobot_server = self.read_dist_from_bobot_server
		self.activity.limpiar_canales()
		self.set_butia_context(num)				
		return False
		
    def click_grises_button (self, button=None,num='0'):
		log.debug('********** clickea botton grises ***********')
		self.mode = 'grises'
		self.read_sensor_from_bobot_server = self.read_grises_from_bobot_server
		self.activity.limpiar_canales()
		self.set_butia_context(num)								
		return False

    def click_luz_button (self, button=None,num='0'):
		log.debug('********** clickea botton luz ***********')
		self.mode = 'luz'
		self.read_sensor_from_bobot_server = self.read_luz_from_bobot_server
		self.activity.limpiar_canales()
		self.set_butia_context(num)								
		return False
       	         
    def set_butia_context(self,num='0'):
		self.activity.audiograb.stop_grabbing()
		if self._butia_context_id:
			gobject.source_remove(self._butia_context_id)
		self._butia_context_id =\
            gobject.timeout_add(50,self.butia_context_on,num)
		
    def butia_context_on(self,num='0'):        	
        bufChannelTmp = []

        #Si esta el boton de pause activada no se agregar el nuevo valor
        if self.activity.audiograb.get_freeze_the_display():
            bufChannelTmp.append(self.read_sensor_from_bobot_server(num))
            for i in range(self.activity.audiograb.channels):      
                self.activity.wave.new_buffer(bufChannelTmp,i)            
                if self.we_are_logging:
                    self.logging_to_file(bufChannelTmp,i)
            
        if self.activity.CONTEXT == 'butia':
            return True
        else:
            return False
            
    def logging_to_file(self, data_buffer, channel):
        if self.we_are_logging:
            if self._logging_counter == MAX_LOG_ENTRIES:
                self._logging_counter = 0
                self.we_are_logging = False
                self.activity.data_logger.stop_session()
            else:
                if self._logging_interval == 0:
                    self._emit_for_logging(data_buffer, channel=channel)
                    self._log_this_sample = False
                    self.we_are_logging = False
                    self.activity.data_logger.stop_session()
                elif self._log_this_sample:
                    # Sample channels in order
                    if self.activity.audiograb._channels_logged.index(False) == channel:
                        self.activity.audiograb._channels_logged[channel] = True
                        self._emit_for_logging(data_buffer, channel=channel)
                        # Have we logged every channel?
                        if self.activity.audiograb._channels_logged.count(True) == self.activity.audiograb.channels:
                            self._log_this_sample = False
                            for i in range(self.activity.audiograb.channels):
                                self.activity.audiograb._channels_logged[i] = False
                            self._logging_counter += 1        

    def _emit_for_logging(self, data_buffer, channel=0):
        '''Sends the data for logging'''
        if not self._busy:
            self._busy = True
            if self._take_screenshot:
                if self.activity.data_logger.take_screenshot(
                    self._image_counter):
                    self._image_counter += 1
                else:
                    log.debug('failed to take screenshot %d' % (
                            self._logging_counter))
                self._busy = False
                return
                
            value_string = data_buffer[0]

            if self.activity.audiograb.channels > 1:
                self.activity.data_logger.write_value(
                    value_string, channel=channel,
                    sample=self._logging_counter)
            else:
                self.activity.data_logger.write_value(
                    value_string, sample=self._logging_counter)
            self._busy = False
        else:
            log.debug('skipping sample %d.%d' % (
                    self._logging_counter, channel))

    def _sample_now(self):
        ''' Log the current sample now. This method is called from the
        _logging_timer object when the interval expires. '''
        self._log_this_sample = True
        self._make_timer()

    def _make_timer(self):
        ''' Create the next timer that will trigger data logging. '''
        self._logging_timer = Timer(self._logging_interval, self._sample_now)
        self._logging_timer.start()

    def record_control_cb(self, button=None):
        ''' Depending upon the selected interval, does either a logging
        session, or just logs the current buffer. '''
        if self.we_are_logging:
            self.set_logging_params(start_stop=False)
            self._record.set_icon('media-record')
            self._record.show()
            self._record.set_tooltip(_('Start Recording'))
        else:
            Xscale = 0.0
            Yscale = 0.0
            interval = self.interval_convert()
            username = self.activity.nick
            if self.activity.wave.get_fft_mode():
                self.activity.data_logger.start_new_session(
                    username, Xscale, Yscale, _(self.logging_interval_status),
                    channels=self._channels, mode='frequency')
            else:
                self.activity.data_logger.start_new_session(
                    username, Xscale, Yscale, _(self.logging_interval_status),
                    channels=self._channels, mode=self.mode)
            self.set_logging_params(
                start_stop=True, interval=interval, screenshot=False)
            self._record.set_icon('record-stop')
            self._record.show()
            self._record.set_tooltip(_('Stop Recording'))
            self.activity.new_recording = True

    def set_logging_params(self, start_stop=False, interval=0,
                           screenshot=True):
        ''' Configures for logging of data: starts or stops a session;
        sets the logging interval; and flags if screenshot is taken. '''
        self.we_are_logging = start_stop
        self._logging_interval = interval
        if not start_stop:
            if self._logging_timer:
                self._logging_timer.cancel()
                self._logging_timer = None
                self._log_this_sample = False
                self._logging_counter = 0
        elif interval != 0:
            self._make_timer()
        self._take_screenshot = screenshot
        self._busy = False

    def interval_convert(self):
        ''' Converts interval string to an integer that denotes the
        number of times the audiograb buffer must be called before a
        value is written.  When set to 0, the whole of current buffer
        will be written. '''
        interval_dictionary = {'1/10 second': 0.1, '1 second': 1,
                               '30 seconds': 30,
                               '5 minutes': 300, '30 minutes': 1800}
        try:
            return interval_dictionary[self.logging_interval_status]
        except ValueError:
            logging.error('logging interval status = %s' %\
                              (str(self.logging_interval_status)))
            return 0

    def log_interval_cb(self, combobox):
        ''' Callback from the Logging Interval Combo box: sets status '''
        if self._log_interval_combo.get_active() != -1:
            intervals = ['1/10 second', '1 second', '30 seconds',
                         '5 minutes', '30 minutes']
            self.logging_interval_status = \
                              intervals[self._log_interval_combo.get_active()]

    def take_screenshot(self):
        ''' Capture the current screen to the Journal '''
        log.debug('taking a screenshot %d' % (self._logging_counter))
        self.set_logging_params(start_stop=True, interval=0, screenshot=True)
