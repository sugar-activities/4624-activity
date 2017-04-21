#!/bin/bash
# Script para encender y apagar el bobot server.

#./lua bobot-server.lua
bobot_folder=butiaXO 
lua_cmd='./lua bobot-server.lua'
#bobot_mode=chotox &

function bobot_on() {
	
	$lua_cmd
	return 0
}

function bobot_off() {
			
	PID=`pidof lua`
	echo $PID
	kill -9 $PID
	return 0

}

echo 'orden: ' $1 

cd $bobot_folder

if [ "$1" == "on" ]; then
	bobot_on
else 
	bobot_off
fi


