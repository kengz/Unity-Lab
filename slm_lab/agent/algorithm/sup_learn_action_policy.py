from slm_lab.agent import net
from slm_lab.agent.algorithm import policy_util
from slm_lab.agent.algorithm.base import Algorithm
from slm_lab.lib import math_util, util
from slm_lab.agent.net import net_util
from slm_lab.lib.decorator import lab_api
import numpy as np
import torch

from slm_lab.lib import logger
logger = logger.get_logger(__name__)

# TODO change doc
class SupervisedLAPolicy(Algorithm):
    '''
    SpLActPolicy = Supervised learning the action policy

    e.g. algorithm_spec:
    "algorithm": {
        "name": "Reinforce",
        "action_pdtype": "default",
        "action_policy": "default",
        "explore_var_spec": null,
        "gamma": 0.99,
        "entropy_coef_spec": {
          "name": "linear_decay",
          "start_val": 0.01,
          "end_val": 0.001,
          "start_step": 100,
          "end_step": 5000,
        },
        "training_frequency": 1,
    }
    '''

    @lab_api
    def init_algorithm_params(self):
        '''Initialize other algorithm parameters'''
        # set default
        util.set_attr(self, dict(
            action_pdtype='default',
            action_policy='default',
            # center_return=False,
            # normalize_return=False,
            explore_var_spec=None,
            entropy_coef_spec=None,
            policy_loss_coef=1.0,
        ))
        util.set_attr(self, self.algorithm_spec, [
            'action_pdtype',
            'action_policy',
            # 'center_return',  # center by the mean
            # 'normalize_return', # divide by std
            'explore_var_spec',
            # 'gamma',  # the discount factor
            'entropy_coef_spec',
            'policy_loss_coef',
            'training_frequency',
        ])
        self.to_train = 0
        self.action_policy = getattr(policy_util, self.action_policy)
        self.explore_var_scheduler = policy_util.VarScheduler(self.body.env.clock, self.explore_var_spec)
        self.explore_var_scheduler.start_val
        if self.entropy_coef_spec is not None:
            self.entropy_coef_scheduler = policy_util.VarScheduler(self.body.env.clock, self.entropy_coef_spec)

    @lab_api
    def init_nets(self, global_nets=None):
        '''
        Initialize the neural network used to learn the policy function from the spec
        Below we automatically select an appropriate net for a discrete or continuous action space if the setting is of the form 'MLPNet'. Otherwise the correct type of network is assumed to be specified in the spec.
        Networks for continuous action spaces have two heads and return two values, the first is a tensor containing the mean of the action policy, the second is a tensor containing the std deviation of the action policy. The distribution is assumed to be a Gaussian (Normal) distribution.
        Networks for discrete action spaces have a single head and return the logits for a categorical probability distribution over the discrete actions
        '''
        in_dim = self.body.observation_dim
        out_dim = net_util.get_out_dim(self.body)
        NetClass = getattr(net, self.net_spec['type'])
        self.net = NetClass(self.net_spec, in_dim, out_dim, self.body.env.clock)
        self.net_names = ['net']
        # init net optimizer and its lr scheduler
        self.optim = net_util.get_optim(self.net, self.net.optim_spec)
        self.lr_scheduler = net_util.get_lr_scheduler(self.optim, self.net.lr_scheduler_spec)
        net_util.set_global_nets(self, global_nets)
        self.post_init_nets()

    @lab_api
    def calc_pdparam(self, x, net=None):
        '''The pdparam (proba distrib param) will be the logits for discrete prob. dist., or the mean and std for
        continuous prob. dist.'''
        net = self.net if net is None else net
        pdparam = net(x)
        return pdparam

    @lab_api
    def act(self, state):
        # print("state act", state)
        body = self.body
        action, action_pd = self.action_policy(state, self, body)
        # print("act", action)
        # print("prob", action_pd.probs.tolist())
        return action.cpu().squeeze().numpy(), action_pd  # squeeze to handle scalar

    @lab_api
    def sample(self):
        '''Samples a batch from memory'''
        batch = self.memory.sample()
        batch = util.to_torch_batch(batch, self.net.device, self.memory.is_episodic)
        return batch

    def calc_pdparam_batch(self, batch):
        '''Efficiently forward to get pdparam and by batch for loss computation'''
        states = batch['states']
        if self.body.env.is_venv:
            states = math_util.venv_unpack(states)
        pdparam = self.calc_pdparam(states)
        return pdparam

    def calc_ret_advs(self, batch):
        '''Calculate plain returns; which is generalized to advantage in ActorCritic'''
        rets = math_util.calc_returns(batch['rewards'], batch['dones'], self.gamma)
        if self.center_return:
            rets = math_util.center_mean(rets)
        if self.normalize_return:
            rets = math_util.normalize_var(rets)
        advs = rets
        if self.body.env.is_venv:
            advs = math_util.venv_unpack(advs)
        return advs

    def calc_supervised_learn_loss(self, batch, pdparams):
        '''Calculate the actor's policy loss'''
        action_pd = policy_util.init_action_pd(self.body.ActionPD, pdparams)
        targets = batch['actions']
        if self.body.env.is_venv:
            targets = math_util.venv_unpack(targets)
        preds = action_pd.probs
        if targets.dim() == 1:
            targets = self.one_hot_embedding(targets.long(), self.agent.body.action_space[self.agent.agent_idx].n)
        print("spl preds", preds[0:5,:])
        print("spl targets", targets[0:5,:])
        supervised_learning_loss = self.net.loss_fn(preds, targets).mean()

        if self.entropy_coef_spec:
            print("spl action_pd.entropy()",action_pd.entropy()[0:5])
            entropy = action_pd.entropy().mean()

            logger.debug(f'entropy {entropy}')
            self.to_log["entropy"] = entropy.item()
            self.to_log["entropy_coef"] = self.entropy_coef_scheduler.val
            entropy_loss = (-self.entropy_coef_scheduler.val * entropy)
            if supervised_learning_loss != 0.0:
                self.to_log["entropy_over_loss"] = entropy_loss / supervised_learning_loss
            supervised_learning_loss += entropy_loss
        logger.debug(f'supervised_learning_loss: {supervised_learning_loss:g}')
        return supervised_learning_loss

    def one_hot_embedding(self, labels, num_classes):
        """Embedding labels to one-hot form.

        Args:
          labels: (LongTensor) class labels, sized [N,].
          num_classes: (int) number of classes.

        Returns:
          (tensor) encoded labels, sized [N, #classes].
        """
        y = torch.eye(num_classes)
        return y[labels]

    @lab_api
    def train(self):
        if util.in_eval_lab_modes():
            return np.nan
        clock = self.body.env.clock
        if self.to_train == 1:
            batch = self.sample()
            clock.set_batch_size(len(batch))

            # Compute predictions
            pdparams = self.calc_pdparam_batch(batch)
            # _, pdparams = self.act(batch['states'])

            loss = self.calc_supervised_learn_loss(batch, pdparams)

            self.net.train_step(loss, self.optim, self.lr_scheduler, clock=clock, global_net=self.global_net)
            # reset
            self.to_train = 0
            logger.debug(f'Trained {self.name} at epi: {clock.epi}, frame: {clock.frame}, t: {clock.t}, total_reward so far: {self.body.env.total_reward}, loss: {loss:g}')
            self.to_log["loss"] = loss.item()
            return loss.item()
        else:
            return np.nan

    @lab_api
    def update(self):
        self.explore_var_scheduler.update(self, self.body.env.clock)
        if self.entropy_coef_spec is not None:
            self.entropy_coef_scheduler.update(self, self.body.env.clock)
        return self.explore_var_scheduler.val
