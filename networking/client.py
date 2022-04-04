#!/usr/bin/env python3
import socket
from networking.standards import *
import time
import pickle
import threading
from networking.player_state import PlayerState


class BreakthroughClient:
    def __init__(self, client_name, host_ip):
        self._clientName = client_name
        self._clientActive = False
        self._port = 9999
        self._clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # TCP socket
        self._host_ip = host_ip
        self._hostAddress = (self._host_ip, self._port)
        self._playerState = {'score': 0, 'locksSolved': 0}
        self._objFromServer = {}
        self.connected = threading.Event()
        self.gameStarted = threading.Event()
        self.recvdObjFromServer = threading.Event()

    @property
    def port(self) -> int:
        return self._port

    @property
    def clientActive(self) -> bool:
        return self._clientActive

    @clientActive.setter
    def clientActive(self, value):
        self._clientActive = value
        if not value: self._clientSocket.close()

    @property
    def playerScore(self) -> int:
        return self._playerState['score']

    @property
    def playerLocksSolved(self) -> int:
        return self._playerState['locksSolved']

    @playerScore.setter
    def playerScore(self, value):
        if value < 0 or value > 100: return
        self._playerState['score'] = value

    @playerLocksSolved.setter
    def playerLocksSolved(self, value):
        if value < 0 or value > 100: return
        self._playerState['locksSolved'] = value

    def disconnectHost(self):
        self._clientSocket.close()

    def switchHost(self, new_ip, new_port):
        self._host_ip = new_ip
        self._port = new_port
        self._hostAddress = (new_ip, new_port)

    def connect(self):
        print("client attempting connection")
        self._clientActive = True
        self._clientSocket.connect((self._hostAddress))
        self._clientSocket.send(bytes((f'{len(self._clientName):<{HEADER_SIZE}}' + self._clientName), "utf-8"))
        time.sleep(0.2)
        self.connected.set()
        time.sleep(0.2) # avoid mixing packets
        self.__handleServerStreamData()

    def __checkHeaderDecodeBit(self, flag) -> bool:
        pass

    def __handleServerStreamData(self):
        new_message  = True
        decode_bytes = True
        message_data = ''
        message_bytes = b''
        while self._clientActive:
            if self._clientSocket:
                try:
                    packet = self._clientSocket.recv(PACKET_SIZE)
                    if len(packet) > 0:
                        if new_message:
                            payload_size = int(packet[:PAYLOAD_WIDTH])
                            new_message = False
                            if str(SERVER_SEND_PICKLE) in str(packet[PAYLOAD_WIDTH:HEADER_SIZE]):
                                decode_bytes = False
                                self.recvdObjFromServer.clear()

                        if decode_bytes:
                            message_data += packet.decode(ENCODING_STD)
                            if len(message_data) - HEADER_SIZE >= payload_size:
                                self.__processServerMessage(message_data[HEADER_SIZE:])
                                message_data = ''
                                new_message = True
                        else:
                            message_bytes += packet
                            if len(message_bytes) + 1 - HEADER_SIZE >= payload_size:
                                self._objFromServer = pickle.loads(message_bytes[HEADER_SIZE + 1:])
                                self.recvdObjFromServer.set()
                                message_bytes = b''
                                new_message = True
                                decode_bytes = True  # by default

                except ConnectionAbortedError or ConnectionResetError:
                    self.connected.reset()
                    return

    def __processServerMessage(self, message: str):
        if len(message) == 1: # it is a set command
            request_code = int(message)
            if request_code == SERVER_PS_REQUEST:
                self.sendPlayerState()
            elif request_code == SERVER_START_GAME:
                print("starting game!")
                self.gameStarted.set()
            if request_code == CLIENT_WON_GAME:  # end the game in some way?
                self._clientActive = False
        else:
            pass
            print("\nFROM SERVER: \n" + message)

    def sendPlayerState(self):
        if self._clientActive and self._clientSocket:
            msg = pickle.dumps(self._playerState)
            msg = bytes(f'{len(msg):<{HEADER_SIZE}}', ENCODING_STD) + msg
            self._clientSocket.send(msg)

    def messageHost(self, message):
        self._clientSocket.send(bytes((f'{len(message):<{HEADER_SIZE}}' + message), "utf-8"))

    def reportEvent(self, event: int):
        self._clientSocket.send(bytes((f'{len(str(event)):<{HEADER_SIZE}}' + str(bit)), "utf-8"))

    def requestData(self, bit: int) -> str:
        self._clientSocket.send(bytes((f'{len(str(bit)):<{HEADER_SIZE}}' + str(bit)), "utf-8"))
