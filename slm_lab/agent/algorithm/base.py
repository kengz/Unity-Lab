from abc import ABC, abstractmethod, abstractproperty
from slm_lab.lib import util
import numpy as np


class Algorithm(ABC):
    '''
    Abstract class ancestor to all Algorithms,
    specifies the necessary design blueprint for agent to work in Lab.
    Mostly, implement just the abstract methods and properties.
    '''

    def __init__(self, agent):
        self.agent = agent

    @abstractmethod
    def post_body_init(self):
        '''Initializes the part of algorithm needing a body to exist first.'''
        raise NotImplementedError

    def body_act_discrete(self, body, state):
        '''Implement atomic discrete action, or throw NotImplementedError. E.g. fetch action from net given body info.'''
        raise NotImplementedError
        return action

    def body_act_continuous(self, body, state):
        '''Implement atomic continuous action, or throw NotImplementedError. E.g. fetch action from net given body info.'''
        raise NotImplementedError
        return action

    def body_act(self, body, state):
        '''Standard atomic body_act method. Atomic body logic should be implemented in submethods.'''
        if body.is_discrete:
            return self.body_act_discrete(body, state)
        else:
            return self.body_act_continuous(body, state)

    def act(self, state_a):
        '''Interface-level agent act method for all its bodies. Resolves state to state; get action and compose into action.'''
        action_a = self.agent.data_spaces['action'].init_data_s(a=self.agent.a)
        for (e, b), body in util.ndenumerate_nonan(self.agent.body_a):
            state = state_a[(e, b)]
            action_a[(e, b)] = self.body_act(body, state)
        return action_a

    @abstractmethod
    def train(self):
        '''Implement algorithm train, or throw NotImplementedError'''
        raise NotImplementedError

    @abstractmethod
    def update(self):
        '''Implement algorithm update, or throw NotImplementedError'''
        raise NotImplementedError
