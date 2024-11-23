#!/usr/bin/env python3

import yaml
import networkx as nx
import matplotlib.pyplot as plt
from netmiko import ConnectHandler
from collections import defaultdict
import logging
import sys

class NetworkDiscovery:
    def __init__(self, config_file='config.yaml'):
        self.config = self.load_config(config_file)
        self.graph = nx.Graph()
        self.setup_logging()

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def load_config(self, config_file):
        try:
            with open(config_file, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading config file: {e}")
            sys.exit(1)

    def connect_to_device(self, device):
        device_params = {
            'device_type': device['type'],
            'ip': device['ip'],
            'username': device['username'],
            'password': device['password'],
            'secret': device.get('enable_secret', ''),
        }
        try:
            return ConnectHandler(**device_params)
        except Exception as e:
            self.logger.error(f"Failed to connect to {device['hostname']}: {e}")
            return None

    def get_lldp_neighbors(self, connection, device_hostname):
        try:
            if 'cisco' in connection.device_type:
                output = connection.send_command('show lldp neighbors detail')
                # Parse LLDP output and add to graph
                # This is a simplified example - actual parsing would be more complex
                self.graph.add_node(device_hostname)
                # Add parsing logic here
        except Exception as e:
            self.logger.error(f"Error getting LLDP neighbors from {device_hostname}: {e}")

    def get_ospf_neighbors(self, connection, device_hostname):
        try:
            if 'cisco' in connection.device_type:
                output = connection.send_command('show ip ospf neighbor')
                # Parse OSPF output and add to graph
                # Add parsing logic here
        except Exception as e:
            self.logger.error(f"Error getting OSPF neighbors from {device_hostname}: {e}")

    def get_bgp_neighbors(self, connection, device_hostname):
        try:
            if 'cisco' in connection.device_type:
                output = connection.send_command('show ip bgp neighbors')
                # Parse BGP output and add to graph
                # Add parsing logic here
        except Exception as e:
            self.logger.error(f"Error getting BGP neighbors from {device_hostname}: {e}")

    def discover_topology(self):
        for device in self.config['devices']:
            connection = self.connect_to_device(device)
            if connection:
                self.logger.info(f"Connected to {device['hostname']}")
                
                if 'lldp' in self.config['discovery']['protocols']:
                    self.get_lldp_neighbors(connection, device['hostname'])
                
                if 'ospf' in self.config['discovery']['protocols']:
                    self.get_ospf_neighbors(connection, device['hostname'])
                
                if 'bgp' in self.config['discovery']['protocols']:
                    self.get_bgp_neighbors(connection, device['hostname'])
                
                connection.disconnect()

    def visualize_topology(self):
        plt.figure(figsize=(12, 8))
        vis_config = self.config['visualization']
        
        pos = getattr(nx, f"{vis_config['layout']}_layout")(self.graph)
        
        nx.draw(self.graph, pos,
                with_labels=True,
                node_color=vis_config['node_color'],
                node_size=vis_config['node_size'],
                edge_color=vis_config['edge_color'],
                font_size=vis_config['font_size'])
        
        plt.savefig(f"network_topology.{vis_config['output_format']}")
        plt.close()

def main():
    topology = NetworkDiscovery()
    topology.discover_topology()
    topology.visualize_topology()

if __name__ == "__main__":
    main()
