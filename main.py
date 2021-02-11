import numpy as np
import gym
from Network import Network

BS_PARAMS = [{'capacity_bandwidth': 20000000000, 'coverage': 500,
                'ratios': {'emBB': 0.5, 'mMTC': 0.4, 'URLLC': 0.1},
                'x': 500, 'y': 500}
                ]

SLICE_PARAMS = {'emBB': {
                'delay_tolerance': 10,
                'qos_class': 5,
                'bandwidth_guaranteed': 0,
                'bandwidth_max': 100000000,
                'client_weight': 0.45,
                'threshold': 0,
                'usage_pattern': {'distribution': 'randint', 'params': (4000000, 800000000)}
                },
                'mMTC': {
                'delay_tolerance': 10,
                'qos_class': 2,
                'bandwidth_guaranteed': 1000000,
                'bandwidth_max': 100000000,
                'client_weight': 0.3,
                'threshold': 0,
                'usage_pattern': {'distribution': 'randint', 'params': (800000, 8000000)}
                },
                'URLLC': {
                'delay_tolerance': 10,
                'qos_class': 1,
                'bandwidth_guaranteed': 5000000,
                'bandwidth_max': 100000000,
                'client_weight': 0.25,
                'threshold': 0,
                'usage_pattern': {'distribution': 'randint', 'params': (800, 8000000)}
                }}

CLIENT_PARAMS = {'location':{'x': {'distribution': 'randint', 'params': (0, 1000)}, 'y': {'distribution': 'randint', 'params': (0, 1000)}}
                , 'usage_frequency': {'distribution': 'randint', 'params': (0, 100000), 'divide_scale': 1000000}}
NUM_CLIENTS = 1000

def log_all_info(file_name: str, *state_action):
    f = open(file_name, "a")
    msg = "State: {}, Action: {}, Reward: {}, Done: {}".format((*state_action))
    f.write(msg)
    f.close()


if __name__ == "__main__":
    nw = Network(bs_params=BS_PARAMS, slice_params=SLICE_PARAMS, client_params=CLIENT_PARAMS)
    nw.reset()
    file_name = "Output.txt"
    for episode in range(100):
        state, action, reward, done, info = nw.step(nw.action_space.sample())
        log_all_info(file_name, state, action, reward, done)
        
               
