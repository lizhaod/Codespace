#!/usr/bin/env python3

import csv
import concurrent.futures
from jnpr.junos import Device
from jnpr.junos.exception import ConnectError
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
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

class LogCapture:
    """Context manager to capture and store log messages."""
    def __init__(self):
        self.messages = []
        self.handler = None
        self.has_error = False

    def emit(self, record):
        if record.levelno >= logging.ERROR:
            self.has_error = True
        self.messages.append(self.handler.format(record))

    def __enter__(self):
        # Create a handler that stores messages
        self.handler = logging.StreamHandler()
        self.handler.setFormatter(logging.Formatter('%(message)s'))
        self.handler.emit = self.emit
        
        # Remove existing handlers and add our capture handler
        logger.handlers = []
        logger.addHandler(self.handler)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore default logging
        logger.handlers = []
        logger.addHandler(logging.StreamHandler())
        
    def display_logs(self):
        """Display all captured log messages only if errors occurred."""
        if self.has_error:
            console.print("\n[bold red]Connection Errors:[/bold red]")
            for message in self.messages:
                if "ERROR" in message or "WARNING" in message:
                    console.print(message)

def find_devices_file():
    """Find the devices.csv file in either current directory or script directory."""
    # Try current working directory first
    cwd_path = os.path.join(os.getcwd(), 'devices.csv')
    if os.path.exists(cwd_path):
        return cwd_path
        
    # Try script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, 'devices.csv')
    if os.path.exists(script_path):
        return script_path
        
    return None

def load_devices(site=None):
    """Load device information from CSV file."""
    devices = []
    
    # Find devices.csv file
    devices_file = find_devices_file()
    if not devices_file:
        console.print("[red]Error: devices.csv not found in current directory or script directory[/red]")
        console.print("[blue]Please ensure devices.csv exists in one of these locations:[/blue]")
        console.print(f"[blue]1. Current directory: {os.getcwd()}[/blue]")
        console.print(f"[blue]2. Script directory: {os.path.dirname(os.path.abspath(__file__))}[/blue]")
        return []
    
    try:
        with open(devices_file, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    name, host = line.strip().split(',')
                    if site is None or site.lower() in name.lower():
                        devices.append({
                            'name': name.strip(),
                            'host': host.strip()
                        })
        return devices
    except Exception as e:
        logger.error(f"Error loading devices configuration: {str(e)}")
        return []

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
    
    # Enhanced SSH connection parameters
    ssh_config = {
        'StrictHostKeyChecking': 'no',
        'UserKnownHostsFile': '/dev/null',
        'ServerAliveInterval': '30',
        'ServerAliveCountMax': '5',
        'TCPKeepAlive': 'yes',
        'ControlMaster': 'auto',
        'ControlPersist': '10m',
        'ConnectTimeout': '300',
        'ConnectionAttempts': '3',
        'GSSAPIAuthentication': 'no',
        'PreferredAuthentications': 'password,keyboard-interactive',
        'NumberOfPasswordPrompts': '3',
        'KexAlgorithms': '+diffie-hellman-group14-sha1,diffie-hellman-group-exchange-sha1',
        'Ciphers': '+aes128-cbc,aes192-cbc,aes256-cbc,3des-cbc',
        'HostKeyAlgorithms': '+ssh-rsa,ssh-dss',
        'PubkeyAcceptedKeyTypes': '+ssh-rsa,ssh-dss'
    }
    
    # Common device parameters
    device_params = {
        'host': device_info['host'],
        'user': username,
        'password': password,
        'gather_facts': False,  # Skip fact gathering for faster connection
        'normalize': True,
        'timeout': 300,  # Connection timeout in seconds (5 minutes)
        'attempts': 3,   # Number of connection attempts
        'auto_probe': 30,  # Auto probe every 30 seconds
        'ssh_config': None,  # Using custom ssh_options instead
        'ssh_private_key_file': None,
        'ssh_options': ssh_config
    }
    
    def try_connection(port):
        """Try to connect using specified port."""
        try:
            with suppress_junos_logs():
                # Update device parameters with current port
                dev_params = device_params.copy()
                dev_params['port'] = port
                
                # Attempt connection
                dev = Device(**dev_params)
                
                with dev:
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
            logger.error(f"Connection failed on port {port} for {device_info['name']} ({device_info['host']}): {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error on port {port} for {device_info['name']} ({device_info['host']}): {str(e)}")
            return None

    # Try NETCONF port first (830)
    result = try_connection(830)
    if result:
        return result
        
    # Fallback to SSH port (22)
    result = try_connection(22)
    if result:
        return result

    # If both attempts fail, return error
    error_msg = "Failed to connect on both NETCONF (830) and SSH (22) ports"
    logger.error(f"{error_msg} for {device_info['name']} ({device_info['host']})")
    return {
        'device': device_info['name'],
        'status': 'error',
        'output': error_msg
    }

def execute_commands_with_progress(devices, command, credentials):
    """Execute commands on all devices with a progress bar."""
    results = []
    error_console = Console(stderr=True, highlight=False)
    
    # Clear screen and hide cursor
    console.clear()
    console.show_cursor(False)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False,
        refresh_per_second=10,
        expand=True
    ) as progress:
        try:
            # Create single progress task
            task = progress.add_task(
                f"[cyan]Executing command on {len(devices)} devices...",
                total=len(devices)
            )
            
            # Print a newline after progress bar for error messages
            print("")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                future_to_device = {}
                
                # Submit all tasks
                for device in devices:
                    future = executor.submit(execute_command, device, command, credentials)
                    future_to_device[future] = device
                
                # Process completed tasks
                for future in concurrent.futures.as_completed(future_to_device):
                    device = future_to_device[future]
                    try:
                        result = future.result()
                        # Update progress description to show current device
                        progress.update(task, 
                                     advance=1, 
                                     description=f"[cyan]Processing {result['device']} ({future_to_device[future]['host']})...")
                        results.append(result)
                        
                        # If there's an error in the result, display it
                        if result['status'] == 'error':
                            error_console.print(f"[red]{result['device']}: {result['output']}[/red]")
                            
                    except Exception as e:
                        error_msg = f"Error: {str(e)}"
                        results.append({
                            'device': device['name'],
                            'status': 'error',
                            'output': error_msg
                        })
                        error_console.print(f"[red]{device['name']}: {error_msg}[/red]")
                        progress.update(task, advance=1)
                        
        finally:
            console.show_cursor(True)
    
    # Add a newline after all processing is done
    print("")
    return results

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
            
            results = execute_commands_with_progress(devices, command, credentials)
            display_results(results, args.output)
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled by user[/yellow]")
            break
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")

if __name__ == "__main__":
    main()
