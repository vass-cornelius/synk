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
    # Rich is a dependency, so we handle its absence gracefully before the check.
    print("Rich library not found. The installer needs it to run.")
    print("Attempting to install dependencies now...")
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
        print("Dependencies installed successfully. Please run the script again.")
    except subprocess.CalledProcessError:
        print("Failed to install dependencies. Please run 'pip3 install -r requirements.txt' manually.")
    sys.exit(0)

def check_and_install_dependencies(console):
    """Checks for required packages and installs them if missing."""
    with open('requirements.txt', 'r') as f:
        required_packages = [line.strip() for line in f if line.strip() and not line.startswith('#')]

    missing_packages = []
    for package in required_packages:
        try:
            # The package name for checking might be different (e.g., python-dotenv -> dotenv)
            # This is a simple check; for more complex cases, a mapping would be needed.
            # For this project, the import names match the requirement names well enough.
            dist = pkg_resources.get_distribution(package)
        except pkg_resources.DistributionNotFound:
            missing_packages.append(package)

    if not missing_packages:
        console.print("✅ [green]All required packages are already installed.[/green]")
        return True

    console.print(f"🟡 [yellow]Missing packages found: {', '.join(missing_packages)}[/yellow]")
    if Confirm.ask("Do you want to install them now?", default=True):
        console.print("Installing dependencies with `pip3 install -r requirements.txt`...")
        try:
            # Using pip3 directly is more robust in some environments
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

    # --- Step 0: Check and install dependencies ---
    if not check_and_install_dependencies(console):
        sys.exit(1) # Exit if installation fails or is declined

    console.print("\nThis script will help you create your personal `.env` configuration file.")

    # --- Step 1: Create .env file ---
    env_vars = {}
    
    if os.path.exists('.env'):
        if not Confirm.ask("\n[yellow]An `.env` file already exists. Do you want to overwrite it?[/yellow]", default=False):
            console.print("\nSkipping `.env` file creation.")
            env_vars = None # Flag to skip writing the file
        else:
            console.print() # Add a newline for spacing

    if env_vars is not None:
        console.print("[bold]Please provide your Moco details:[/bold]")
        env_vars['MOCO_SUBDOMAIN'] = Prompt.ask("  Enter your Moco subdomain (e.g., 'your-company')")
        env_vars['MOCO_API_KEY'] = Prompt.ask("  Enter your Moco API Key")

        console.print("\n[bold]Please provide your JIRA details:[/bold]")
        env_vars['JIRA_SERVER'] = Prompt.ask("  Enter your JIRA server URL (e.g., 'https://your-domain.atlassian.net')")
        env_vars['JIRA_USER_EMAIL'] = Prompt.ask("  Enter your JIRA login email")
        env_vars['JIRA_API_TOKEN'] = Prompt.ask("  Enter your JIRA API Token")

        console.print("\n[bold]Optional Configuration:[/bold]")
        env_vars['DEFAULT_TASK_NAME'] = Prompt.ask("  Enter a default task name pattern (e.g., '^CH: Main'). Leave empty to skip")

        # Create the .env file content
        env_content = f"""# -- Moco Configuration --
MOCO_SUBDOMAIN="{env_vars['MOCO_SUBDOMAIN']}"
MOCO_API_KEY="{env_vars['MOCO_API_KEY']}"

# -- JIRA Configuration --
JIRA_SERVER="{env_vars['JIRA_SERVER']}"
JIRA_USER_EMAIL="{env_vars['JIRA_USER_EMAIL']}"
JIRA_API_TOKEN="{env_vars['JIRA_API_TOKEN']}"

# -- Optional: Default Task Name --
DEFAULT_TASK_NAME="{env_vars['DEFAULT_TASK_NAME']}"
"""
        try:
            with open('.env', 'w') as f:
                f.write(env_content)
            console.print("\n✅ [green]Successfully created the `.env` configuration file.[/green]")
        except IOError as e:
            console.print(f"\n❌ [red]Error: Could not write to .env file: {e}[/red]")
            sys.exit(1)

    # --- Step 2: Make .command files executable ---
    try:
        console.print("\nMaking script files executable...")
        command_files = glob.glob('*.command')
        if not command_files:
            console.print("[yellow]No `.command` files found to make executable.[/yellow]")
        
        for file_path in command_files:
            # Add execute permissions for user, group, and others
            current_permissions = os.stat(file_path).st_mode
            os.chmod(file_path, current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            console.print(f"  ✅ [green]Made `{file_path}` executable.[/green]")
            
    except Exception as e:
        console.print(f"\n❌ [red]Error: Could not make scripts executable: {e}[/red]")

    console.print(Panel.fit("\n🎉 [bold green]Setup Complete![/bold green] 🎉\nYou can now use the `start-synk.command` and `start-watcher.command` files."))

if __name__ == "__main__":
    main()
