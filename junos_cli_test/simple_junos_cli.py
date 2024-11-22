#!/usr/bin/env python3

from rich.console import Console
from rich.panel import Panel

console = Console()

def show_help():
    """Display help information in a panel."""
    help_text = """
[bold white]Available Commands:[/bold white]
• [green]show[/green] commands (e.g., 'show interfaces', 'show version')
• [green]set[/green] commands for configuration
• Type [bold yellow]'exit'[/bold yellow] at any time to quit the program
• Press [bold yellow]Ctrl+C[/bold yellow] to cancel current operation

[bold white]Tips:[/bold white]
• Commands are case-insensitive
• Extra spaces are automatically cleaned
• Use arrow keys to navigate command history
• Common show commands: version, interfaces, chassis, system information
"""
    console.print(Panel(help_text, title="[bold blue]Help & Usage[/bold blue]", border_style="blue"))

def main():
    """Main function to run the CLI tool."""
    try:
        console.print("\n[bold blue]Junos Multi-Device CLI Tool[/bold blue]")
        console.print("[dim]Type 'help' at any time to see available commands and usage tips[/dim]")
        
        # Show help at startup
        show_help()
        
        # Wait for user input
        input("\nPress Enter to exit...")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Program interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Fatal error: {str(e)}[/red]")
    finally:
        console.print("\n[blue]Exiting program. Goodbye![/blue]")

if __name__ == "__main__":
    main()
