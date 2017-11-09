import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.autograd import Variable
import torch.nn.functional as F
from slm_lab.agent.net.feedforward import MLPNet
from slm_lab.agent.net.convnet import ConvNet
import pytest


@pytest.fixture
def test_df():
    data = pd.DataFrame({
        'integer': [1, 2, 3],
        'square': [1, 4, 9],
        'letter': ['a', 'b', 'c'],
    })
    assert isinstance(data, pd.DataFrame)
    return data


@pytest.fixture
def test_dict():
    data = {
        'a': 1,
        'b': 2,
        'c': 3,
    }
    assert isinstance(data, dict)
    return data


@pytest.fixture
def test_list():
    data = [1, 2, 3]
    assert isinstance(data, list)
    return data


@pytest.fixture
def test_str():
    data = 'lorem ipsum dolor'
    assert isinstance(data, str)
    return data


@pytest.fixture
def test_multiline_str():
    data = '''
        lorem ipsum dolor
        sit amet

        consectetur adipiscing elit
        '''
    assert isinstance(data, str)
    return data


@pytest.fixture(scope="class", params=[
    (MLPNet(10, [5, 3], 2),
     Variable(torch.ones((2, 10))),
     Variable(torch.zeros((2, 2))),
     None,
     2),
    (MLPNet(20, [10, 50, 5], 2),
     Variable(torch.ones((2, 20))),
     Variable(torch.zeros((2, 2))),
     None,
     2),
    (MLPNet(10, [], 5),
     Variable(torch.ones((2, 10))),
     Variable(torch.zeros((2, 5))),
     None,
     2),
    (ConvNet((3, 32, 32),
             [],
             [],
             10,
             optim.Adam,
             F.smooth_l1_loss,
             False,
             False),
        Variable(torch.ones((2, 3, 32, 32))),
     Variable(torch.zeros(2, 10)),
     None,
     2),
    (ConvNet((3, 32, 32),
             [[3, 16, (5, 5), 2, 0, 1],
              [16, 32, (5, 5), 2, 0, 1]],
             [100],
             10,
             optim.Adam,
             F.smooth_l1_loss,
             False,
             False),
        Variable(torch.ones((2, 3, 32, 32))),
     Variable(torch.zeros(2, 10)),
     None,
     2),
    (ConvNet((3, 32, 32),
             [[3, 16, (5, 5), 2, 0, 1],
                 [16, 32, (5, 5), 2, 0, 1]],
             [100, 50],
             10,
             optim.Adam,
             F.smooth_l1_loss,
             False,
             True),
        Variable(torch.ones((2, 3, 32, 32))),
     Variable(torch.zeros(2, 10)),
     None,
     2),
    (ConvNet((3, 32, 32),
             [[3, 16, (5, 5), 2, 0, 1],
              [16, 32, (5, 5), 1, 0, 1],
              [32, 64, (5, 5), 1, 0, 2]],
             [100],
             10,
             optim.Adam,
             F.smooth_l1_loss,
             True,
             False),
        Variable(torch.ones((2, 3, 32, 32))),
     Variable(torch.zeros(2, 10)),
     None,
     2),
    (ConvNet((3, 32, 32),
             [[3, 16, (5, 5), 2, 0, 1],
              [16, 32, (5, 5), 1, 0, 1],
              [32, 64, (5, 5), 1, 0, 2]],
             [100],
             10,
             optim.Adam,
             F.smooth_l1_loss,
             True,
             True),
     Variable(torch.ones((2, 3, 32, 32))),
     Variable(torch.zeros(2, 10)),
     None,
     2),
    (ConvNet((3, 32, 32),
             [[3, 16, (7, 7), 1, 0, 1],
              [16, 32, (5, 5), 1, 0, 1],
              [32, 64, (3, 3), 1, 0, 1]],
             [100, 50],
             10,
             optim.Adam,
             F.smooth_l1_loss,
             False,
             False),
     Variable(torch.ones((2, 3, 32, 32))),
     Variable(torch.zeros(2, 10)),
     None,
     2),
    (ConvNet((3, 32, 32),
             [[3, 16, (7, 7), 1, 0, 1],
              [16, 32, (5, 5), 1, 0, 1],
              [32, 64, (3, 3), 1, 0, 1]],
             [100, 50],
             10,
             optim.Adam,
             F.smooth_l1_loss,
             False,
             True),
     Variable(torch.ones((2, 3, 32, 32))),
     Variable(torch.zeros(2, 10)),
     None,
     2),
])
def test_nets(request):
    return request.param


@pytest.fixture(scope="class", params=[(None, None)])
def test_data_gen(request):
    return request.param
