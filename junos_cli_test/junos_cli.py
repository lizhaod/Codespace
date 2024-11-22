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
from contextlib import contextmanager
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress all ncclient-related logs
for logger_name in ['ncclient.transport.ssh', 'ncclient.transport.session', 'ncclient.operations.rpc']:
    logging.getLogger(logger_name).setLevel(logging.WARNING)

console = Console()

@contextmanager
def suppress_junos_logs():
    """Temporarily suppress Junos connection logs."""
    original_level = logging.getLogger('ncclient.transport.session').level
    logging.getLogger('ncclient.transport.session').setLevel(logging.ERROR)
    try:
        yield
    finally:
        logging.getLogger('ncclient.transport.session').setLevel(original_level)

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Junos Multi-Device CLI Tool')
    parser.add_argument('-s', '--site', 
                      help='Filter devices by site code (case-insensitive)',
                      default='')
    return parser.parse_args()

def load_devices(site_filter=''):
    """Load device information from CSV file."""
    try:
        devices = []
        with open('devices.csv', 'r') as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                # Apply site filter if specified
                if site_filter:
                    if site_filter.lower() in row['name'].lower():
                        devices.append(row)
                else:
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
    return username, password

def execute_command(device_info, command, credentials):
    """Execute command on a single device and return the result."""
    username, password = credentials
    try:
        with suppress_junos_logs():
            with Device(host=device_info['host'],
                    user=username,
                    password=password,
                    auto_add_policy=True,  # Automatically accept SSH host keys
                    port=22) as dev:
                
                # Execute command based on type
                if command.startswith('show'):
                    result = dev.cli(command, warning=False)
                else:
                    # For configuration commands
                    with dev.config(mode='exclusive') as cu:
                        cu.load(command, format='set')
                        cu.commit()
                    result = "Configuration committed successfully"
                    
                return {
                    'device': device_info['name'],
                    'status': 'success',
                    'output': result
                }
    except ConnectError as e:
        return {
            'device': device_info['name'],
            'status': 'error',
            'output': f"Connection error: {str(e)}"
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
    args = parse_arguments()
    devices = load_devices(args.site)
    
    if not devices:
        if args.site:
            console.print(f"[red]No devices found matching site code: {args.site}[/red]")
        else:
            console.print("[red]No devices found in the configuration file[/red]")
        sys.exit(1)
    
    console.print("[bold blue]Junos Multi-Device CLI Tool[/bold blue]")
    if args.site:
        console.print(f"[blue]Filtered by site: {args.site}[/blue]")
    
    credentials = get_credentials()
    
    console.print("\nType 'exit' to quit the program\n")

    while True:
        try:
            command = Prompt.ask("[yellow]Enter command(type 'exit' to quit)[/yellow]")
            
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
