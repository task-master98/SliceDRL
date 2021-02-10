import numpy as np

class Stats:
    def __init__(self, base_stations, clients, area):
        
        self.base_stations = base_stations
        self.clients = clients
        self.area = area
        #self.graph = graph

        # Stats
        self.total_connected_users_ratio = [0]
        self.total_used_bw = [0]
        self.avg_slice_load_ratio = [0]
        self.avg_slice_client_count = [0]
        self.coverage_ratio = [0]
        self.connect_attempt = [0]
        self.block_count = [0]
        self.handover_count = [0]
        self.user_in_each_slice = [0]
    
    def get_stats(self):
        return (
            self.total_connected_users_ratio,
            self.total_used_bw,
            self.avg_slice_load_ratio,
            self.avg_slice_client_count,
            self.coverage_ratio,
            self.block_count,
            self.handover_count,
            self.user_in_each_slice
        )

    def collect(self):
        
        self.connect_attempt.append(0)
        self.block_count.append(0)
        self.handover_count.append(0)
        while True:
            self.block_count[-1] /= self.connect_attempt[-1] if self.connect_attempt[-1] != 0 else 1
            self.handover_count[-1] /= self.connect_attempt[-1] if self.connect_attempt[-1] != 0 else 1

            self.total_connected_users_ratio.append(self.get_total_connected_users_ratio())
            self.total_used_bw.append(self.get_total_used_bw())
            self.avg_slice_load_ratio.append(self.get_avg_slice_load_ratio())
            self.avg_slice_client_count.append(self.get_avg_slice_client_count())
            self.coverage_ratio.append(self.get_coverage_ratio())
            self.user_in_each_slice.append(self.used_bw_each_slice())

            self.connect_attempt.append(0)
            self.block_count.append(0)
            self.handover_count.append(0)
            

    def get_total_connected_users_ratio(self):
        t, cc = 0, 0
        for c in self.clients:
            if self.is_client_in_coverage(c):
                t += c.connected
                cc += 1
        # for bs in self.base_stations:
        #     for sl in bs.slices:
        #         t += sl.connected_users
        return t/cc if cc != 0 else 0

    def get_total_used_bw(self):
        t = 0
        for bs in self.base_stations:
            for sl in bs.slices:
                t += sl.capacity.capacity - sl.capacity.level
        return t

    def get_avg_slice_load_ratio(self):
        t, c = 0, 0
        for bs in self.base_stations:
            for sl in bs.slices:
                c += sl.capacity.capacity
                t += sl.capacity.capacity - sl.capacity.level
                #c += 1
                #t += (sl.capacity.capacity - sl.capacity.level) / sl.capacity.capacity
        return t/c if c !=0 else 0

    def get_avg_slice_client_count(self):
        t, c = 0, 0
        for bs in self.base_stations:
            for sl in bs.slices:
                c += 1
                t += sl.connected_users
        return t/c if c !=0 else 0
    
    def get_coverage_ratio(self):
        t, cc = 0, 0
        for c in self.clients:
            if self.is_client_in_coverage(c):
                cc += 1
                if c.base_station is not None and c.base_station.coverage.is_in_coverage(c.x, c.y):
                    t += 1
        return t/cc if cc !=0 else 0

    def incr_connect_attempt(self, client):
        if self.is_client_in_coverage(client):
            self.connect_attempt[-1] += 1

    def incr_block_count(self, client):
        if self.is_client_in_coverage(client):
            self.block_count[-1] += 1

    def incr_handover_count(self, client):
        if self.is_client_in_coverage(client):
            self.handover_count[-1] += 1

    def is_client_in_coverage(self, client):
        xs, ys = self.area
        return True if xs[0] <= client.x <= xs[1] and ys[0] <= client.y <= ys[1] else False
    
    def get_users_in_each_slice(self):
        slice_hash_table = {}
        for bs in self.base_stations:
            for itr, slice in enumerate(bs.slices):
                slice_hash_table[slice.name] = slice.connected_users
        return slice_hash_table
        
    def used_bw_each_slice(self):
        slice_hash_table = {}
        for bs in self.base_stations:
            for slice in bs.slices:
                slice_hash_table[slice.name] = slice.capacity.capacity - slice.capacity.level
        return slice_hash_table