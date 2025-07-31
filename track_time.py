# --- IMPORTS ---
import os
import re
import sys
import pkg_resources
from datetime import datetime, timedelta, date


# --- DEPENDENCY CHECK ---
required_packages = ['requests', 'jira', 'python-dotenv', 'rich']
missing_packages = []
for package in required_packages:
    try:
        pkg_resources.get_distribution(package)
    except pkg_resources.DistributionNotFound:
        missing_packages.append(package)

if missing_packages:
    print("❌ Error: Required Python libraries are missing.")
    print("Please install them by running this command in your terminal:")
    install_command = f"pip3 install {' '.join(missing_packages)}"
    print(f"\n  {install_command}\n")
    sys.exit(1)

# --- Rich and other library imports ---
import requests
from jira import JIRA, JIRAError
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.text import Text

# --- API HELPER FUNCTIONS ---
def moco_get(session, subdomain, endpoint, params=None):
    """Generic GET request handler for Moco API."""
    url = f"https://{subdomain}.mocoapp.com/api/v1/{endpoint}"
    try:
        response = session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        Console().print(f"[bold red]❌ Moco API Error:[/bold red] {e}")
        sys.exit(1)

def moco_post(session, subdomain, endpoint, data):
    """Generic POST request handler for Moco API."""
    url = f"https://{subdomain}.mocoapp.com/api/v1/{endpoint}"
    try:
        response = session.post(url, json=data)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        Console().print(f"[bold red]❌ Moco API Error creating entry:[/bold red] {e.response.text if e.response else e}")
        sys.exit(1)

def get_last_entry_end_time(session, subdomain, user_id, for_date):
    """Fetch end time of the last entry by parsing its description."""
    params = {'user_id': user_id, 'from': for_date.isoformat(), 'to': for_date.isoformat()}
    activities = moco_get(session, subdomain, "activities", params=params)
    if not activities:
        return None
    
    activities.sort(key=lambda x: x.get('id', 0), reverse=True)
    description = activities[0].get("description", "")
    match = re.search(r'\((\d{2}:\d{2})-(\d{2}:\d{2})\)', description)
    return match.group(2) if match else None

def validate_time_format(time_str):
    """Check if a string is in HH:mm format."""
    return re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", time_str) is not None

# --- SETUP AND VERIFICATION ---
def setup_clients(console):
    """Load environment variables, verify credentials, and initialize API clients."""
    load_dotenv()
    moco_subdomain = os.getenv("MOCO_SUBDOMAIN")
    moco_api_key = os.getenv("MOCO_API_KEY")
    jira_server = os.getenv("JIRA_SERVER")
    jira_user_email = os.getenv("JIRA_USER_EMAIL")
    jira_api_token = os.getenv("JIRA_API_TOKEN")
    default_task_name = os.getenv("DEFAULT_TASK_NAME")

    if not all([moco_subdomain, moco_api_key, jira_server, jira_user_email, jira_api_token]):
        console.print("[bold red]❌ Error: One or more required environment variables are missing.[/bold red]")
        sys.exit(1)

    with console.status("[yellow]Connecting to services...[/yellow]"):
        try:
            auth_header = {'Authorization': f'Bearer {moco_api_key}'}
            session_url = f"https://{moco_subdomain}.mocoapp.com/api/v1/session"
            response = requests.get(session_url, headers=auth_header)
            response.raise_for_status()
            moco_user_id = response.json()['id']
            console.print("✅ [green]Moco connection successful.[/green]")
        except (requests.exceptions.RequestException, KeyError) as e:
            console.print(f"❌ [bold red]Moco connection failed:[/bold red] {e}")
            sys.exit(1)

        try:
            jira_client = JIRA(server=jira_server, basic_auth=(jira_user_email, jira_api_token))
            jira_client.myself()
            console.print("✅ [green]JIRA connection successful.[/green]")
        except JIRAError as e:
            console.print(f"❌ [bold red]JIRA connection failed:[/bold red] {e.text}")
            sys.exit(1)
            
    moco_session = requests.Session()
    moco_session.headers.update({'Authorization': f'Bearer {moco_api_key}', 'Content-Type': 'application/json'})

    return moco_session, jira_client, moco_subdomain, moco_user_id, default_task_name

# --- MAIN WORKFLOW ---
def main():
    console = Console()
    console.print(Panel.fit("🚀 [bold blue]Time Tracking Tool[/bold blue] 🚀"))
    
    moco_session, jira_client, moco_subdomain, moco_user_id, default_task_name = setup_clients(console)

    while True:
        date_input = Prompt.ask("[cyan]1.[/cyan] Enter date ([bold]YYYY-MM-DD[/bold]), or leave empty for today")
        if not date_input:
            work_date = date.today()
            break
        try:
            work_date = date.fromisoformat(date_input)
            break
        except ValueError:
            console.print("  [red]Invalid date format. Please try again.[/red]")
            
    console.print(f"\n✅ Tracking time for: [bold yellow]{work_date.strftime('%A, %Y-%m-%d')}[/bold yellow]")

    while True:
        with console.status("[yellow]Fetching projects...[/yellow]"):
            all_assigned_projects = moco_get(moco_session, moco_subdomain, "projects/assigned")
            
            # --- NEW: Stricter project filtering ---
            # A project is only included if it's active AND has at least one active task.
            filtered_projects = []
            for project in all_assigned_projects:
                if project.get('active', False):
                    active_tasks = [t for t in project.get('tasks', []) if t.get('active', False)]
                    if active_tasks:
                        # If the project is valid, update its task list to only the active ones
                        project['tasks'] = active_tasks
                        filtered_projects.append(project)
            
            assigned_projects = filtered_projects
            assigned_projects.sort(key=lambda p: (p.get('customer', {}).get('name', '').lower(), p.get('name', '').lower()))

        if not assigned_projects:
            console.print("\n[bold red]❌ No assigned projects with active tasks were found.[/bold red]")
            break

        console.print("\n[cyan]2.[/cyan] [bold]What project did you work on?[/bold]")
        for i, p in enumerate(assigned_projects):
            customer = p.get('customer', {}).get('name', 'No Customer')
            console.print(f"  [magenta][{i+1:>2}][/magenta] {customer} / {p['name']}")
        
        while True:
            try:
                proj_choice = int(Prompt.ask("[bold]Project number[/bold]")) - 1
                if 0 <= proj_choice < len(assigned_projects):
                    selected_project_data = assigned_projects[proj_choice]
                    break
                else: console.print("  [red]Choice out of range. Try again.[/red]")
            except ValueError: console.print("  [red]Please enter a valid number.[/red]")
        
        tasks_original = selected_project_data.get('tasks', [])
        # The tasks list is already pre-filtered, so we don't need to check for empty here
        
        tasks_display = []
        for task in tasks_original:
            display_name = task.get('name', '').split('|')[0].strip()
            tasks_display.append({**task, 'display_name': display_name})

        default_task = None
        if default_task_name:
            for task in tasks_display:
                if re.search(default_task_name, task.get('name', '')):
                    default_task = task
                    break
        
        task_prompt = Text("\n3. ", style="cyan", end="")
        task_prompt.append("What task did you work on?", style="bold")
        if default_task: task_prompt.append(f" (empty for '{default_task['display_name']}')")
        
        console.print(task_prompt)
        for i, t in enumerate(tasks_display): console.print(f"  [magenta][{i+1:>2}][/magenta] {t['display_name']}")
        
        while True:
            choice_input = Prompt.ask("[bold]Task number[/bold]")
            if default_task and not choice_input:
                selected_task = default_task
                console.print(f"  ✅ Defaulting to: [bright_magenta]{selected_task['display_name']}[/bright_magenta]")
                break
            try:
                choice = int(choice_input) - 1
                if 0 <= choice < len(tasks_display):
                    selected_task = tasks_display[choice]
                    break
                else: console.print("  [red]Choice out of range. Try again.[/red]")
            except ValueError: console.print("  [red]Invalid input. Please enter a number.[/red]")

        jira_issue, jira_id = None, None
        while True:
            jira_id_input = Prompt.ask("\n[cyan]4.[/cyan] [bold]JIRA ticket?[/bold] (e.g., PROJ-123, empty to skip)")
            if not jira_id_input: break
            try:
                with console.status(f"[yellow]Verifying {jira_id_input.upper()}...[/yellow]"):
                    jira_issue = jira_client.issue(jira_id_input.upper())
                console.print(f"  ✅ [green]Found:[/green] {jira_issue.fields.summary}")
                jira_id = jira_id_input.upper()
                break
            except JIRAError: console.print(f"  ❌ [red]JIRA ticket '{jira_id_input}' not found. Try again.[/red]")
        
        comment = Prompt.ask("\n[cyan]5.[/cyan] [bold]Anything to add (comment)?[/bold]")

        last_end_time = get_last_entry_end_time(moco_session, moco_subdomain, moco_user_id, work_date)
        start_prompt = Text("\n6. ", style="cyan", end="")
        start_prompt.append("When did you start?", style="bold")
        if last_end_time: start_prompt.append(f" ('last' for {last_end_time})")
        
        while True:
            start_time_str = Prompt.ask(start_prompt)
            if start_time_str.lower() == 'last' and last_end_time:
                start_time_str = last_end_time; break
            if start_time_str.lower() == 'last' and not last_end_time:
                console.print(f"  [yellow]No entries on {work_date.isoformat()} to start after.[/yellow]")
            elif validate_time_format(start_time_str): break
            else: console.print("  [red]Invalid format. Use HH:mm or 'last'.[/red]")

        end_prompt = Text("\n7. ", style="cyan", end="")
        end_prompt.append(f"When did you finish? (start: {start_time_str})", style="bold")
        end_prompt.append(" (HH:mm or decimal hours)")
        
        while True:
            end_input = Prompt.ask(end_prompt)
            start_time_dt = datetime.strptime(start_time_str, "%H:%M")
            if validate_time_format(end_input):
                end_time_dt = datetime.strptime(end_input, "%H:%M")
                if end_time_dt <= start_time_dt: console.print("  [red]End time must be after start time.[/red]"); continue
                duration_hours = (end_time_dt - start_time_dt).total_seconds() / 3600
                end_time_str = end_input; break
            else:
                try:
                    duration_hours = float(end_input)
                    if duration_hours <= 0: console.print("  [red]Duration must be positive.[/red]"); continue
                    end_time_str = (start_time_dt + timedelta(hours=duration_hours)).strftime("%H:%M"); break
                except ValueError: console.print("  [red]Invalid format.[/red]")

        customer_name_summary = selected_project_data.get('customer',{}).get('name', 'No Customer')
        time_part = f"({start_time_str}-{end_time_str})"
        desc_parts = [part for part in [jira_id, comment, time_part] if part]
        description = " ".join(desc_parts)

        summary_text = Text()
        summary_text.append(f"Project:    {customer_name_summary} / {selected_project_data['name']}\n", style="white")
        summary_text.append(f"Task:       {selected_task['display_name']}\n", style="white")
        if jira_id: summary_text.append(f"JIRA Ticket: {jira_id}\n", style="white")
        summary_text.append(f"Time:       {start_time_str} - {end_time_str} ({duration_hours:.2f} hours)\n", style="yellow")
        summary_text.append(f"Description: {description}", style="white")
        
        console.print(Panel(summary_text, title="[bold blue]Summary[/bold blue]", border_style="blue", expand=False))

        if Confirm.ask("\n[bold]💾 Save this entry?[/bold]", default=True):
            with console.status("[yellow]Saving...[/yellow]"):
                moco_payload = {
                    "date": work_date.isoformat(), "project_id": selected_project_data['id'],
                    "task_id": selected_task['id'], "hours": round(duration_hours, 4), "description": description
                }
                moco_post(moco_session, moco_subdomain, "activities", data=moco_payload)
                console.print("✅ [green]Entry saved to Moco.[/green]")
                
                if jira_issue:
                    try:
                        jira_comment = f"{comment} {time_part}".strip()
                        jira_client.add_worklog(
                            issue=jira_issue, timeSpentSeconds=int(duration_hours*3600),
                            comment=jira_comment, started=datetime.combine(work_date, start_time_dt.time()).astimezone()
                        )
                        console.print("✅ [green]Worklog added to JIRA.[/green]")
                    except JIRAError as e: console.print(f"❌ [red]Failed to add JIRA worklog:[/red] {e.text}")
        else:
            console.print(" Canceled.")

        if not Confirm.ask("\n[bold]➕ Add another entry for this date?[/bold]"):
            break
            
    console.print("\n[bold blue]Time tracking finished. Goodbye! 👋[/bold blue]")

if __name__ == "__main__":
    main()