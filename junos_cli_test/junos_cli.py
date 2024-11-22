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
import json
import os

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
    parser.add_argument('-o', '--output',
                      help='Output file path (supports .json, .txt, or .csv formats)',
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
    
    # Split command and grep pattern if exists
    command_parts = command.split(' | grep ')
    base_command = command_parts[0]
    grep_pattern = command_parts[1] if len(command_parts) > 1 else None
    
    try:
        with suppress_junos_logs():
            with Device(host=device_info['host'],
                    user=username,
                    password=password,
                    auto_add_policy=True,  # Automatically accept SSH host keys
                    port=22) as dev:
                
                # Execute command based on type
                if base_command.startswith('show'):
                    result = dev.cli(base_command, warning=False)
                    
                    # Apply grep filter if specified
                    if grep_pattern:
                        filtered_lines = []
                        for line in result.split('\n'):
                            if grep_pattern.lower() in line.lower():
                                filtered_lines.append(line)
                        result = '\n'.join(filtered_lines)
                else:
                    # For configuration commands
                    with dev.config(mode='exclusive') as cu:
                        cu.load(base_command, format='set')
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

def save_results(results, output_file):
    """Save results to a file based on the file extension."""
    # Get file extension
    _, ext = os.path.splitext(output_file.lower())
    
    try:
        if ext == '.json':
            # Save as JSON
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)
        elif ext == '.csv':
            # Save as CSV
            import csv
            with open(output_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Device', 'Status', 'Output'])
                for result in results:
                    writer.writerow([result['device'], result['status'], result['output']])
        else:
            # Default to txt format
            with open(output_file, 'w') as f:
                for result in results:
                    f.write(f"Device: {result['device']}\n")
                    f.write(f"Status: {result['status']}\n")
                    f.write("Output:\n")
                    f.write(result['output'])
                    f.write("\n" + "="*50 + "\n\n")
        
        console.print(f"\n[green]Results saved to {output_file}[/green]")
    except Exception as e:
        console.print(f"\n[red]Error saving results to {output_file}: {str(e)}[/red]")

def display_results(results, output_file=None):
    """Display results in a formatted table and optionally save to file."""
    table = Table(show_header=True, header_style="bold magenta", show_lines=True)
    table.add_column("Device", style="cyan")
    table.add_column("Status", width=12)
    table.add_column("Output")

    for result in results:
        status_color = "green" if result['status'] == 'success' else "red"
        table.add_row(
            result['device'],
            f"[{status_color}]{result['status']}[/{status_color}]",
            result['output']
        )

    console.print(table)
    
    # Save results if output file is specified
    if output_file:
        save_results(results, output_file)

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

            display_results(results, args.output)
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled by user[/yellow]")
            break
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")

if __name__ == "__main__":
    main()
