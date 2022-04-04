#!/usr/bin/env python3
import socket
import pickle
import threading
import time
import datetime
from dataclasses import dataclass
from networking.player_state import PlayerState
from networking.standards import *


@dataclass
class BtHostClient:
    name: str
    sock: socket.socket
    address: (str, int)
    decode: bool


class BreakthroughHost:
    def __init__(self, player_name):
        self._playerName = player_name
        self._serverListening = False
        self._clientCount = 0
        self._activeClients = {}
        self._port = 9999  # hope no one is using this!
        self._serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # create TCP socket
        self._host_name = socket.gethostname()
        self._host_ip = socket.gethostbyname(self._host_name)
        self._socketAddress = (self._host_ip, self._port)
        self._wantsPackets = True
        self._playerState = {'score': 0, 'locksSolved': 0}
        self._hostStartingData = {}
        self.__clientDataObjects = []
        self.__cdoMutex = threading.Lock()

    @property
    def port(self) -> int:
        return self._port

    @property
    def clientCount(self) -> int:
        return self._clientCount

    @property
    def serverListening(self) -> bool:
        return self._serverListening

    @serverListening.setter
    def serverListening(self, value):
        if not value: self._serverSocket.close()
        self._serverListening = value

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
        if value < 0 or value > 20: return
        self._playerState['locksSolved'] = value

    def uploadStartingData(self, hand, deck, locks):
        assert(hand.GetName() == "HAND" and deck.GetName() == "DECK")
        self._hostStartingData["HAND"] = [card.GetDescription() for card in hand.GetCards()]
        self._hostStartingData["DECK"] = [card.GetDescription() for card in deck.GetCards()]
        self._hostStartingData["LOCKS"] = []
        for lock in locks:
            self._hostStartingData["LOCKS"].append([c.GetCondition() for c in lock.GetChallenges()])

    def listenForClients(self):
        print(f'Listening for clients on: {self._socketAddress}')
        self._serverListening = True
        self._serverSocket.bind(self._socketAddress)  # Binding
        self._serverSocket.listen(0)
        while self._serverListening:
            client_socket, address = self._serverSocket.accept()
            self.__handleClientConnection(client_socket, address)

    def __handleClientConnection(self, client_sock, address):
        if client_sock:
            name = client_sock.recv(PACKET_SIZE).decode(ENCODING_STD)[HEADER_SIZE:]
            self._activeClients[name] = BtHostClient(name, client_sock, address, True)
            #self.__submitMsgToAll(f'New player: {name} has connected!')
            # create a thread to receive data from current client on
            stream_thread = threading.Thread(target=self.__handleClientStreamData, args=(name,), daemon=True)
            stream_thread.start()
            self._clientCount += 1

    def __handleClientStreamData(self, client_name): # each new client thread
        client_obj = self._activeClients[client_name]
        new_message = True
        message_data_utf = ''
        message_pure_bytes = b''
        decode_bytes = self._activeClients[client_name].decode

        while self._wantsPackets:
            if client_obj.sock:
                try:
                    packet = client_obj.sock.recv(PACKET_SIZE)
                    if len(packet) > 0:
                        if new_message:
                            payload_size = int(packet[:HEADER_SIZE])
                            new_message = False
                            decode_bytes = self._activeClients[client_name].decode  # do we want bytes for new msg?

                        if decode_bytes:
                            message_data_utf += packet.decode(ENCODING_STD)
                            if len(message_data_utf) - HEADER_SIZE >= payload_size:
                                self.__processClientMessage(client_name, message_data_utf[HEADER_SIZE:])
                                message_data_utf = ''
                                new_message = True
                        else:
                            message_pure_bytes += packet
                            if len(message_pure_bytes) - HEADER_SIZE >= payload_size:
                                self.__addClientObjectReceived(client_name, pickle.loads(message_pure_bytes[HEADER_SIZE:]))
                                self._activeClients[client_name].decode = True  # we have received object, back to norm
                                new_message = True
                                message_bytes = b''

                except ConnectionResetError or ConnectionAbortedError or KeyError:  # disconnected, left, or kicked
                    break

        self.__handlePlayerDisconnect(client_obj.name)

    def __handlePlayerDisconnect(self, name, reason="Disconnection"):
        if name in self._activeClients:
            del self._activeClients[name]
            self._clientCount -= 1
            self.__submitMsgToAll(f'PLAYER: {name} has been disconnected ({reason})')

    def __submitMsgToAll(self, message: str, pickled=False):
        print(message)  # all includes us
        for name in self._activeClients.keys():
            self.__submitMsgToClient(name, message, pickled=pickled)

    def __submitMsgToClient(self, name, message: str, pickled=False):
        if self._activeClients[name].sock:
            if not pickled:
                self._activeClients[name].sock.send(bytes((f'{len(message):<{HEADER_SIZE}}' + message), ENCODING_STD))
            else:
                msg = f'{len(message):<{HEADER_SIZE}}'
                flag = msg[:PAYLOAD_WIDTH] + str(SERVER_SEND_PICKLE) + msg[HEADER_SIZE + len(str(SERVER_SEND_PICKLE)):]  # add pf header
                self._activeClients[name].sock.send(bytes(flag, ENCODING_STD) + message)


    def handleClientEvent(self, client_name, event_flag: int):
        if event_flag == CLIENT_LOST_GAME:
            if client_name != self._playerName:
                self.kickPlayer(client_name, "Lost game")   # seems a little harsh
            self.__submitMsgToAll(f'{client_name} is now out of the game.')

        elif event_flag == CLIENT_WON_GAME:
            self.__submitMsgToAll(f'{client_name} has won the game!')
        else:
            self.__submitMsgToAll(str(event_flag))

    def __processClientMessage(self, client_name, message):
        if len(str(message)) == 1:
            request_flag = int(message)
            if request_flag == CLIENT_LOBBY_REQUEST:
                self.__submitMsgToClient(client_name, self.getLobbyDisplay())
            elif request_flag == CLIENT_SDATA_REQUEST:  # starting data request
                self.__submitStartDataToClient(client_name)
            elif request_flag == CLIENT_STATS_REQUEST:
                threading.Thread(target=self.__processStatsRequest, args=(client_name,), daemon=True).start()
            else:
                self.handleClientEvent(client_name, request_flag)
        else:
            print(f'SERVER: message from client {self._activeClients[name].address} ({name}): {message}')

    @staticmethod
    def formatPlayerState(name, obj) -> str:
        msg = f'{name} -- :\n'
        msg += f'Current Score:{obj["score"]}\n'
        msg += f'Locks Solved:{obj["locksSolved"]}\n'
        return msg

    def __collectStatsResponse(self) -> str:
        for name in self._activeClients:
            self._activeClients[name].decode = False # start receving bytes only (for pickle)
            self.__submitMsgToClient(name, str(SERVER_PS_REQUEST))

        stats_msg = ''
        while True:
            if len(self.__clientDataObjects) == self._clientCount:
                for obj in self.__clientDataObjects:
                    stats_msg += BreakthroughHost.formatPlayerState(obj[0], obj[1])
                stats_msg += BreakthroughHost.formatPlayerState(self._playerName, self._playerState)
                break

        self.__clientDataObjects.clear()
        return stats_msg
    
    def __processStatsRequest(self, client):
        stats_msg = self.__collectStatsResponse()
        self.__submitMsgToClient(client, stats_msg)

    def isssueStatsRequest(self):
        print(self.__collectStatsResponse())

    def __addClientObjectReceived(self, client, obj):
        self.__cdoMutex.acquire()
        self.__clientDataObjects.append([client, obj])
        self.__cdoMutex.release()

    def __submitStartDataToClient(self, client):  # at the start of the game all players should start with same cards
        msg = pickle.dumps(self._hostStartingData)
        self.__submitMsgToClient(client, msg, pickled=True)

    def getLobbyDisplay(self) -> str:
        msg = "------------ Players in lobby --------------\n"
        for key in self._activeClients.keys():
            msg += "USERNAME: " + self._activeClients[key].name + "\n"
            msg += "ADDRESS: " + str(self._activeClients[key].address) + "\n"
        msg += "--------------------------------------------\n"
        return msg

    def displayClientsForAll(self):
        msg = getLobbyDisplay()
        self.__submitMsgToAll(msg)

    def kickPlayer(self, username, reason):
        if username in self._activeClients:
            self.__handlePlayerDisconnect(username, reason=reason)
        else: print(f'Error: username ({username}) was not recognised as an active player.')

    def messageAllClients(self, message: str):
        self.__submitMsgToAll(message)

    def closeSocket(self):
        self._serverSocket.close()
