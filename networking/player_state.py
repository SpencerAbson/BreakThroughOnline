#!/usr/bin/env python3

from dataclasses import dataclass

class BreakthroughPlayer():
    def __init__(self, name):
        self._score = 0
        self._name = name
        self._locksSolved = 0

    @property
    def score(self):
        return score

    @property
    def locksSolved(self):
        return self._lockSolved

    @score.setter
    def score(self, value):
        assert(value > 0)
        self._score = value

    @locksSolved.setter
    def lockSolved(self, value):
        assert(value > 0)
        self._lockSovled = value

    def getPlayerStats(self):
        stats = f'------- {self._name} --------\n'
        stats += 'Score:{self._score}\n'
        stats += 'Locks solved:{self._locksSolved}\n'
        return stats

@dataclass
class PlayerState:
    score: int = 0
    locksSolved: int = 0
