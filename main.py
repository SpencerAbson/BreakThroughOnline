#!/usr/bin/env python3
from networking import server
import threading
import abc
import time
from networking.player_state import PlayerState
# two users to start a game together -> each game run locally and are to compete/shown others locks


# players to create/join a server and first to certain score wins
# each move, their score is updated


# need to abstract away from being host/client gamesession.UpdateScore() gameSession.handleMessage

if __name__ == "__main__":
    print("hola", end='', flush=True)
    #time.sleep(1)
    #print("\rhello", flush=True)
    s = server.BreakthroughHost("John")
    threading.Thread(target=s.listenForClients, daemon=True).start()
    time.sleep(30)
    s.kickPlayer("Spencer")
