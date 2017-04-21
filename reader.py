import butiaAPI
import time
 
robot = butiaAPI.robot()
 
robot.abrirSensor()
 
i = 0
#inicializacion de variables
 
while i<10:
        #creamos la variable i para que se ejecutara 199 veces y no por siempre
        i += 1
        #linea = robot.getEscalaGris()
        valorgris = getGrayScale()
	print valorgris
        #guardamos el valor del sensor en linea y lo imprime en pantalla
 
        if valorgris > "200":
                #Si es mayor que 200 imprimo esto
                print "Si es mayor que 200 imprimo esto"
        else:
                #Si no imprimo esto
                print "NO es mayor que 200 "
        time.sleep(0.2)
 
