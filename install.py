import os
import stat
import glob
import sys
import subprocess
import pkg_resources

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
except ImportError:
    print("Error: The 'rich' library is not installed.")
    print("Please install it first by running: pip3 install rich")
    sys.exit(1)

def check_and_install_dependencies(console):
    """Checks for required packages and installs them if missing."""
    with open('requirements.txt', 'r') as f:
        required_packages = [line.strip() for line in f if line.strip() and not line.startswith('#')]

    missing_packages = []
    for package in required_packages:
        try:
            pkg_resources.get_distribution(package)
        except pkg_resources.DistributionNotFound:
            missing_packages.append(package)

    if not missing_packages:
        console.print("✅ [green]All required packages are already installed.[/green]")
        return True

    console.print(f"🟡 [yellow]Missing packages found: {', '.join(missing_packages)}[/yellow]")
    if Confirm.ask("Do you want to install them now?", default=True):
        console.print("Installing dependencies with `pip3 install -r requirements.txt`...")
        try:
            subprocess.check_call(['pip3', 'install', '-r', 'requirements.txt'])
            console.print("✅ [green]Dependencies installed successfully.[/green]")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            console.print(f"❌ [red]Failed to install dependencies: {e}[/red]")
            console.print("Please run `pip3 install -r requirements.txt` manually and then run this script again.")
            return False
    else:
        console.print("[red]Installation canceled. The tool may not run correctly without dependencies.[/red]")
        return False

def main():
    """
    An interactive script to configure Synk and prepare it for first use.
    """
    console = Console()
    console.print(Panel.fit("🚀 [bold blue]Synk Setup Assistant[/bold blue] 🚀"))

    if not check_and_install_dependencies(console):
        sys.exit(1)

    console.print("\nThis script will help you create your personal `.env` configuration file.")

    if os.path.exists('.env'):
        if not Confirm.ask("\n[yellow]An `.env` file already exists. Do you want to overwrite it?[/yellow]", default=False):
            console.print("\nSkipping `.env` file creation.")
            # Still make scripts executable
            make_scripts_executable(console)
            console.print(Panel.fit("\n🎉 [bold green]Setup Complete![/bold green] 🎉\nYou can now use the `start-synk.command` and `start-watcher.command` files."))
            sys.exit(0)

    # --- Moco Configuration ---
    console.print("\n[bold]Please provide your Moco details:[/bold]")
    moco_subdomain = Prompt.ask("  Enter your Moco subdomain (e.g., 'your-company')")
    moco_api_key = Prompt.ask("  Enter your Moco API Key")

    # --- JIRA Configuration ---
    console.print("\n[bold]JIRA Configuration (supports multiple instances):[/bold]")
    jira_instances_str = Prompt.ask("  Enter short names for your JIRA instances, separated by commas (e.g., work,client_a)")
    jira_instances = [name.strip() for name in jira_instances_str.split(',')]
    
    jira_configs = {}
    for instance in jira_instances:
        console.print(f"\n[bold]Configuring JIRA instance: '{instance}'[/bold]")
        server = Prompt.ask(f"  Enter server URL for '{instance}' (e.g., 'https://{instance}.atlassian.net')")
        email = Prompt.ask(f"  Enter login email for '{instance}'")
        token = Prompt.ask(f"  Enter API Token for '{instance}'")
        keys = Prompt.ask(f"  Enter project keys for '{instance}', separated by commas (e.g., SYN,DEVOPS)")
        jira_configs[instance] = {
            "server": server,
            "email": email,
            "token": token,
            "keys": keys.upper()
        }

    # --- Optional Configuration ---
    console.print("\n[bold]Optional Configuration:[/bold]")
    default_task_name = Prompt.ask("  Enter a default task name pattern (e.g., '^CH: Main'). Leave empty to skip")
    question_order = Prompt.ask("  Enter question order (default: project,task,jira,comment,time)", default="project,task,jira,comment,time")

    # --- Create .env file ---
    env_content = f"""# -- Moco Configuration --
MOCO_SUBDOMAIN="{moco_subdomain}"
MOCO_API_KEY="{moco_api_key}"

# -- JIRA Instance Configuration --
JIRA_INSTANCES="{','.join(jira_instances)}"

"""
    for instance, config in jira_configs.items():
        env_content += f"""# -- JIRA '{instance}' Details --
JIRA_{instance.upper()}_SERVER="{config['server']}"
JIRA_{instance.upper()}_USER_EMAIL="{config['email']}"
JIRA_{instance.upper()}_API_TOKEN="{config['token']}"
JIRA_{instance.upper()}_PROJECT_KEYS="{config['keys']}"

"""
    env_content += f"""# -- Workflow Configuration --
DEFAULT_TASK_NAME="{default_task_name}"
QUESTION_ORDER="{question_order}"
"""
    try:
        with open('.env', 'w') as f:
            f.write(env_content)
        console.print("\n✅ [green]Successfully created the `.env` configuration file.[/green]")
    except IOError as e:
        console.print(f"\n❌ [red]Error: Could not write to .env file: {e}[/red]")
        sys.exit(1)

    make_scripts_executable(console)
    console.print(Panel.fit("\n🎉 [bold green]Setup Complete![/bold green] 🎉\nYou can now use the `start-synk.command` and `start-watcher.command` files."))

def make_scripts_executable(console):
    """Makes .command files executable."""
    try:
        console.print("\nMaking script files executable...")
        command_files = glob.glob('*.command')
        if not command_files:
            console.print("[yellow]No `.command` files found to make executable.[/yellow]")
        
        for file_path in command_files:
            current_permissions = os.stat(file_path).st_mode
            os.chmod(file_path, current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            console.print(f"  ✅ [green]Made `{file_path}` executable.[/green]")
            
    except Exception as e:
        console.print(f"\n❌ [red]Error: Could not make scripts executable: {e}[/red]")

if __name__ == "__main__":
    main()
