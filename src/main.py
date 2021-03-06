import datetime
import logging
import time
import Astar
import randomWalks2D as rw
import readTrajectory as rt
import random as r
import threading

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.positioning.position_hl_commander import PositionHlCommander
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncLogger import SyncLogger

dron1Positions = []
dron2Positions = []

logging.basicConfig(level=logging.ERROR)

def writeFile(filename, data):
    with open(filename, 'w') as file:
        for element in data:
            text = "{}, {},\n".format(element[0], element[1])
            file.write(text)

def writeDronLogfile(filename, data):
    with open(filename, 'w') as file:
        for element in data:
            text = "{}, {}, {}, {}, {}, {}\n".format(element[0], element[1], element[2], element[3], element[4], element[5])
            file.write(text)

#--------------- Callbacks ------------------
def producerDron_callback(timestamp, data, logconf):
    global dron1Positions
    position = (timestamp, data["stateEstimate.x"], data["stateEstimate.y"], data["stateEstimate.z"], data["acc.x"], data["acc.y"])
    dron1Positions.append(position)

def consumerDron_callback(timestamp, data, logconf):
    global dron2Positions
    position = (timestamp, data["stateEstimate.x"], data["stateEstimate.y"], data["stateEstimate.z"], data["acc.x"], data["acc.y"])
    dron2Positions.append(position)

#--------------- Producer ------------------
def producer(queue, eventoProducer, eventoConsumer, dat, uridron):
    print("Producer: Iniciando")
    randomTrajectory = rw.generate2DRandomWalk(30)
    print("Producer: Trayectoria generada")

    for element in randomTrajectory:
        print("Producer: {}".format(element))
        queue.append(element)
    print("Producer: Notificando")
    eventoProducer.set()

    directoryPath = "./data/Experiment/"
    randomWalkFilename = directoryPath + dat.strftime("randomWalk_%d%b%Y_%H.%M") + ".txt"
    writeFile(randomWalkFilename, randomTrajectory)

    eventoConsumer.wait()

    with SyncCrazyflie(uridron, cf=Crazyflie(rw_cache='./cache1')) as scf1:
        log_dron1 = LogConfig(name='Stabilizer', period_in_ms=100)
        log_dron1.add_variable('stateEstimate.x', 'float')
        log_dron1.add_variable('stateEstimate.y', 'float')
        log_dron1.add_variable('stateEstimate.z', 'float')
        log_dron1.add_variable('acc.x', 'float')
        log_dron1.add_variable('acc.y', 'float')
        scf1.cf.log.add_config(log_dron1)
        log_dron1.data_received_cb.add_callback(producerDron_callback)
        log_dron1.start()

        z =  0.4
        with PositionHlCommander(scf1, default_height=0.4, controller=PositionHlCommander.CONTROLLER_PID) as pc1:
            while len(randomTrajectory) > 0:
                point = randomTrajectory.pop()
                pc1.go_to(point[0]/100, point[1]/100, z)
                time.sleep(0.1)

        log_dron1.stop()

    dronpostionsFilename = directoryPath + dat.strftime("Dron1_Vuelo_%d%b%Y_%H.%M_log") + ".txt"
    writeDronLogfile(dronpostionsFilename, dron1Positions)

    print("Producer: Finalizado")



#--------------- Consumer ------------------
def consumer(queue, eventoProducer, eventoConsumer, dat, uridron):
    print('Consumer: Iniciando')

    r.seed()
    rNum = r.randint(-200, -120)
    x_i = rNum - (rNum % 10)
    rNum = r.randint(-90, 90)
    y_i = rNum - (rNum % 10)

    rNum = r.randint(170, 200)
    x_f = rNum - (rNum % 10)
    rNum = r.randint(-40, 80)
    y_f = rNum - (rNum % 10)

    p_i = (x_i, y_i)
    p_f = (x_f, y_f)

    inputFilename = "./src/MATLAB/puntos.txt"
    obstacles = rt.readTrajectory(inputFilename)
    print("Consumer: Esperando")
    eventoProducer.wait()
    print("Consumer: Continuando")

    newQueue = queue.copy()

    for element in queue:
        x = element[0]
        y = element[1]
        points = [(x, y + 10), (x, y - 10), (x + 10, y), (x - 10, y)]
        for point in points:
            isOnlist = False
            for data in queue:
                if point in data:
                    isOnlist = True
                    break
            if isOnlist == False:
                newQueue.append(point)


    while len(newQueue) > 0:
        data = newQueue.pop()
        encontrado = False
        for element in obstacles:
            if data in element:
                print("Consumer: {} en obstacles".format(data[0]))
                encontrado = True
                element[1] = 1.0
                break
        if encontrado == False:
            new = [data, 1.0]
            obstacles.append(new)

    directoryPath = "./data/Experiment/"
    obstaclesFilename = directoryPath + dat.strftime("obstacles_%d%b%Y_%H.%M") + ".txt" 
    writeFile(obstaclesFilename, obstacles)

    pathResult = Astar.Aasterisk(p_i, p_f, obstacles)

    pathResultFilename = directoryPath + dat.strftime("result_%d%b%Y_%H.%M") + ".txt"
    writeFile(pathResultFilename, pathResult)

    eventoConsumer.set()

    with SyncCrazyflie(uridron, cf=Crazyflie(rw_cache='./cache2')) as scf2:
        log_dron2 = LogConfig(name='Stabilizer', period_in_ms=100)
        log_dron2.add_variable('stateEstimate.x', 'float')
        log_dron2.add_variable('stateEstimate.y', 'float')
        log_dron2.add_variable('stateEstimate.z', 'float')
        log_dron2.add_variable('acc.x', 'float')
        log_dron2.add_variable('acc.y', 'float')
        scf2.cf.log.add_config(log_dron2)
        log_dron2.data_received_cb.add_callback(consumerDron_callback)
        log_dron2.start()

        z = 0.4
        with PositionHlCommander(scf2, default_height=0.4, controller=PositionHlCommander.CONTROLLER_PID) as pc2:
            for element in pathResult:
                pc2.go_to(element[0]/100, element[1]/100, z)
                time.sleep(0.2)

        log_dron2.stop()
    
    dronpostionsFilename = directoryPath + dat.strftime("Dron2_Vuelo_%d%b%Y_%H.%M_log") + ".txt"
    writeDronLogfile(dronpostionsFilename, dron2Positions)

    print("Consumer: Finalizando")


#--------------- Main ------------------
if __name__ == '__main__':
    cflib.crtp.init_drivers(enable_debug_driver=False)

    uriDron1  = 'radio://0/80/2M/E7E7E7E7E7'
    uriDron2  = 'radio://0/80/2M/E7E7E7E7E8'
    pipeline = []
    dat = datetime.datetime.now()
    eventoProducer = threading.Event()
    eventoConsumer = threading.Event()

    producerThread = threading.Thread(target=producer, args=(pipeline, eventoProducer, eventoConsumer, dat, uriDron1))
    consumerThread = threading.Thread(target=consumer, args=(pipeline, eventoProducer, eventoConsumer, dat, uriDron2))
    
    producerThread.start()
    consumerThread.start()

    print('Main: Finalizado')