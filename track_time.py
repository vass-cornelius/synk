# --- IMPORTS ---
import os
import re
import sys
import json
from datetime import date, datetime

# --- Rich and other library imports ---
import requests
from requests.auth import HTTPBasicAuth
from jira import JIRA, JIRAError
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich.table import Table

from logic import TimeTracker, SynkError, parse_and_validate_time_input

# --- WORKFLOW STEP FUNCTIONS ---
def display_daily_entries(console, activities):
    """Fetches and displays all entries for a given date."""
    if not activities:
        console.print("  [grey53]No entries found for this date.[/grey53]")
        return

    table = Table(show_header=True, header_style="bold magenta", border_style="dim")
    table.add_column("Time", style="cyan", width=15)
    table.add_column("Project")
    table.add_column("Task")
    table.add_column("Description", no_wrap=False)

    total_seconds = 0
    for activity in activities:
        description = activity.get("description", "")
        match = re.search(r'\((\d{4})-(\d{4})\)', description)
        time_str = ""
        if match:
            start, end = match.groups()
            time_str = f"{start[:2]}:{start[2:]} - {end[:2]}:{end[2:]}"
        
        project_name = activity.get('project', {}).get('name', 'N/A')
        
        hours = activity.get('hours', 0)
        total_seconds += hours * 3600
        task_name = activity.get('task', {}).get('name', 'N/A').split('|')[0].strip()
        
        # Remove the time part from the description for cleaner display
        desc_display = re.sub(r'\s*\(\d{4}-\d{4}\)$', '', description).strip()

        table.add_row(time_str, project_name, task_name, desc_display)
    
    console.print(table)

    total_hours = int(total_seconds // 3600)
    total_minutes = int((total_seconds % 3600) // 60)
    console.print(f"\n[bold]Total time booked: {total_hours:02d}:{total_minutes:02d}[/bold]")


def ask_for_project(console, assigned_projects, default_project):
    """Asks the user to select a project from a list."""

    project_prompt = Text("\n▶️ ", style="cyan", end="")
    project_prompt.append("What project did you work on?", style="bold")
    if default_project:
        default_project = assigned_projects[0]
        customer_name = default_project.get('customer', {}).get('name', 'No Customer')
        project_name = default_project['name']
        project_prompt.append(f" (empty for last used: {customer_name} / {project_name})")

    console.print(project_prompt)
    for i, p in enumerate(assigned_projects):
        customer = p.get('customer', {}).get('name', 'No Customer')
        console.print(f"  [magenta][{i+1:>2}][/magenta] {customer} / {p['name']}")
    
    while True:
        try:
            choice_input = Prompt.ask("[bold]Project number[/bold]")
            if default_project and not choice_input:
                selected_project_data = assigned_projects[0]
                customer = selected_project_data.get('customer', {}).get('name', 'No Customer')
                project_name = selected_project_data['name']
                console.print(f"  ✅ Defaulting to: [bright_magenta]{customer} / {project_name}[/bright_magenta]")
                return selected_project_data

            proj_choice = int(choice_input) - 1
            if 0 <= proj_choice < len(assigned_projects):
                return assigned_projects[proj_choice]
            else:
                console.print("  [red]Choice out of range. Try again.[/red]")
        except ValueError:
            console.print("  [red]Please enter a valid number.[/red]")

def ask_for_task(console, tasks_display, default_task):
    """Asks the user to select a task from a list."""
    task_prompt = Text("\n▶️ ", style="cyan", end="")
    task_prompt.append("What task did you work on?", style="bold")
    if default_task:
        task_prompt.append(f" (empty for '{default_task['display_name']}')")
    
    console.print(task_prompt)
    for i, t in enumerate(tasks_display):
        console.print(f"  [magenta][{i+1:>2}][/magenta] {t['display_name']}")
    
    while True:
        choice_input = Prompt.ask("[bold]Task number[/bold]")
        if default_task and not choice_input:
            console.print(f"  ✅ Defaulting to: [bright_magenta]{default_task['display_name']}[/bright_magenta]")
            return default_task
        try:
            choice = int(choice_input) - 1
            if 0 <= choice < len(tasks_display):
                return tasks_display[choice]
            else:
                console.print("  [red]Choice out of range. Try again.[/red]")
        except ValueError:
            console.print("  [red]Invalid input. Please enter a number.[/red]")

def ask_for_jira(console, tracker):
    """Handles the JIRA ticket selection workflow."""
    while True:
        jira_id_input = Prompt.ask("\n▶️ [bold]JIRA ticket?[/bold] (e.g., PROJ-123, '?' for list, empty to skip)")
        
        if not jira_id_input:
            return None, None, None
        if jira_id_input == '?':
            with console.status("[yellow]Fetching recent JIRA tickets...[/yellow]"):
                all_recent_issues = tracker.search_recent_jira_issues()
            
            if not all_recent_issues:
                console.print("  [yellow]No recent or in-progress tickets found across all instances.[/yellow]")
                continue

            console.print("  [bold]Select a recent ticket:[/bold]")
            for i, issue in enumerate(all_recent_issues):
                console.print(f"    [magenta][{i+1:>2}][/magenta] ({issue['instance_name']}) {issue['key']}: {issue['fields']['summary']}")
            
            while True:
                try:
                    choice = int(Prompt.ask("  [bold]Ticket number[/bold] (or 0 to go back)"))
                    if choice == 0:
                        break
                    if 1 <= choice <= len(all_recent_issues):
                        selected_issue_data = all_recent_issues[choice - 1]
                        jira_id = selected_issue_data['key']
                        jira_client = tracker.config['jira_instances'][selected_issue_data['instance_name']]['client']
                        return jira_client.issue(jira_id), jira_id, jira_client
                    else:
                        console.print("  [red]Choice out of range.[/red]")
                except ValueError:
                    console.print("  [red]Please enter a number.[/red]")
            
            if 'jira_id' not in locals():
                continue

        try:
            with console.status(f"[yellow]Verifying {jira_id_input.upper()}...[/yellow]"):
                verified_data = tracker.verify_jira_ticket(jira_id_input)
        except SynkError as e:
            console.print(f"  ❌ [red]{e}[/red]")
            continue

        if verified_data:
            jira_issue, jira_id, jira_client, summary = verified_data
            console.print(f"  ✅ [green]Found:[/green] {summary}")
            
            if Confirm.ask("Is this the correct ticket?", default=True):
                return jira_issue, jira_id, jira_client
            else:
                console.print("  [yellow]Please enter the ticket ID again.[/yellow]")
                continue
        else:
            console.print(f"  ❌ [red]JIRA ticket '{jira_id_input.upper()}' not found.[/red]")

def ask_for_comment(console):
    return Prompt.ask("\n▶️ [bold]Anything to add (comment)?[/bold]")
    
def ask_for_time(console, tracker, last_activity, project: dict = None):
    """Handles the time input workflow."""
    last_end_time = tracker.get_start_time_suggestion(last_activity)
    
    start_prompt = Text("\n▶️ ", style="cyan", end="")
    start_prompt.append("When did you start?", style="bold")
    if last_end_time: start_prompt.append(f" ('last' for {last_end_time})")
    
    while True:
        start_time_input = Prompt.ask(start_prompt)
        if start_time_input.lower() == 'last' and last_end_time:
            start_time_str = last_end_time
            break
        if start_time_input.lower() == 'last' and not last_end_time:
            console.print(f"  [yellow]No previous entries to start after.[/yellow]")
        
        parsed_time = parse_and_validate_time_input(start_time_input)
        if parsed_time:
            start_time_str = parsed_time
            break
        else:
            console.print("  [red]Invalid format. Use (h)hmm (e.g., 800 or 1730) or 'last'.[/red]")

    end_prompt = Text("▶️ ", style="cyan", end="")
    end_prompt.append(f"When did you finish? (start: {start_time_str})", style="bold")
    end_prompt.append(" ((h)hmm or decimal hours)")
    
    while True:
        end_input = Prompt.ask(end_prompt)        
        try:
            end_time_str, duration_hours = tracker.calculate_duration(start_time_str, end_input, project=project)
            break
        except ValueError as e:
            console.print(f"  [red]{e}[/red]")
    
    return start_time_str, end_time_str, duration_hours

# --- SETUP AND VERIFICATION ---
def setup_clients(console):
    """Load environment variables, verify credentials, and initialize API clients."""
    load_dotenv()
    config = {
        "moco_subdomain": os.getenv("MOCO_SUBDOMAIN"),
        "moco_api_key": os.getenv("MOCO_API_KEY"),
        "question_order": os.getenv("QUESTION_ORDER", "project,task,jira,comment,time").split(','),
        "default_task_name": os.getenv("DEFAULT_TASK_NAME"),
        "task_filter_regex": os.getenv("TASK_FILTER_REGEX"),
        "jira_instances": {},
    }

    if not all([config["moco_subdomain"], config["moco_api_key"]]):
        raise SynkError("Moco configuration is missing in your .env file. Please run install.py again.")

    with console.status("[yellow]Connecting to services...[/yellow]"):
        try:
            auth_header = {'Authorization': f'Bearer {config["moco_api_key"]}'}
            session_url = f"https://{config['moco_subdomain']}.mocoapp.com/api/v1/session"
            response = requests.get(session_url, headers=auth_header)
            response.raise_for_status()
            config["moco_user_id"] = response.json()['id']
            console.print("✅ [green]Moco connection successful.[/green]")
        except (requests.exceptions.RequestException, KeyError) as e:
            raise SynkError(f"Moco connection failed: {e}") from e

        # Parse duration rules
        try:
            min_dur = os.getenv("MIN_DURATION_MINUTES")
            config["min_duration_minutes"] = int(min_dur) if min_dur else None
        except (ValueError, TypeError):
            console.print("[yellow]Warning: MIN_DURATION_MINUTES is not a valid number. Ignoring.[/yellow]")
            config["min_duration_minutes"] = None
        
        try:
            max_dur = os.getenv("MAX_DURATION_MINUTES")
            config["max_duration_minutes"] = int(max_dur) if max_dur else None
        except (ValueError, TypeError):
            console.print("[yellow]Warning: MAX_DURATION_MINUTES is not a valid number. Ignoring.[/yellow]")
            config["max_duration_minutes"] = None

        rules_str = os.getenv("PROJECT_DURATION_RULES")
        try:
            config["project_duration_rules"] = json.loads(rules_str) if rules_str else {}
        except json.JSONDecodeError:
            raise SynkError("Invalid format for PROJECT_DURATION_RULES in .env. It must be valid JSON.")

        jira_instance_names = [name.strip() for name in os.getenv("JIRA_INSTANCES", "").split(',') if name.strip()]
        if not jira_instance_names:
            console.print("[yellow]No JIRA instances configured. JIRA features will be disabled.[/yellow]")
        
        for name in jira_instance_names:
            key_prefix = f"JIRA_{name.upper()}_"
            server = os.getenv(f"{key_prefix}SERVER")
            email = os.getenv(f"{key_prefix}USER_EMAIL")
            token = os.getenv(f"{key_prefix}API_TOKEN")
            keys = [key.strip().upper() for key in os.getenv(f"{key_prefix}PROJECT_KEYS", "").split(',')]

            if not all([server, email, token, keys]):
                raise SynkError(f"Missing configuration for JIRA instance '{name}'. Check your .env file.")
            
            try:
                client = JIRA(server=server, basic_auth=(email, token))
                client.myself()
                config["jira_instances"][name] = {
                    "name": name,
                    "server": server,
                    "auth": HTTPBasicAuth(email, token),
                    "client": client,
                    "keys": keys
                }
                console.print(f"✅ [green]JIRA connection successful for '{name}'.[/green]")
            except JIRAError as e:
                raise SynkError(f"JIRA connection failed for '{name}': {e.text}") from e
            
    config["moco_session"] = requests.Session()
    config["moco_session"].headers.update({'Authorization': f'Bearer {config["moco_api_key"]}', 'Content-Type': 'application/json'})

    return config

def main_loop(console: Console):
    """The main application logic, wrapped to handle exceptions gracefully."""
    console.print(Panel.fit("🚀 [bold blue]Synk Time Tracking Tool[/bold blue] 🚀"))
    config = setup_clients(console)
    tracker = TimeTracker(config)

    while True:
        date_input = Prompt.ask("▶️ Enter date ([bold]YYYY-MM-DD[/bold]), or leave empty for today")
        if not date_input:
            work_date = date.today()
            break
        try:
            work_date = date.fromisoformat(date_input)
            break
        except ValueError:
            console.print("  [red]Invalid date format. Please try again.[/red]")

    console.print(f"\n[bold]🗓️  Entries for {work_date.strftime('%A, %Y-%m-%d')}:[/bold]")
    with console.status("[yellow]Fetching existing entries...[/yellow]"):
        daily_entries = tracker.get_daily_entries(work_date)
    display_daily_entries(console, daily_entries)

    last_activity = tracker.get_last_activity(work_date)

    while True:
        entry_data = {}
        
        with console.status("[yellow]Fetching projects...[/yellow]"):
            assigned_projects, default_project = tracker.get_project_choices(last_activity)

        if not assigned_projects:
            console.print("\n[bold red]❌ No assigned projects with active tasks were found.[/bold red]")
            break

        for step in config["question_order"]:
            if step == "project":
                entry_data["selected_project"] = ask_for_project(console, assigned_projects, default_project)
            elif step == "task":
                if "selected_project" not in entry_data: console.print("[red]Error: Project must be selected before task.[/red]"); break
                tasks, default_task = tracker.get_task_choices(entry_data["selected_project"])
                entry_data["selected_task"] = ask_for_task(console, tasks, default_task)
            elif step == "jira":
                if config["jira_instances"]:
                    entry_data["jira_issue"], entry_data["jira_id"], entry_data["jira_client"] = ask_for_jira(console, tracker)
                else: # Skip if no JIRA instances are configured
                    entry_data["jira_issue"], entry_data["jira_id"], entry_data["jira_client"] = None, None, None
            elif step == "comment":
                entry_data["comment"] = ask_for_comment(console)
            elif step == "time":
                selected_project = entry_data.get("selected_project")
                start_time, end_time, duration = ask_for_time(console, tracker, last_activity, project=selected_project)
                entry_data.update({"start_time": start_time, "end_time": end_time, "duration_hours": duration})
        
        # Re-validate duration. If the order was time,project,..., this ensures the project-specific
        # rules are checked. If validation fails, it prompts the user to re-enter the time.
        while True:
            try:
                tracker.validate_duration_rules(
                    duration_hours=entry_data.get('duration_hours', 0),
                    project=entry_data.get('selected_project')
                )
                break  # Validation passed, continue to summary
            except (ValueError, KeyError) as e:
                console.print(f"\n[bold red]❌ Validation Error:[/bold red] {e}")
                console.print("[yellow]The entered time violates a duration rule for the selected project. Please correct the time.[/yellow]")
                
                # Re-ask for time, preserving other data
                selected_project = entry_data.get("selected_project")
                start_time, end_time, duration = ask_for_time(console, tracker, last_activity, project=selected_project)
                entry_data.update({"start_time": start_time, "end_time": end_time, "duration_hours": duration})

        start_time_hhmm = entry_data.get('start_time', 'N/A').replace(':', '')
        end_time_hhmm = entry_data.get('end_time', 'N/A').replace(':', '')
        time_part = f"({start_time_hhmm}-{end_time_hhmm})"
        desc_parts = [part for part in [entry_data.get('jira_id'), entry_data.get('comment'), time_part] if part]
        description = " ".join(desc_parts)

        summary_text = Text()
        summary_text.append(f"Project:    {entry_data['selected_project'].get('customer',{}).get('name', 'N/A')} / {entry_data['selected_project']['name']}\n", style="white")
        summary_text.append(f"Task:       {entry_data['selected_task']['display_name']}\n", style="white")
        if entry_data.get('jira_id'): summary_text.append(f"JIRA Ticket: {entry_data['jira_id']}\n", style="white")
        summary_text.append(f"Time:       {entry_data.get('start_time', 'N/A')} - {entry_data.get('end_time', 'N/A')} ({entry_data.get('duration_hours', 0):.2f} hours)\n", style="yellow")
        summary_text.append(f"Description: {description}", style="white")
        
        console.print(Panel(summary_text, title="[bold blue]Summary[/bold blue]", border_style="blue", expand=False))

        if Confirm.ask("\n[bold]💾 Save this entry?[/bold]", default=True):
            with console.status("[yellow]Saving...[/yellow]"):
                tracker.save_entry(work_date, entry_data)
                console.print("✅ [green]Entry saved to Moco.[/green]")
                if entry_data.get("jira_id"):
                    console.print("✅ [green]Worklog added to JIRA.[/green]")
        else:
            console.print(" Canceled.")

        last_activity = tracker.get_last_activity(work_date)

        if not Confirm.ask("\n[bold]➕ Add another entry for this date?[/bold]", default=True):
            console.print(f"\n[bold]🗓️  Final entries for {work_date.strftime('%A, %Y-%m-%d')}:[/bold]")
            with console.status("[yellow]Fetching updated entries...[/yellow]"):
                daily_entries = tracker.get_daily_entries(work_date)
            display_daily_entries(console, daily_entries)
            break
            
    console.print("\n[bold blue]Time tracking finished. Goodbye! 👋[/bold blue]")

# --- MAIN WORKFLOW ---
def main():
    """Initializes the console and runs the main application."""
    console = Console()
    try:
        main_loop(console)
    except SynkError as e:
        console.print(f"\n[bold red]❌ An unrecoverable error occurred:[/bold red]\n{e}")
        sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        console.print("\n\n[bold yellow]Operation cancelled by user. Goodbye! 👋[/bold yellow]")
        sys.exit(0)

if __name__ == "__main__":
    main()
