'''
This module defines the wrapper for the 
open AI gym. This will describe the basestation
which allocates bandwidth to the network slices
dynamically depending on the number of requests
at each interval
'''
from BaseStation import BaseStation
from Client import Client
from Slice import Slice
from Container import Container
from Coverage import Coverage
from Distributor import Distributor
from Stats import Stats 
from utils import kdtree



import numpy as np
import random
import os 
import math
import gym
from gym import Env
from gym import spaces, logger
from gym.utils import seeding
from queue import Queue
from collections import defaultdict


class Network(Env):
    """
    Description:
        A base station has some maximum allocated bandwidth
        which it shares among the network slices depending
        on the instantaneous slice ratios. This enable dynamic
        slicing of the network.
        
    Episode Termination:
        An episode terminates if all the user requests are accepted
        or if all the users are out of coverage of the base station
        or if the combined requests (new users + queue) exceed the 
        bandwidth restrictions of the base station

    States:
        {slice 1 allocated bandwidth ratio, slice 1 instantaneous bandwidth usage ratio, slice 1 client density,
        slice 2 allocated bandwidth ratio, slice 2 instantaneous bandwidth usage ratio, slice 2 client density,
        slice 3 allocated bandwidth ratio, slice 3 instantaneous bandwidth usage ratio, slice 3 client density}
    
    Actions:
        A={(0, 0, 0), (+0.05, -0.025, -0.025), (-0.05, +0.025,
        +0.025), (-0.025, +0.05, -0.025), (+0.025, -0.05, +0.025), (-0.025,
        -0.025, +0.05), (+0.025, +0.025, -0.05)}
    
    """
      
    slices_info = {'emBB': 0.45, 'mMTC': 0.3, 'URLLC': 0.25}
    collected, slice_weights = 0, []
    for _, item in slices_info.items():
        collected += item
        slice_weights.append(collected)
    mb_weights = []
    
      

    def __init__(self, bs_params, slice_params, client_params):
        self.n_clients = 100
        self.clients = self.clients_init(self.n_clients, client_params) 
        self.base_stations = self.base_stations_init(bs_params, slice_params)
        self.x_range = (0, 1000)
        self.y_range = (0, 1000)
        self.stats = Stats(self.base_stations, None, (self.x_range, self.y_range))
        for client in self.clients:
            client.stat_collector = self.stats
        
        
        self.action_list = [(0, 0, 0), (0.05, -0.025, -0.025), (-0.05, +0.025,
                            +0.025), (-0.025, +0.05, -0.025), (+0.025, -0.05, +0.025), (-0.025,
                            -0.025, +0.05), (+0.025, +0.025, -0.05)]
        self.action_space = spaces.Discrete(7)
        self.state = None
        high = np.ones(shape=(9, ))
        low = -high
        self.observation_space = spaces.Box(low, high, dtype=np.float32)
        self.steps_beyond_done = None
        self.seed()
        
    def seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [seed]    
    
    def reset(self):
        self.state = self.np_random.uniform(low=0, high=1, size=(9,))
        self.steps_beyond_done = None
        return np.array(self.state)
    
    def step(self, action: int):
        """
        A step is defined in the client
        class which has 4 different parts 
        for each cycle: Lock, Stats, Release and Move
        See method Client.iter()
        Each part has a duration allocated and is 
        followed by a yeild(timeout)

        In the Stats step, the get_stats() 
        method of the Stats class is called
        which provides one observation in the
        form of an array
        """
        ### Initialise the stat collector which gives state information
        selected_action = self.SelectedAction(action)
        for bs in self.base_stations:
            for itr, slice in enumerate(bs.slices):
                new_s_cap = (1 + selected_action[itr])*slice.init_capacity
                slice.init_capacity = new_s_cap
                slice.capacity = Container(init=new_s_cap, capacity=new_s_cap)

        self.initialise_stats()
        selected_clients = self.generate_user_requests()
        slice_hash_table = defaultdict(list)
        reward = self.reward(selected_clients)

        total_connected_clients, clients_in_coverage = 0, 0
        for bs in self.base_stations:
            for slice in bs.slices:
                total_connected_clients += slice.connected_users
                slice_hash_table[slice.name].append([slice.connected_users/len(selected_clients),
                                                    (slice.capacity.capacity - slice.capacity.level)/slice.bandwidth_max,
                                                    slice.capacity.capacity/slice.bandwidth_max])
        state_array = []
        for _, item in slice_hash_table.items():
            state_array.append(item)

        self.state = (np.array(state_array)).flatten()
        done = total_connected_clients == len(selected_clients)     ## TODO: done condition is too harsh! Should add used bandwidth condition

        if not done:
            reward = -10
        elif self.steps_beyond_done is None:
            self.steps_beyond_done = 0
            reward = -10
        else:
            if self.steps_beyond_done == 0:
                logger.warn(
                    "You are calling 'step()' even though this "
                    "environment has already returned done = True. You "
                    "should always call 'reset()' once you receive 'done = "
                    "True' -- any further steps are undefined behavior.")
                self.steps_beyond_done += 1
                reward = 0.0
                

        return self.state, selected_action, reward, done, {}


                
    def SelectedAction(self, action: int):
        action = self.action_list[action]
        return action



    def generate_user_requests(self):
        ## A subset of clients are selected at each step
        ## this follows a normal distribution
        n_active_clients = max(int(random.random()*self.n_clients), int(0.1*self.n_clients))
        
        random_client_ids = np.random.randint(self.n_clients, size=n_active_clients)
        all_clients = np.array(self.clients)
        selected_clients = all_clients[random_client_ids]

        for selected_client in selected_clients:
            selected_client.iter()

        return selected_clients

      
    
    def reward(self, clients: np.ndarray):
        """
        The reward function is defined in the 
        base paper: https://ieeexplore.ieee.org/abstract/document/9235006/references#references
        It is a function of the latency requirements (inverse of the delay tolerance) of each
        slice, the blocked request counts for that slice and the total request counts for that
        slice. The net reward is the sum over all the slices. The request counts can be generated
        from the Stats.get_stats() method.
        """
        reward = 0
        for client in clients:
            if client.base_station is not None:
                slice: Slice = client.base_station.slices[client.subscribed_slice_index]
                stats: Stats = client.stat_collector
                latency_requirements = 1/slice.delay_tolerance
                connection_requests = stats.connect_attempt[-1]
                blocked_requests = connection_requests - slice.connected_users
                reward_slice = -(latency_requirements)*(blocked_requests/connection_requests)
                reward += reward_slice
        return reward
            
        

    def is_done(self):
        """
        Episode termination step is provided here. This is already described 
        above.
        """
        pass

    def connections_init(self):
        """
        Initialise connections with  KDTree
        """
        # self.kdt.limit = 5
        kdtree(self.clients, self.base_stations)
    
    def initialise_stats(self):
        """
        Assigns clients to the stats method
        only after initialising the KDTree i.e.,
        only after assigning closest base stations 
        to all the clients
        """
        self.connections_init()
        self.stats.clients = self.clients

        
    @classmethod
    def base_stations_init(cls, bs_params, slice_params):
        base_stations = []
        i = 0
        usage_patterns = {}
        for name, s in slice_params.items():
            usage_patterns[name] = Distributor(name, get_dist(s['usage_pattern']['distribution']), *s['usage_pattern']['params'])
        
        for bs in bs_params:
            slices = []
            ratios = bs['ratios']
            capacity = bs['capacity_bandwidth']
            for name, s in slice_params.items():
                s_cap = capacity * ratios[name]
            
                s = Slice(name, ratios[name], 0, s['client_weight'],
                    s['delay_tolerance'],
                    s['qos_class'], s['bandwidth_guaranteed'],
                    s['bandwidth_max'], s_cap, usage_patterns[name])
                s.capacity = Container(init=s_cap, capacity=s_cap)
                slices.append(s)
            base_station = BaseStation(i, Coverage((bs['x'], bs['y']), bs['coverage']), capacity, slices)
            base_stations.append(base_station)
            i += 1
        return base_stations

            
    @classmethod
    def clients_init(cls, n_clients, client_params):
        i = 0
        clients = []
        ufp = client_params['usage_frequency']
        usage_freq_pattern = Distributor(f'ufp', get_dist(ufp['distribution']),
                                        *ufp['params'], divide_scale=ufp['divide_scale'])

        for _ in range(n_clients):
            loc_x = client_params['location']['x']
            loc_y = client_params['location']['y']
            location_x = get_dist(loc_x['distribution'])(*loc_x['params'])
            location_y = get_dist(loc_y['distribution'])(*loc_y['params'])
            
            connected_slice_index = get_random_slice_index(cls.slice_weights)
            c = Client(i, location_x, location_y, usage_freq_pattern.generate_scaled(),
                         connected_slice_index, None, None)
            clients.append(c)
            i += 1
        return clients





def get_dist(d):
    return {
        'randrange': random.randrange, # start, stop, step
        'randint': random.randint, # a, b
        'random': random.random,
        'uniform': random, # a, b
        'triangular': random.triangular, # low, high, mode
        'beta': random.betavariate, # alpha, beta
        'expo': random.expovariate, # lambda
        'gamma': random.gammavariate, # alpha, beta
        'gauss': random.gauss, # mu, sigma
        'lognorm': random.lognormvariate, # mu, sigma
        'normal': random.normalvariate, # mu, sigma
        'vonmises': random.vonmisesvariate, # mu, kappa
        'pareto': random.paretovariate, # alpha
        'weibull': random.weibullvariate # alpha, beta
    }.get(d)

def get_random_mobility_pattern(vals, mobility_patterns):
    i = 0
    r = random.random()

    while vals[i] < r:
        i += 1

    return mobility_patterns[i]


def get_random_slice_index(vals):
    i = 0
    r = random.random()

    while vals[i] < r:
        i += 1
    return i  




