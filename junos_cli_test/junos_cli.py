#!/usr/bin/env python3

import csv
import concurrent.futures
from jnpr.junos import Device
from jnpr.junos.exception import ConnectError
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from rich import print as rprint
import sys
import logging
from getpass import getpass
import socket

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

console = Console()

def load_devices():
    """Load device information from CSV file."""
    try:
        devices = []
        with open('devices.csv', 'r') as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                if row['host']:  # Only add if host is not empty
                    devices.append(row)
        return devices
    except Exception as e:
        logger.error(f"Error loading devices configuration: {str(e)}")
        sys.exit(1)

def get_credentials():
    """Prompt for username and password."""
    console.print("\n[bold blue]Enter credentials for device access:[/bold blue]")
    username = Prompt.ask("Username")
    password = getpass("Password: ")
    
    # Ask for port number with default value
    port = Prompt.ask("Port number (press Enter for default 830)", default="830")
    return username, password, int(port)

def execute_command(device_info, command, credentials):
    """Execute command on a single device and return the result."""
    username, password, port = credentials
    try:
        # First, check if the port is open
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((device_info['host'], port))
        sock.close()
        
        if result != 0:
            return {
                'device': device_info['name'],
                'status': 'error',
                'output': f"Port {port} is not accessible. Please ensure NETCONF is enabled on the device:\n" +
                         "1. Check if NETCONF is enabled: 'show configuration system services netconf'\n" +
                         "2. To enable NETCONF, use: 'set system services netconf ssh'\n" +
                         f"3. Verify port {port} is not blocked by firewall"
            }

        # Try to connect using PyEZ
        dev = Device(host=device_info['host'],
                    user=username,
                    password=password,
                    port=port,
                    gather_facts=False)  # Skip fact gathering for faster connection
        
        dev.open()
        try:
            # Execute command based on type
            if command.startswith('show'):
                result = dev.cli(command, warning=False)
            else:
                # For configuration commands
                with dev.config(mode='exclusive') as cu:
                    cu.load(command, format='set')
                    cu.commit()
                result = "Configuration committed successfully"
            
            dev.close()
            return {
                'device': device_info['name'],
                'status': 'success',
                'output': result
            }
        except Exception as e:
            dev.close()
            raise e
            
    except ConnectError as e:
        error_msg = str(e)
        if "connection refused" in error_msg.lower():
            error_msg += "\nPossible causes:\n" + \
                        "1. NETCONF is not enabled on the device\n" + \
                        "2. Wrong port number (default is 830)\n" + \
                        "3. Firewall blocking the connection"
        return {
            'device': device_info['name'],
            'status': 'error',
            'output': f"Connection error: {error_msg}"
        }
    except Exception as e:
        return {
            'device': device_info['name'],
            'status': 'error',
            'output': f"Error: {str(e)}"
        }

def display_results(results):
    """Display results in a formatted table."""
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Device")
    table.add_column("Status")
    table.add_column("Output")

    for result in results:
        status_color = "green" if result['status'] == 'success' else "red"
        table.add_row(
            result['device'],
            f"[{status_color}]{result['status']}[/{status_color}]",
            result['output']
        )

    console.print(table)

def main():
    """Main function to run the CLI tool."""
    devices = load_devices()
    
    console.print("[bold blue]Junos Multi-Device CLI Tool[/bold blue]")
    credentials = get_credentials()
    
    console.print("\nType 'exit' to quit the program\n")

    while True:
        try:
            command = Prompt.ask("[yellow]Enter command[/yellow]")
            
            if command.lower() == 'exit':
                break

            with concurrent.futures.ThreadPoolExecutor(max_workers=len(devices)) as executor:
                future_to_device = {
                    executor.submit(execute_command, device, command, credentials): device
                    for device in devices
                }
                
                results = []
                for future in concurrent.futures.as_completed(future_to_device):
                    result = future.result()
                    results.append(result)

            display_results(results)

        except KeyboardInterrupt:
            console.print("\n[red]Program interrupted by user[/red]")
            break
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")

if __name__ == "__main__":
    main()
