'''
The agent module
Contains graduated components from experiments for building agents and be taught, tested, evaluated on curriculum.
To be designed by human and evolution module, based on the experiment aim (trait) and fitness metrics.
Main SLM components (refer to SLM doc for more):
- primary survival objective
- control policies
- sensors (input) for embodiment
- motors (output) for embodiment
- neural architecture
- memory (with time)
- prioritization mechanism and "emotions"
- strange loop must be created
- social aspect
- high level properties of thinking, e.g. creativity, planning.

Agent components:
- algorithm (with net, policy)
- memory
'''
from slm_lab.agent import algorithm
from slm_lab.experiment.monitor import info_space
from slm_lab.lib import util
import numpy as np
import pydash as _


class Agent:
    '''
    Class for all Agents.
    Standardizes the Agent design to work in Lab.
    Access Envs properties by: Agents - AgentSpace - AEBSpace - EnvSpace - Envs
    '''
    # TODO ok need architecture spec for each agent: disjoint or joint, time or space multiplicity

    def __init__(self, spec, agent_space, a=0):
        self.spec = spec
        self.name = self.spec['name']
        self.agent_space = agent_space
        self.index = a
        self.body_a = None
        self.flat_nonan_body_a = None  # flatten_nonan version of bodies

        AlgoClass = getattr(algorithm, _.get(self.spec, 'algorithm.name'))
        self.algorithm = AlgoClass(self)

    def post_body_init(self):
        '''Run init for components that need bodies to exist first, e.g. memory or architecture.'''
        self.flat_nonan_body_a = util.flatten_nonan(self.body_a)
        self.algorithm.post_body_init()

    def reset(self, state_a):
        '''Do agent reset per episode, such as memory pointer'''
        for (e, b), body in np.ndenumerate(self.body_a):
            body.memory.reset_last_state(state_a[(e, b)])

    def act(self, state_a):
        '''Standard act method from algorithm.'''
        return self.algorithm.act(state_a)

    def update(self, action_a, reward, state_a, done):
        '''
        Update per timestep after env transitions, e.g. memory, algorithm, update agent params, train net
        '''
        # TODO spread over body space, body.memory.update
        for (e, b), body in np.ndenumerate(self.body_a):
            body.memory.update(
                action_a[(e, b)], reward[(e, b)], state_a[(e, b)], done[(e, b)])
        loss = self.algorithm.train()
        explore_var = self.algorithm.update()
        # TODO tmp return, to unify with monitor auto-fetch later
        return loss, explore_var

    def close(self):
        '''Close agent at the end of a session, e.g. save model'''
        # TODO save model
        model_for_loading_next_trial = 'not implemented'
        return model_for_loading_next_trial


class AgentSpace:
    '''
    Subspace of AEBSpace, collection of all agents, with interface to Session logic; same methods as singleton agents.
    Access EnvSpace properties by: AgentSpace - AEBSpace - EnvSpace - Envs
    '''

    def __init__(self, spec, aeb_space):
        self.spec = spec
        self.aeb_space = aeb_space
        self.aeb_shape = aeb_space.aeb_shape
        aeb_space.agent_space = self
        self.agents = [
            Agent(a_spec, self, a) for a, a_spec in enumerate(spec['agent'])]

    def post_body_init(self):
        '''Run init for components that need bodies to exist first, e.g. memory or architecture.'''
        for agent in self.agents:
            agent.post_body_init()

    def get(self, a):
        return self.agents[a]

    def reset(self, state_space):
        for a, agent in enumerate(self.agents):
            state_a = state_space.get(a=a)
            agent.reset(state_a)

    def act(self, state_space):
        action_v = []
        for a, agent in enumerate(self.agents):
            state_a = state_space.get(a=a)
            action_a = agent.act(state_a)
            action_v.append(action_a)
        action_space = self.aeb_space.add('action', action_v)
        return action_space

    def update(self, action_space, reward_space, state_space, done_space):
        for a, agent in enumerate(self.agents):
            action_a = action_space.get(a=a)
            reward = reward_space.get(a=a)
            state_a = state_space.get(a=a)
            done = done_space.get(a=a)
            loss, explore_var = agent.update(action_a, reward, state_a, done)
        # TODO tmp, single body (last); use monitor later
        return loss, explore_var

    def close(self):
        for agent in self.agents:
            agent.close()
