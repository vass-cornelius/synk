import os
import stat
import glob
import sys
import subprocess

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
except ImportError:
    # Rich is a dependency, so we handle its absence gracefully before the check.
    print("Rich library not found. The installer needs it to run.")
    print("Attempting to install dependencies now...")
    try:
        # Use the correct python executable to run pip
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
        print("Dependencies installed successfully. Please run the script again.")
    except subprocess.CalledProcessError:
        print("Failed to install dependencies. Please run 'python3 -m pip install -r requirements.txt' manually.")
    sys.exit(0)

def install_dependencies(console):
    """Asks the user to install or update dependencies from requirements.txt."""
    console.print("This tool requires several Python packages to run correctly.")
    if Confirm.ask("Do you want to install/update them now from `requirements.txt`?", default=True):
        console.print("Installing dependencies...")
        try:
            # Use sys.executable to ensure we use the pip associated with the current python interpreter
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
            console.print("✅ [green]Dependencies installed successfully.[/green]")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            console.print(f"❌ [red]Failed to install dependencies: {e}[/red]")
            console.print(f"Please run `{sys.executable} -m pip install -r requirements.txt` manually and then run this script again.")
            return False
    else:
        console.print("[yellow]Skipping dependency installation. The tool may not run correctly.[/yellow]")
        return True # Allow the user to proceed at their own risk


def main():
    """
    An interactive script to configure Synk and prepare it for first use.
    """
    console = Console()
    console.print(Panel.fit("🚀 [bold blue]Synk Setup Assistant[/bold blue] 🚀"))

    # --- Step 0: Install dependencies ---
    if not install_dependencies(console):
        sys.exit(1) # Exit if installation fails

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

if __name__ == "__main__":
    main()
