# Junos Multi-Device CLI Interaction Tool

This tool allows you to execute commands on multiple Junos devices simultaneously and view their outputs in an organized manner.

## Features
- Connect to multiple Junos devices simultaneously
- Execute CLI commands across all connected devices
- Display results in a clear, formatted output
- Support for both operational and configuration commands
- Secure connection handling with error management
- Interactive credential input (no stored passwords)

## Installation

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

## Usage

1. Update the `devices.csv` file with your device information
2. Run the script:
```bash
python junos_cli.py
```

3. Enter your username and password when prompted (these credentials will be used for all devices)
4. Enter commands when prompted. The tool will execute them on all configured devices simultaneously.

## Configuration

Edit `devices.csv` to add your devices. The file should be in CSV format with the following columns:
- name: Device name for identification
- host: IP address or hostname

Example `devices.csv`:
```csv
name,host
router1,192.168.1.1
router2,192.168.1.2
```

## Security Features
- Credentials are prompted interactively and never stored
- Password input is masked during entry
- Same credentials are used for all devices to simplify management
- SSH key-based authentication is supported (recommended for production environments)
