import pytest
from unittest.mock import MagicMock, patch
from datetime import date

from logic import TimeTracker, parse_and_validate_time_input, SynkError

@pytest.fixture
def mock_config():
    """Provides a mock configuration dictionary for tests."""
    return {
        "moco_session": MagicMock(),
        "moco_subdomain": "test-domain",
        "moco_user_id": 123,
        "default_task_name": "^CH: Main",
        "task_filter_regex": "^MK:",
        "jira_instances": {},
        "min_duration_minutes": None,
        "max_duration_minutes": None,
        "project_duration_rules": {}
    }

@pytest.fixture
def tracker(mock_config):
    """Provides a TimeTracker instance with a mock config."""
    return TimeTracker(mock_config)


def test_get_task_choices_filtering_and_sorting(tracker):
    """
    Tests that tasks are correctly filtered and sorted.
    - Filters out tasks matching `task_filter_regex`.
    - Sorts billable tasks before non-billable ones.
    - Sorts tasks alphabetically within billable/non-billable groups.
    - Correctly identifies the default task.
    """
    mock_project_data = {
        "tasks": [
            {"name": "ZZ: Last Task", "billable": True},
            {"name": "MK: Marketing Task", "billable": True}, # Should be filtered out
            {"name": "CH: Main", "billable": True},
            {"name": "AA: First Task", "billable": True},
            {"name": "NB: Non-billable", "billable": False},
        ]
    }

    tasks, default_task = tracker.get_task_choices(mock_project_data)

    # Check filtering
    assert len(tasks) == 4
    assert not any("MK:" in t['name'] for t in tasks)

    # Check sorting and display name creation
    assert tasks[0]['display_name'] == "AA: First Task"
    assert tasks[1]['display_name'] == "CH: Main"
    assert tasks[2]['display_name'] == "ZZ: Last Task"
    assert tasks[3]['display_name'] == " (NB: Non-billable)" # Non-billable sorted last

    # Check default task identification
    assert default_task is not None
    assert default_task['name'] == "CH: Main"


@pytest.mark.parametrize("time_input, expected_output", [
    ("800", "08:00"),
    ("1730", "17:30"),
    ("0915", "09:15"),
    ("915", "09:15"),
    ("2400", None), # Invalid hour
    ("1260", None), # Invalid minute
    ("8", None),    # Too short
    ("12345", None),# Too long
    ("abcd", None), # Not a digit
])
def test_parse_and_validate_time_input(time_input, expected_output):
    """Tests the time parsing and validation utility function."""
    assert parse_and_validate_time_input(time_input) == expected_output


def test_calculate_duration_from_end_time(tracker):
    """Tests duration calculation when an end time is provided."""
    end_time, duration = tracker.calculate_duration("09:00", "1030")
    assert end_time == "10:30"
    assert duration == 1.5

def test_calculate_duration_from_float(tracker):
    """Tests duration calculation when a float duration is provided."""
    end_time, duration = tracker.calculate_duration("10:00", "0.75")
    assert end_time == "10:45"
    assert duration == 0.75

def test_calculate_duration_invalid_end_time(tracker):
    """Tests that an error is raised for an end time before the start time."""
    with pytest.raises(ValueError, match="End time must be after start time."):
        tracker.calculate_duration("10:00", "0900")

def test_calculate_duration_invalid_input(tracker):
    """Tests that an error is raised for invalid duration input."""
    with pytest.raises(ValueError, match="Invalid format"):
        tracker.calculate_duration("10:00", "abc")

def test_calculate_duration_min_limit(tracker):
    """Tests that duration below the minimum raises an error."""
    tracker.config["min_duration_minutes"] = 15
    with pytest.raises(ValueError, match="Duration must be at least 15 minutes."):
        # 0.2 hours = 12 minutes
        tracker.calculate_duration("10:00", "0.2")

def test_calculate_duration_max_limit(tracker):
    """Tests that duration above the maximum raises an error."""
    tracker.config["max_duration_minutes"] = 60
    with pytest.raises(ValueError, match=r"Duration must not exceed 60 minutes \(1.0 hours\)\."):
        tracker.calculate_duration("10:00", "1.5") # 90 minutes

def test_calculate_duration_project_override(tracker):
    """Tests that project-specific rules override global rules."""
    tracker.config["min_duration_minutes"] = 15
    tracker.config["project_duration_rules"] = {
        "Test Customer / Test Project": {"min": 30}
    }
    project = {
        "name": "Test Project",
        "customer": {"name": "Test Customer"}
    }
    
    # This is ~20 minutes, which is > global min (15) but < project min (30)
    with pytest.raises(ValueError, match="Duration must be at least 30 minutes."):
        tracker.calculate_duration("09:00", "0.3333", project=project)

    # This should pass as it's over 30 mins (~36 mins)
    end_time, duration = tracker.calculate_duration("09:00", "0.6", project=project)
    assert duration == 0.6

def test_calculate_duration_within_limits(tracker):
    """Tests that a valid duration passes without raising an error."""
    tracker.config["min_duration_minutes"] = 10
    tracker.config["max_duration_minutes"] = 120
    end_time, duration = tracker.calculate_duration("10:00", "1.0")
    assert duration == 1.0

@patch('logic.moco_get')
def test_get_last_activity_returns_none_when_no_activities(mock_moco_get, tracker):
    """Tests that get_last_activity handles cases with no entries."""
    mock_moco_get.return_value = []
    result = tracker.get_last_activity(date(2023, 1, 1))
    assert result is None
    mock_moco_get.assert_called_once()