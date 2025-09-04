import os
import re
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any, Tuple

import requests
from requests.auth import HTTPBasicAuth
from jira import JIRA, JIRAError

# --- CUSTOM EXCEPTION ---
class SynkError(Exception):
    """Custom exception for application-specific errors to allow for graceful exit."""
    pass

# --- API HELPER FUNCTIONS ---
def moco_get(session, moco_subdomain, endpoint, params=None):
    """Generic GET request handler for Moco API."""
    url = f"https://{moco_subdomain}.mocoapp.com/api/v1/{endpoint}"
    try:
        response = session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise SynkError(f"Moco API Error on GET {endpoint}: {e}") from e

def moco_post(session, moco_subdomain, endpoint, data):
    """Generic POST request handler for Moco API."""
    url = f"https://{moco_subdomain}.mocoapp.com/api/v1/{endpoint}"
    try:
        response = session.post(url, json=data)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        error_text = e.response.text if e.response else str(e)
        raise SynkError(f"Moco API Error creating entry: {error_text}") from e

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
        # This is a non-fatal error during an interactive search, so just printing is fine.
        # In a real UI, this would be a warning. In tests, we can check for it.
        print(f"[bold yellow]⚠️ JIRA Search Warning:[/bold yellow] {e}")
        return []

def parse_and_validate_time_input(time_str: str) -> Optional[str]:
    """
    Parses and validates a time string in (h)hmm format.
    Returns a "HH:mm" string if valid, otherwise None.
    """
    if not time_str.isdigit() or not 3 <= len(time_str) <= 4:
        return None

    time_str = time_str.zfill(4)  # Pad with leading zero if needed, e.g., "800" -> "0800"

    try:
        hour, minute = int(time_str[:2]), int(time_str[2:])
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
    except ValueError:
        return None
    return None


class TimeTracker:
    """Encapsulates the business logic for time tracking."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.moco_session = config["moco_session"]
        self.moco_subdomain = config["moco_subdomain"]
        self.moco_user_id = config["moco_user_id"]

    def get_last_activity(self, for_date: date) -> Optional[Dict[str, Any]]:
        """Fetch the entire object of the last recorded entry for the user on a specific date."""
        params = {'user_id': self.moco_user_id, 'from': for_date.isoformat(), 'to': for_date.isoformat()}
        activities = moco_get(self.moco_session, self.moco_subdomain, "activities", params=params)
        if not activities:
            return None

        activities.sort(key=lambda x: x.get('id', 0), reverse=True)
        return activities[0]

    def get_daily_entries(self, work_date: date) -> List[Dict[str, Any]]:
        """Fetches and sorts all entries for a given date."""
        params = {'user_id': self.moco_user_id, 'from': work_date.isoformat(), 'to': work_date.isoformat()}
        activities = moco_get(self.moco_session, self.moco_subdomain, "activities", params=params)

        def get_sort_key(activity: dict) -> tuple:
            """Sort key for activities: time-based entries first, then others by ID."""
            description = activity.get("description", "")
            match = re.search(r'\((\d{4})-(\d{4})\)', description)
            if match:
                start_time_hhmm = match.group(1)
                return (0, f"{start_time_hhmm[:2]}:{start_time_hhmm[2:]}")
            return (1, activity.get('id'))

        activities.sort(key=get_sort_key)
        return activities

    def get_project_choices(self, last_activity: Optional[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Fetches and prepares the list of projects for user selection.
        Projects are sorted by customer, then by recent usage, and finally by name.
        """
        # Fetch recent activities to determine project usage frequency
        from_date = date.today() - timedelta(days=28)  # 4 weeks back
        to_date = date.today()
        params = {'user_id': self.moco_user_id, 'from': from_date.isoformat(), 'to': to_date.isoformat()}
        recent_activities = moco_get(self.moco_session, self.moco_subdomain, "activities", params=params)

        project_usage_counts = {}
        for activity in recent_activities:
            project_id = activity.get('project', {}).get('id')
            if project_id:
                project_usage_counts[project_id] = project_usage_counts.get(project_id, 0) + 1

        # Fetch and filter assigned projects
        all_assigned_projects = moco_get(self.moco_session, self.moco_subdomain, "projects/assigned")
        assigned_projects = [p for p in all_assigned_projects if p.get('active', False) and any(t.get('active', False) for t in p.get('tasks', []))]
        for p in assigned_projects:
            p['tasks'] = [t for t in p.get('tasks', []) if t.get('active', False)]

        # Sort by customer, then by usage (desc), then by project name (asc)
        assigned_projects.sort(key=lambda p: (p.get('customer', {}).get('name', '').lower(), -project_usage_counts.get(p['id'], 0), p.get('name', '').lower()))

        default_project = None
        if last_activity:
            last_project_id = last_activity.get('project', {}).get('id')
            project_to_move = next((p for p in assigned_projects if p['id'] == last_project_id), None)
            if project_to_move:
                assigned_projects.remove(project_to_move)
                assigned_projects.insert(0, project_to_move)
                default_project = project_to_move

        return assigned_projects, default_project

    def get_task_choices(self, selected_project_data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Filters and prepares the list of tasks for a project."""
        tasks_original = selected_project_data.get('tasks', [])
        task_filter_regex = self.config.get("task_filter_regex")

        if task_filter_regex:
            try:
                tasks_original = [
                    t for t in tasks_original
                    if not re.search(task_filter_regex, t.get('name', ''))
                ]
            except re.error as e:
                raise SynkError(f"Invalid TASK_FILTER_REGEX in .env file: {e}")

        tasks_display = []
        for t in tasks_original:
            task_item = t.copy()
            base_name = t.get('name', '').split('|')[0].strip()
            task_item['display_name'] = base_name if t.get('billable', True) else f" ({base_name})"
            tasks_display.append(task_item)

        tasks_display.sort(key=lambda t: (not t.get('billable', True), t['display_name'].lower()))

        default_task_name = self.config.get("default_task_name")
        default_task = next((t for t in tasks_display if default_task_name and re.search(default_task_name, t.get('name', ''))), None)

        return tasks_display, default_task

    def verify_jira_ticket(self, jira_id_input: str) -> Optional[Tuple[Any, str, JIRA]]:
        """Verifies a JIRA ticket ID and returns the issue object and client."""
        ticket_prefix = jira_id_input.split('-')[0].upper()
        target_instance = None
        for name, jira_config in self.config["jira_instances"].items():
            if ticket_prefix in jira_config['keys']:
                target_instance = jira_config
                break

        if not target_instance:
            raise SynkError(f"No JIRA instance configured for project key '{ticket_prefix}'. Check your .env file.")

        search_results = search_jira_issues(f'key = "{jira_id_input.upper()}"', target_instance['server'], target_instance['auth'], max_results=1)

        if search_results:
            jira_issue_data = search_results[0]
            jira_id = jira_issue_data['key']
            jira_client = target_instance['client']
            return jira_client.issue(jira_id), jira_id, jira_client, jira_issue_data['fields']['summary']

        return None

    def search_recent_jira_issues(self) -> List[Dict[str, Any]]:
        """Searches for recent JIRA issues across all configured instances."""
        all_recent_issues = []
        for name, jira_config in self.config["jira_instances"].items():
            jql_query = 'assignee = currentUser() AND (status = "In Progress" OR updated >= -14d) ORDER BY updated DESC'
            issues = search_jira_issues(jql_query, jira_config['server'], jira_config['auth'], max_results=5)
            for issue in issues:
                issue['instance_name'] = name
            all_recent_issues.extend(issues)
        return all_recent_issues

    def get_start_time_suggestion(self, last_activity: Optional[Dict[str, Any]]) -> Optional[str]:
        """Determines the suggested start time based on the last activity."""
        if last_activity:
            match = re.search(r'\((\d{4})-(\d{4})\)', last_activity.get("description", ""))
            if match:
                end_time_hhmm = match.group(2)
                return f"{end_time_hhmm[:2]}:{end_time_hhmm[2:]}"
        return None

    def calculate_duration(self, start_time_str: str, end_input: str, project: Optional[Dict[str, Any]] = None) -> Tuple[str, float]:
        """Calculates duration and end time from user input, applying rounding if configured."""
        start_time_dt = datetime.strptime(start_time_str, "%H:%M")

        parsed_end_time = parse_and_validate_time_input(end_input)

        if parsed_end_time:
            end_time_dt = datetime.strptime(parsed_end_time, "%H:%M")
            if end_time_dt <= start_time_dt:
                raise ValueError("End time must be after start time.")
            duration_hours = (end_time_dt - start_time_dt).total_seconds() / 3600
        else:
            try:
                duration_hours = float(end_input)
                if duration_hours <= 0:
                    raise ValueError("Duration must be positive.")
            except ValueError:
                raise ValueError("Invalid format. Use (h)hmm or a decimal number (e.g., 1.5).")

        # --- Rounding Logic ---
        rounding_increment = self.config.get("duration_rounding_increment")
        if rounding_increment and rounding_increment > 0:
            original_duration = duration_hours
            duration_hours = round(duration_hours / rounding_increment) * rounding_increment
            # If rounding to 0, but original duration was positive, round up to the smallest increment.
            if duration_hours == 0 and original_duration > 0:
                duration_hours = rounding_increment

        # Recalculate end time based on final (potentially rounded) duration
        end_time_dt = start_time_dt + timedelta(hours=duration_hours)
        end_time_str = end_time_dt.strftime("%H:%M")

        # --- Duration Validation ---
        self.validate_duration_rules(duration_hours, project)

        return end_time_str, duration_hours

    def validate_duration_rules(self, duration_hours: float, project: Optional[Dict[str, Any]]):
        """
        Validates a given duration in hours against global and project-specific rules.
        Raises ValueError if a rule is violated.
        """
        min_duration_minutes = self.config.get("min_duration_minutes")
        max_duration_minutes = self.config.get("max_duration_minutes")

        if project and self.config.get("project_duration_rules"):
            customer_name = project.get('customer', {}).get('name', 'No Customer')
            project_name = project['name']
            # The key must match the display format in `ask_for_project`
            project_key = f"{customer_name} / {project_name}"

            project_rules = self.config["project_duration_rules"].get(project_key)
            if project_rules:
                # Project rules override global rules if they exist
                min_duration_minutes = project_rules.get("min", min_duration_minutes)
                max_duration_minutes = project_rules.get("max", max_duration_minutes)

        duration_minutes = duration_hours * 60

        if min_duration_minutes is not None and duration_minutes < min_duration_minutes:
            raise ValueError(f"Duration must be at least {min_duration_minutes} minutes.")

        if max_duration_minutes is not None and duration_minutes > max_duration_minutes:
            raise ValueError(f"Duration must not exceed {max_duration_minutes} minutes ({max_duration_minutes/60:.1f} hours).")

    def save_entry(self, work_date: date, entry_data: Dict[str, Any]):
        """Saves the time entry to Moco and JIRA."""
        start_time_hhmm = entry_data.get('start_time', 'N/A').replace(':', '')
        end_time_hhmm = entry_data.get('end_time', 'N/A').replace(':', '')
        time_part = f"({start_time_hhmm}-{end_time_hhmm})"
        desc_parts = [part for part in [entry_data.get('jira_id'), entry_data.get('comment'), time_part] if part]
        description = " ".join(desc_parts)

        # Save to Moco
        moco_payload = {
            "date": work_date.isoformat(),
            "project_id": entry_data["selected_project"]['id'],
            "task_id": entry_data["selected_task"]['id'],
            "hours": round(entry_data["duration_hours"], 4),
            "description": description
        }
        moco_post(self.moco_session, self.moco_subdomain, "activities", data=moco_payload)

        # Save to JIRA
        if entry_data.get("jira_issue"):
            try:
                jira_comment = f"{entry_data.get('comment', '')} {time_part}".strip()
                start_dt = datetime.strptime(entry_data['start_time'], "%H:%M")
                jira_client = entry_data["jira_client"]
                jira_client.add_worklog(
                    issue=entry_data["jira_issue"],
                    timeSpentSeconds=int(entry_data["duration_hours"] * 3600),
                    comment=jira_comment,
                    started=datetime.combine(work_date, start_dt.time()).astimezone()
                )
            except JIRAError as e:
                # Re-raise as a SynkError to be caught by the main loop
                raise SynkError(f"Failed to add JIRA worklog: {e.text}") from e