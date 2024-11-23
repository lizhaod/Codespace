# Network Topology Visualizer

This Python-based tool automatically discovers and visualizes network topology using various network protocols:
- LLDP (Link Layer Discovery Protocol)
- OSPF (Open Shortest Path First)
- BGP (Border Gateway Protocol)
- IS-IS (Intermediate System to Intermediate System)

## Features
- Automatic network discovery using multiple protocols
- Network topology visualization using NetworkX and Graphviz
- Support for multiple vendor devices
- Customizable graph layouts and styling
- Export topology in various formats (PNG, SVG, DOT)

## Installation

1. Clone this repository
2. Install required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Update the `config.yaml` with your network devices information
2. Run the main script:
```bash
python network_topology.py
```

## Configuration

Edit `config.yaml` to specify:
- Network devices and their credentials
- Protocols to use for discovery
- Visualization preferences
