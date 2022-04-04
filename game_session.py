#!/usr/bin/env python3
from networking.server import *
from networking.client import *
from networking.standards import *
import threading
import abc
from networking.player_state import PlayerState
# two users to start a game together -> each game run locally and are to compete/shown others locks


# players to create/join a server and first to certain score wins
# each move, their score is updated
# host creates/loads the cards and then we can send as dictonary to all clients for them

class GameSession(metaclass=abc.ABCMeta):  # common to both the host and cient

    def __init__(self, name, sesh_type):
        self._name = name
        self._type = sesh_type

    @property
    def playerType(self): return self._type

    @abc.abstractmethod
    def displayLobby(self): pass

    @abc.abstractmethod
    def leaveSession(self): pass

    @abc.abstractmethod
    def displayStats(self): pass

    @abc.abstractmethod
    def updatePlayerState(self, score, locks_solved): pass

    @abc.abstractmethod
    def reportEvent(self, event: str): pass


class ClientSession(GameSession):

    def __init__(self, name, host_ip):
        super().__init__(name, "CLIENT")
        self._client = BreakthroughClient(name, host_ip)
        self._clientThread = threading.Thread(target=self._client.connect, daemon=True).start()

    def updatePlayerState(self, new_score, new_ls):
        self._client.playerScore = new_score
        self._client.playerLocksSolved = new_ls

    def waitForGameToStart(self):  # continually 'wait'
        self._client.connected.wait()
        self._client.requestData(CLIENT_SDATA_REQUEST)
        self._client.recvdObjFromServer.wait()

        print("obj" + str(self._client._objFromServer))
        self._client.gameStarted.wait()
        print("fuck it started!")

    def getStartingData(self) -> {}:
        #assert("HAND" in self._client._ObjFromServer.keys() and "DECK" in self._client._ObjFromServer.keys())
        return self._client._objFromServer

    def displayLobby(self):
        print("---------LOBBY-----------")
        self._client.requestData(CLIENT_LOBBY_REQUEST)

    def displayStats(self):
        print("---------CURRENT SCORES---------")
        self._client.requestData(CLIENT_STATS_REQUEST)

    def reportEvent(self, event: str):
        self._client.messageHost(event)

    def leaveSession(self):
        self._client.disconnectHost()


class HostSession(GameSession):

    def __init__(self, name, hand, deck, locks):
        super().__init__(name, "HOST")
        self._server = BreakthroughHost(name)
        self._serverThread = threading.Thread(target=self._server.listenForClients, daemon=True)
        self._serverThread.start()
        self._server.uploadStartingData(hand, deck, locks)
        self._waitForInput = True
        self._lobby()

    def updatePlayerState(self, new_score, new_ls):
        self._server.playerScore = new_score
        self._server.playerLocksSolved = new_ls

    def displayLobby(self):
        print("---------LOBBY-----------")
        print(self._server.getLobbyDisplay())

    def displayStats(self):
        print("---------CURRENT SCORES---------")
        #self._server.issueStatsRequest()
        threading.Thread(target=self._server.issueStatsRequest).start()

    def reportEvent(self, event: int):
        self._server.handleClientEvent(self._name, event)

    def leaveSession(self):
        self._server.serverListening = False
        self._server.closeSocket()

    def sendCardsToClients(self, hand, deck):
        self._server.submitCardsToClients(hand, deck)

    def kickPlayer(self, player, reason):
        self._server.kickPlayer(player, reason)

    def _lobby(self):
        lob = "\r\n------------------LOBBY-----------------------\n"
        print(lob + self._server.getLobbyDisplay())
        cmd = input("\r(r)efresh lobby, (s)tart game:>").upper()
        if cmd == "R": self._lobby()
        elif cmd == "S": self.reportEvent(SERVER_START_GAME)
