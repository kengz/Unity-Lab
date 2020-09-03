from slm_lab.agent import net
from slm_lab.agent.algorithm import policy_util
from slm_lab.agent.algorithm.base import Algorithm
from slm_lab.agent.net import net_util
from slm_lab.lib import logger, math_util, util
from slm_lab.lib.decorator import lab_api
import numpy as np
import pydash as ps
import torch

logger = logger.get_logger(__name__)


class SARSA(Algorithm):
    '''
    Implementation of SARSA.

    Algorithm:
    Repeat:
        1. Collect some examples by acting in the environment and store them in an on policy replay memory (either batch or episodic)
        2. For each example calculate the target (bootstrapped estimate of the discounted value of the state and action taken), y, using a neural network to approximate the Q function. s_t' is the next state following the action actually taken, a_t. a_t' is the action actually taken in the next state s_t'.
                y_t = r_t + gamma * Q(s_t', a_t')
        4. For each example calculate the current estimate of the discounted value of the state and action taken
                x_t = Q(s_t, a_t)
        5. Calculate L(x, y) where L is a regression loss (eg. mse)
        6. Calculate the gradient of L with respect to all the parameters in the network and update the network parameters using the gradient

    e.g. algorithm_spec
    "algorithm": {
        "name": "SARSA",
        "action_pdtype": "default",
        "action_policy": "boltzmann",
        "explore_var_spec": {
            "name": "linear_decay",
            "start_val": 1.0,
            "end_val": 0.1,
            "start_step": 10,
            "end_step": 1000,
        },
        "gamma": 0.99,
        "training_frequency": 10,
    }
    '''

    @lab_api
    def init_algorithm_params(self):
        '''Initialize other algorithm parameters.'''
        # set default
        util.set_attr(self, dict(
            action_pdtype='default',
            action_policy='default',
            normalize_inputs=False,
            explore_var_spec=None,
        ))
        util.set_attr(self, self.algorithm_spec, [
            'action_pdtype',
            'action_policy',
            'normalize_inputs',
            # explore_var is epsilon, tau or etc. depending on the action policy
            # these control the trade off between exploration and exploitaton
            'explore_var_spec',
            'gamma',  # the discount factor
            'training_frequency',  # how often to train for batch training (once each training_frequency time steps)
        ])
        self.to_train = 0
        self.action_policy = getattr(policy_util, self.action_policy)
        self.explore_var_scheduler = policy_util.VarScheduler(self.internal_clock, self.explore_var_spec)
        self.body.explore_var = self.explore_var_scheduler.start_val

    @lab_api
    def init_nets(self, global_nets=None):
        '''Initialize the neural network used to learn the Q function from the spec
        '''
        if 'Recurrent' in self.net_spec['type']:
            self.net_spec.update(seq_len=self.net_spec['seq_len'])
        in_dim = self.body.observation_dim
        out_dim = net_util.get_out_dim(self.body)
        NetClass = getattr(net, self.net_spec['type'])
        self.net = NetClass(self.net_spec, in_dim, out_dim, self.internal_clock,
                            name=f"agent_{self.agent.agent_idx}_algo_{self.algo_idx}_net")
        self.net_names = ['net']
        # init net optimizer and its lr scheduler
        self.optim = net_util.get_optim(self.net, self.net.optim_spec)
        self.lr_scheduler = net_util.get_lr_scheduler(self.optim, self.net.lr_scheduler_spec)
        net_util.set_global_nets(self, global_nets)
        self.post_init_nets()

    @lab_api
    def proba_distrib_params(self, x, net=None):
        '''
        To get the pdparam for action policy sampling, do a forward pass of the appropriate net, and pick the correct outputs.
        The pdparam will be the logits for discrete prob. dist., or the mean and std for continuous prob. dist.
        '''

        if self.normalize_inputs:
            # print("x", x.min(), x.max())
            assert x.min() >= 0.0
            assert x.max() <= 1.0
            x = (x - 0.5) / 0.5
            # print("x normalized", x.min(), x.max())
            assert x.min() >= -1.0
            assert x.max() <= 1.0

        net = self.net if net is None else net
        pdparam = net(x)
        for i, q_action_i in enumerate(pdparam.mean(dim=0).tolist()):
            self.to_log[f'q_act_{i}'] = q_action_i

        return pdparam

    @lab_api
    def act(self, state):
        '''Note, SARSA is discrete-only'''
        self.net.eval()
        with torch.no_grad():
            body = self.body
            action, action_pd = self.action_policy(state, self, body)
        self.net.train()
        self.to_log["entropy_act"] = action_pd.entropy().mean().item()
        return action.cpu().squeeze().numpy(), action_pd  # squeeze to handle scalar

    @lab_api
    def sample(self, batch_idxs=None, reset=False):
        '''Samples a batch from memory'''
        batch = self.memory.sample(batch_idxs, reset)
        # this is safe for next_action at done since the calculated act_next_q_preds will be multiplied by (1 - batch['dones'])
        batch['next_actions'] = np.zeros_like(batch['actions'])
        batch['next_actions'][:-1] = batch['actions'][1:]
        batch = util.to_torch_batch(batch, self.net.device, self.memory.is_episodic)
        return batch

    def calc_q_loss(self, batch):
        '''Compute the Q value loss using predicted and target Q values from the appropriate networks'''
        states = batch['states']
        next_states = batch['next_states']

        if self.normalize_inputs:
            # print("x", x.min(), x.max())
            assert states.min() >= 0.0
            assert states.max() <= 1.0
            states = (states - 0.5) / 0.5
            # print("x normalized", x.min(), x.max())
            assert states.min() >= -1.0
            assert states.max() <= 1.0

            assert next_states.min() >= 0.0
            assert next_states.max() <= 1.0
            next_states = (next_states - 0.5) / 0.5
            assert next_states.min() >= -1.0
            assert next_states.max() <= 1.0

        if self.body.env.is_venv:
            states = math_util.venv_unpack(states)
            next_states = math_util.venv_unpack(next_states)
        q_preds = self.net(states)
        with torch.no_grad():
            next_q_preds = self.net(next_states)
            # TODO change this : we would prefer the q value per state
            for i, q_action_i in enumerate(next_q_preds.mean(dim=0).tolist()):
                self.to_log[f'q_train_{i}'] = q_action_i
            action_pd = policy_util.init_action_pd(self.ActionPD, next_q_preds)
            self.to_log["entropy_train"] = action_pd.entropy().mean().item()
        if self.body.env.is_venv:
            q_preds = math_util.venv_pack(q_preds, self.body.env.num_envs)
            next_q_preds = math_util.venv_pack(next_q_preds, self.body.env.num_envs)
        act_q_preds = q_preds.gather(-1, batch['actions'].long().unsqueeze(-1)).squeeze(-1)
        act_next_q_preds = next_q_preds.gather(-1, batch['next_actions'].long().unsqueeze(-1)).squeeze(-1)
        act_q_targets = batch['rewards'] + self.gamma * (1 - batch['dones']) * act_next_q_preds
        logger.debug(f'act_q_preds: {act_q_preds}\nact_q_targets: {act_q_targets}')
        q_loss = self.net.loss_fn(act_q_preds, act_q_targets)
        return q_loss

    @lab_api
    def train(self):
        '''
        Completes one training step for the agent if it is time to train.
        Otherwise this function does nothing.
        '''
        if util.in_eval_lab_modes():
            return np.nan
        clock = self.internal_clock
        if self.to_train == 1:
            batch = self.sample()
            clock.set_batch_size(len(batch))
            loss = self.calc_q_loss(batch)
            self.net.train_step(loss, self.optim, self.lr_scheduler, clock=clock, global_net=self.global_net)
            # reset
            self.to_train = 0
            logger.debug(f'Trained {self.name} at epi: {clock.epi}, frame: {clock.frame}, t: {clock.t}, total_reward so far: {self.body.env.total_reward}, loss: {loss:g}')
            self.to_log["loss"] = loss.item()
            self.to_log['lr'] = np.mean(self.lr_scheduler.get_lr())
            return loss.item()
        else:
            return np.nan

    @lab_api
    def update(self):
        '''Update the agent after training'''
        self.explore_var_scheduler.update(self, self.internal_clock)
        self.to_log['explore_var'] = self.explore_var_scheduler.val
        # print("sarsa update", self.explore_var_scheduler.val)
        return self.explore_var_scheduler.val
