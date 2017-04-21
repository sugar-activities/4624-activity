#!/bin/bash
# Script para setear los drivers


HOME=bobot-server/bobot/drivers/hotplug


drivers = (gpio.lua grey.lua light.lua port.lua temp.lua tilt.lua vibra.lua)

function drivers_originales {
	for driver in $drivers; do
		cp $driver.orig $driver
	
}

function drivers_random {
	 for driver in $drivers; do
                cp $driver.ran $driver
 	done;

}

echo 'orden: ' $1 

if [ "$1" == "debug" ]; then
	drivers_random
else 
	drivers_originales
fi


