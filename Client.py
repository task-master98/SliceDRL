import operator
import random

from utils import distance


class Client:
    def __init__(self, id, x, y,
                 usage_freq,
                 subscribed_slice_index, stat_collector,
                 base_station=None):
        self.id = id
        self.x = x
        self.y = y
        
        self.usage_freq = usage_freq
        self.base_station = base_station
        self.stat_collector = stat_collector
        self.subscribed_slice_index = subscribed_slice_index
        self.usage_remaining = 0
        self.last_usage = 0
        self.closest_base_stations = []
        self.connected = False

        # Stats
        self.total_connected_time = 0
        self.total_unconnected_time = 0
        self.total_request_count = 0
        self.total_consume_time = 0
        self.total_usage = 0

        
        # print(self.usage_freq)

    def iter(self):
        '''
        There are three steps in a cycle:
            1- .00: Lock
            2- .25: Stats
            3- .50: Release
        '''

        # .00: Lock
        if self.base_station is not None:
            if self.usage_remaining > 0:
                if self.connected:
                    self.start_consume()
                else:
                    self.connect()
            else:
                if self.connected:
                    self.disconnect()
                else:
                    self.generate_usage_and_connect()
                  
        # .50: Release
        # Base station check skipped as it's already implied by self.connected
        if self.connected and self.last_usage > 0:
            self.release_consume()
            if self.usage_remaining <= 0:
                self.disconnect()
       
  
    def get_slice(self):
        if self.base_station is None:
            return None
        return self.base_station.slices[self.subscribed_slice_index]
    
    def generate_usage_and_connect(self):
        if self.usage_freq < random.random() and self.get_slice() is not None:
            # Generate a new usage
            self.usage_remaining = self.get_slice().usage_pattern.generate()
            self.total_request_count += 1
            self.connect()
            # print(f'[{int(self.env.now)}] Client_{self.id} [{self.x}, {self.y}] requests {self.usage_remaining} usage.')

    def connect(self):
        s = self.get_slice()
        if self.connected:
            return
        # increment connect attempt
        self.stat_collector.incr_connect_attempt(self)
        if s.is_avaliable():
            s.connected_users += 1
            self.connected = True
            # print(f'[{int(self.env.now)}] Client_{self.id} [{self.x}, {self.y}] connected to slice={self.get_slice()} @ {self.base_station}')
            return True
        else:
            self.assign_closest_base_station(exclude=[self.base_station.id])
            if self.base_station is not None and self.get_slice().is_avaliable():
                # handover
                self.stat_collector.incr_handover_count(self)
            elif self.base_station is not None:
                # block
                self.stat_collector.incr_block_count(self)
            else:
                pass # uncovered
            # print(f'[{int(self.env.now)}] Client_{self.id} [{self.x}, {self.y}] connection refused to slice={self.get_slice()} @ {self.base_station}')
            return False

    def disconnect(self):
        if self.connected == False:
            pass
            # print(f'[{int(self.env.now)}] Client_{self.id} [{self.x}, {self.y}] is already disconnected from slice={self.get_slice()} @ {self.base_station}')
        else:
            slice = self.get_slice()
            slice.connected_users -= 1
            self.connected = False
            # print(f'[{int(self.env.now)}] Client_{self.id} [{self.x}, {self.y}] disconnected from slice={self.get_slice()} @ {self.base_station}')
        return not self.connected

    def start_consume(self):
        s = self.get_slice()
        amount = min(s.get_consumable_share(), self.usage_remaining)
        # Allocate resource and consume ongoing usage with given bandwidth
        s.capacity.get(amount)
        # print(f'[{int(self.env.now)}] Client_{self.id} [{self.x}, {self.y}] gets {amount} usage.')
        self.last_usage = amount

    def release_consume(self):
        s = self.get_slice()
        # Put the resource back
        if self.last_usage > 0: # note: s.capacity.put cannot take 0
            s.capacity.put(self.last_usage)
            # print(f'[{int(self.env.now)}] Client_{self.id} [{self.x}, {self.y}] puts back {self.last_usage} usage.')
            self.total_consume_time += 1
            self.total_usage += self.last_usage
            self.usage_remaining -= self.last_usage
            self.last_usage = 0

   

    def __str__(self):
        return f'Client_{self.id} [{self.x:<5}, {self.y:>5}] connected to: slice={self.get_slice()} @ {self.base_station}\t with mobility pattern of {self.mobility_pattern}'
