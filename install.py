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
            return None

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
        return venv_path
    except FileNotFoundError:
        print(f"❌ Error: Could not find pip executable at '{pip_executable}'.")
        return None
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies:")
        # Print the error output from pip for better debugging
        print(e.stderr)
        return False

def main():
    """
    An interactive script to configure Synk and prepare it for first use.
    """
    print("🚀 Synk Setup Assistant 🚀")

    # --- Step 0: Setup virtual environment and install dependencies ---
    venv_path = setup_virtual_environment()
    if not venv_path:
        sys.exit(1) # Exit if installation fails

    # After successful venv setup, execute rich_setup.py using the venv's python interpreter
    pip_executable = os.path.join(venv_path, 'bin', 'python')    
    try:
        subprocess.check_call([pip_executable, 'rich_setup.py'])
        print("\n✅ Rich setup executed successfully within the virtual environment.")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Failed to execute rich_setup.py: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print(f"❌ Error: Could not find python executable at '{pip_executable}'.")
        sys.exit(1)


if __name__ == "__main__":
    main()
