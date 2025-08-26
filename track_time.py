# --- IMPORTS ---
import os
import re
import sys
from datetime import datetime, timedelta, date

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

# --- API HELPER FUNCTIONS ---
def moco_get(session, moco_subdomain, endpoint, params=None):
    """Generic GET request handler for Moco API."""
    url = f"https://{moco_subdomain}.mocoapp.com/api/v1/{endpoint}"
    try:
        response = session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        Console().print(f"[bold red]❌ Moco API Error:[/bold red] {e}")
        sys.exit(1)

def moco_post(session, moco_subdomain, endpoint, data):
    """Generic POST request handler for Moco API."""
    url = f"https://{moco_subdomain}.mocoapp.com/api/v1/{endpoint}"
    try:
        response = session.post(url, json=data)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        Console().print(f"[bold red]❌ Moco API Error creating entry:[/bold red] {e.response.text if e.response else e}")
        sys.exit(1)

def get_last_activity(session, moco_subdomain, user_id, for_date):
    """Fetch the entire object of the last recorded entry for the user on a specific date."""
    params = {'user_id': user_id, 'from': for_date.isoformat(), 'to': for_date.isoformat()}
    activities = moco_get(session, moco_subdomain, "activities", params=params)
    if not activities:
        return None
    
    activities.sort(key=lambda x: x.get('id', 0), reverse=True)
    return activities[0]

def search_jira_issues(jql, jira_server, auth, max_results=5):
    """Searches for JIRA issues using the REST API."""
    url = f"{jira_server}/rest/api/3/search/jql"
    headers = {"Accept": "application/json"}
    query = {'jql': jql, 'maxResults': max_results, 'fields': 'summary'}
    
    try:
        response = requests.get(url, headers=headers, params=query, auth=auth)
        response.raise_for_status()
        return response.json().get('issues', [])
    except requests.exceptions.RequestException as e:
        Console().print(f"[bold red]❌ JIRA Search Error:[/bold red] {e}")
        return []

def parse_and_validate_time_input(time_str):
    """
    Parses and validates a time string in (h)hmm format.
    Returns a "HH:mm" string if valid, otherwise None.
    """
    if not re.fullmatch(r"\d{3,4}", time_str):
        return None

    if len(time_str) == 3:
        time_str = "0" + time_str

    hour_str, minute_str = time_str[:2], time_str[2:]
    try:
        hour, minute = int(hour_str), int(minute_str)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
    except ValueError:
        return None
    return None

# --- WORKFLOW STEP FUNCTIONS ---
def display_daily_entries(console, session, moco_subdomain, user_id, work_date):
    """Fetches and displays all entries for a given date."""
    console.print(f"\n[bold]🗓️  Entries for {work_date.strftime('%A, %Y-%m-%d')}:[/bold]")
    with console.status("[yellow]Fetching existing entries...[/yellow]"):
        params = {'user_id': user_id, 'from': work_date.isoformat(), 'to': work_date.isoformat()}
        activities = moco_get(session, moco_subdomain, "activities", params=params)

    if not activities:
        console.print("  [grey53]No entries found for this date.[/grey53]")
        return

    parsed_activities = []
    for activity in activities:
        description = activity.get("description", "")
        match = re.search(r'\((\d{4})-(\d{4})\)', description)
        if match:
            start_time_hhmm = match.group(1)
            start_time_for_sort = f"{start_time_hhmm[:2]}:{start_time_hhmm[2:]}"
            parsed_activities.append({**activity, 'start_time_for_sort': start_time_for_sort})
        else:
            # Add activities without a time part to sort them at the end
            parsed_activities.append({**activity, 'start_time_for_sort': "99:99"})

    # Sort activities by the parsed start time
    parsed_activities.sort(key=lambda x: x['start_time_for_sort'])

    table = Table(show_header=True, header_style="bold magenta", border_style="dim")
    table.add_column("Time", style="cyan", width=15)
    table.add_column("Project")
    table.add_column("Task")
    table.add_column("Description", no_wrap=False)

    for activity in parsed_activities:
        description = activity.get("description", "")
        match = re.search(r'\((\d{4})-(\d{4})\)', description)
        time_str = ""
        if match:
            start, end = match.groups()
            time_str = f"{start[:2]}:{start[2:]} - {end[:2]}:{end[2:]}"
        
        project_name = activity.get('project', {}).get('name', 'N/A')
        task_name = activity.get('task', {}).get('name', 'N/A').split('|')[0].strip()
        
        # Remove the time part from the description for cleaner display
        desc_display = re.sub(r'\s*\(\d{4}-\d{4}\)$', '', description).strip()

        table.add_row(time_str, project_name, task_name, desc_display)
    
    console.print(table)


def ask_for_project(console, assigned_projects, last_activity):
    has_last_project_default = False
    if last_activity:
        last_project_id = last_activity.get('project', {}).get('id')
        project_to_move = next((p for p in assigned_projects if p['id'] == last_project_id), None)
        if project_to_move:
            assigned_projects.remove(project_to_move)
            assigned_projects.insert(0, project_to_move)
            has_last_project_default = True

    project_prompt = Text("\n▶️ ", style="cyan", end="")
    project_prompt.append("What project did you work on?", style="bold")
    if has_last_project_default:
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
            if has_last_project_default and not choice_input:
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

def ask_for_task(console, selected_project_data, default_task_name):
    tasks_original = selected_project_data.get('tasks', [])
    tasks_display = [{'display_name': t.get('name', '').split('|')[0].strip(), **t} for t in tasks_original]

    default_task = next((t for t in tasks_display if default_task_name and re.search(default_task_name, t.get('name', ''))), None)
    
    task_prompt = Text("\n▶️ ", style="cyan", end="")
    task_prompt.append("What task did you work on?", style="bold")
    if default_task: task_prompt.append(f" (empty for '{default_task['display_name']}')")
    
    console.print(task_prompt)
    for i, t in enumerate(tasks_display): console.print(f"  [magenta][{i+1:>2}][/magenta] {t['display_name']}")
    
    while True:
        choice_input = Prompt.ask("[bold]Task number[/bold]")
        if default_task and not choice_input:
            console.print(f"  ✅ Defaulting to: [bright_magenta]{default_task['display_name']}[/bright_magenta]")
            return default_task
        try:
            choice = int(choice_input) - 1
            if 0 <= choice < len(tasks_display):
                return tasks_display[choice]
            else: console.print("  [red]Choice out of range. Try again.[/red]")
        except ValueError: console.print("  [red]Invalid input. Please enter a number.[/red]")

def ask_for_jira(console, config):
    while True:
        jira_id_input = Prompt.ask("\n▶️ [bold]JIRA ticket?[/bold] (e.g., PROJ-123, '?' for list, empty to skip)")
        
        if not jira_id_input:
            return None, None, None

        if jira_id_input == '?':
            all_recent_issues = []
            with console.status("[yellow]Fetching recent JIRA tickets from all instances...[/yellow]"):
                for name, jira_config in config["jira_instances"].items():
                    jql_query = 'assignee = currentUser() AND (status = "In Progress" OR updated >= -14d) ORDER BY updated DESC'
                    issues = search_jira_issues(jql_query, jira_config['server'], jira_config['auth'], max_results=5)
                    for issue in issues:
                        issue['instance_name'] = name
                    all_recent_issues.extend(issues)
            
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
                        instance_name = selected_issue_data['instance_name']
                        jira_client = config['jira_instances'][instance_name]['client']
                        return jira_client.issue(jira_id), jira_id, jira_client
                    else:
                        console.print("  [red]Choice out of range.[/red]")
                except ValueError:
                    console.print("  [red]Please enter a number.[/red]")
            
            if 'jira_id' not in locals():
                continue

        ticket_prefix = jira_id_input.split('-')[0].upper()
        target_instance = None
        for name, jira_config in config["jira_instances"].items():
            if ticket_prefix in jira_config['keys']:
                target_instance = jira_config
                break
        
        if not target_instance:
            console.print(f"  ❌ [red]No JIRA instance configured for project key '{ticket_prefix}'. Check your .env file.[/red]")
            continue

        with console.status(f"[yellow]Verifying {jira_id_input.upper()} on '{target_instance['name']}' instance...[/yellow]"):
            search_results = search_jira_issues(f'key = "{jira_id_input.upper()}"', target_instance['server'], target_instance['auth'], max_results=1)
        
        if search_results:
            jira_issue_candidate_data = search_results[0]
            console.print(f"  ✅ [green]Found:[/green] {jira_issue_candidate_data['fields']['summary']}")
            
            if Confirm.ask("Is this the correct ticket?", default=True):
                jira_id = jira_issue_candidate_data['key']
                jira_client = target_instance['client']
                return jira_client.issue(jira_id), jira_id, jira_client
            else:
                console.print("  [yellow]Please enter the ticket ID again.[/yellow]")
                continue
        else:
            console.print(f"  ❌ [red]JIRA ticket '{jira_id_input.upper()}' not found on the '{target_instance['name']}' instance.[/red]")

def ask_for_comment(console):
    return Prompt.ask("\n▶️ [bold]Anything to add (comment)?[/bold]")

def ask_for_time(console, last_activity):
    last_end_time = None
    if last_activity:
        match = re.search(r'\((\d{4})-(\d{4})\)', last_activity.get("description", ""))
        if match:
            end_time_hhmm = match.group(2)
            last_end_time = f"{end_time_hhmm[:2]}:{end_time_hhmm[2:]}"

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
        start_time_dt = datetime.strptime(start_time_str, "%H:%M")
        
        parsed_end_time = parse_and_validate_time_input(end_input)
        if parsed_end_time:
            end_time_dt = datetime.strptime(parsed_end_time, "%H:%M")
            if end_time_dt <= start_time_dt:
                console.print("  [red]End time must be after start time.[/red]")
                continue
            duration_hours = (end_time_dt - start_time_dt).total_seconds() / 3600
            end_time_str = parsed_end_time
            break
        else:
            try:
                duration_hours = float(end_input)
                if duration_hours <= 0:
                    console.print("  [red]Duration must be positive.[/red]")
                    continue
                end_time_str = (start_time_dt + timedelta(hours=duration_hours)).strftime("%H:%M")
                break
            except ValueError:
                console.print("  [red]Invalid format. Use (h)hmm or a decimal number (e.g., 1.5).[/red]")
    
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
        "jira_instances": {}
    }

    if not all([config["moco_subdomain"], config["moco_api_key"]]):
        console.print("[bold red]❌ Error: Moco configuration is missing in your .env file.[/bold red]")
        sys.exit(1)

    with console.status("[yellow]Connecting to services...[/yellow]"):
        try:
            auth_header = {'Authorization': f'Bearer {config["moco_api_key"]}'}
            session_url = f"https://{config['moco_subdomain']}.mocoapp.com/api/v1/session"
            response = requests.get(session_url, headers=auth_header)
            response.raise_for_status()
            config["moco_user_id"] = response.json()['id']
            console.print("✅ [green]Moco connection successful.[/green]")
        except (requests.exceptions.RequestException, KeyError) as e:
            console.print(f"❌ [bold red]Moco connection failed:[/bold red] {e}")
            sys.exit(1)

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
                console.print(f"❌ [bold red]Missing configuration for JIRA instance '{name}'. Check your .env file.[/bold red]")
                sys.exit(1)
            
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
                console.print(f"❌ [bold red]JIRA connection failed for '{name}':[/bold red] {e.text}")
                sys.exit(1)
            
    config["moco_session"] = requests.Session()
    config["moco_session"].headers.update({'Authorization': f'Bearer {config["moco_api_key"]}', 'Content-Type': 'application/json'})

    return config

# --- MAIN WORKFLOW ---
def main():
    console = Console()
    console.print(Panel.fit("🚀 [bold blue]Synk Time Tracking Tool[/bold blue] 🚀"))
    
    config = setup_clients(console)

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
            
    display_daily_entries(console, config["moco_session"], config["moco_subdomain"], config["moco_user_id"], work_date)

    last_activity = get_last_activity(config["moco_session"], config["moco_subdomain"], config["moco_user_id"], work_date)

    while True:
        entry_data = {}
        
        with console.status("[yellow]Fetching projects...[/yellow]"):
            all_assigned_projects = moco_get(config["moco_session"], config["moco_subdomain"], "projects/assigned")
            assigned_projects = [p for p in all_assigned_projects if p.get('active', False) and any(t.get('active', False) for t in p.get('tasks', []))]
            for p in assigned_projects:
                p['tasks'] = [t for t in p.get('tasks', []) if t.get('active', False)]
            assigned_projects.sort(key=lambda p: (p.get('customer', {}).get('name', '').lower(), p.get('name', '').lower()))

        if not assigned_projects:
            console.print("\n[bold red]❌ No assigned projects with active tasks were found.[/bold red]")
            break

        for step in config["question_order"]:
            if step == "project":
                entry_data["selected_project"] = ask_for_project(console, assigned_projects, last_activity)
            elif step == "task":
                if "selected_project" not in entry_data: console.print("[red]Error: Project must be selected before task.[/red]"); break
                entry_data["selected_task"] = ask_for_task(console, entry_data["selected_project"], config["default_task_name"])
            elif step == "jira":
                if config["jira_instances"]:
                    entry_data["jira_issue"], entry_data["jira_id"], entry_data["jira_client"] = ask_for_jira(console, config)
                else: # Skip if no JIRA instances are configured
                    entry_data["jira_issue"], entry_data["jira_id"], entry_data["jira_client"] = None, None, None
            elif step == "comment":
                entry_data["comment"] = ask_for_comment(console)
            elif step == "time":
                start_time, end_time, duration = ask_for_time(console, last_activity)
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
                moco_payload = {
                    "date": work_date.isoformat(),
                    "project_id": entry_data["selected_project"]['id'],
                    "task_id": entry_data["selected_task"]['id'],
                    "hours": round(entry_data["duration_hours"], 4),
                    "description": description
                }
                moco_post(config["moco_session"], config["moco_subdomain"], "activities", data=moco_payload)
                console.print("✅ [green]Entry saved to Moco.[/green]")
                
                if entry_data.get("jira_issue"):
                    try:
                        jira_comment = f"{entry_data.get('comment', '')} {time_part}".strip()
                        start_dt = datetime.strptime(entry_data['start_time'], "%H:%M")
                        jira_client = entry_data["jira_client"]
                        jira_client.add_worklog(
                            issue=entry_data["jira_issue"], timeSpentSeconds=int(entry_data["duration_hours"]*3600),
                            comment=jira_comment, started=datetime.combine(work_date, start_dt.time()).astimezone()
                        )
                        console.print("✅ [green]Worklog added to JIRA.[/green]")
                    except JIRAError as e: console.print(f"❌ [red]Failed to add JIRA worklog:[/red] {e.text}")
        else:
            console.print(" Canceled.")

        last_activity = get_last_activity(config["moco_session"], config["moco_subdomain"], config["moco_user_id"], work_date)

        if not Confirm.ask("\n[bold]➕ Add another entry for this date?[/bold]"):
            display_daily_entries(console, config["moco_session"], config["moco_subdomain"], config["moco_user_id"], work_date)
            break
            
    console.print("\n[bold blue]Time tracking finished. Goodbye! 👋[/bold blue]")

if __name__ == "__main__":
    main()
