'''
The random agent algorithm
For basic dev purpose.
'''
import numpy as np
from slm_lab.agent.algorithm.base import Algorithm


class Random(Algorithm):
    '''
    Example Random agent that works in both discrete and continuous envs
    '''

    def act_discrete(self, state):
        '''Random discrete action'''
        # TODO AEB space resolver, lineup index
        # agent action could be single-body action repeated in time for all bodies (identical only), or
        # or all existing in space, on distinct network output units
        # either way needs access to AEB/A/E, get_action_dim, get_observable_dim['state']
        # also ensure algorithm act is congruent with agent.act
        action = np.random.randint(self.agent.bodies[0].env.get_action_dim())
        return action

    def act_continuous(self, state):
        '''Random continuous action'''
        # TODO AEB space resolver, lineup index
        action = np.random.randn(self.agent.bodies[0].env.get_action_dim())
        return action

    def update(self, reward, state, done):
        return
