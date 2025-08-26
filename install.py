import os
import stat
import glob
import sys
import subprocess

def setup_virtual_environment():
    """
    Creates a virtual environment and installs dependencies into it.
    Uses plain print statements as this runs before rich is guaranteed to be installed.
    """
    venv_path = "venv"
    
    if not os.path.exists(venv_path):
        print("Creating a dedicated virtual environment for Synk...")
        try:
            subprocess.check_call([sys.executable, '-m', 'venv', venv_path])
            print("✅ Virtual environment created successfully.")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to create virtual environment: {e}")
            return False

    print("\nInstalling/updating required packages into the virtual environment...")
    
    # Determine the correct pip executable path within the venv
    pip_executable = os.path.join(venv_path, 'bin', 'pip')
    
    try:
        # Use subprocess.run to capture output and hide it unless there's an error
        result = subprocess.run(
            [pip_executable, 'install', '-r', 'requirements.txt'],
            capture_output=True, text=True, check=True
        )
        print("✅ Dependencies installed successfully.")
        return True
    except FileNotFoundError:
        print(f"❌ Error: Could not find pip executable at '{pip_executable}'.")
        return False
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies:")
        # Print the error output from pip for better debugging
        print(e.stderr)
        return False

def run_rich_setup():
    """
    Runs the main part of the setup using the 'rich' library for a better UI.
    This function is called only after dependencies are confirmed to be installed.
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm

    console = Console()
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

        console.print("\n[bold]JIRA Configuration (supports multiple instances):[/bold]")
        jira_instances_str = Prompt.ask("  Enter short names for your JIRA instances, separated by commas (e.g., work,client_a)")
        jira_instances = [name.strip() for name in jira_instances_str.split(',') if name.strip()]
        
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

        console.print("\n[bold]Optional Configuration:[/bold]")
        env_vars['DEFAULT_TASK_NAME'] = Prompt.ask("  Enter a default task name pattern (e.g., '^CH: Main'). Leave empty to skip")
        env_vars['QUESTION_ORDER'] = Prompt.ask("  Enter question order (default: project,task,jira,comment,time)", default="project,task,jira,comment,time")

        # Create the .env file content
        env_content = f"""# -- Moco Configuration --
MOCO_SUBDOMAIN="{env_vars['MOCO_SUBDOMAIN']}"
MOCO_API_KEY="{env_vars['MOCO_API_KEY']}"

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
DEFAULT_TASK_NAME="{env_vars['DEFAULT_TASK_NAME']}"
QUESTION_ORDER="{env_vars['QUESTION_ORDER']}"
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

def main():
    """
    An interactive script to configure Synk and prepare it for first use.
    """
    print("🚀 Synk Setup Assistant 🚀")

    # --- Step 0: Setup virtual environment and install dependencies ---
    if not setup_virtual_environment():
        sys.exit(1) # Exit if installation fails

    # --- Step 1: Now that dependencies are installed, we can import and use rich ---
    try:
        run_rich_setup()
    except ImportError:
        print("\nCould not import the 'rich' library even after installation.")
        print("Continuing with basic setup (plain text).")
        # A fallback to a plain text setup could be implemented here if needed.
        # For now, we will assume the installation was successful if we reached this point.
        print("\nSetup is complete. You can now use the .command files.")


if __name__ == "__main__":
    main()
