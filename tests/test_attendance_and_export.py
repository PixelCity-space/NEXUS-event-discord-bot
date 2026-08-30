import io
import csv
import discord
from services.attendance_service import calculate_attendance_stats
from services.export_service import generate_events_csv, generate_rsvps_csv, create_csv_discord_file
from services.notification_service import normalize_rsvps

def test_calculate_attendance_stats_empty():
    """Test attendance calculation with zero participants."""
    attended, no_shows, rate = calculate_attendance_stats([])
    assert attended == 0
    assert no_shows == 0
    assert rate == 0.0

def test_calculate_attendance_stats_mixed():
    """Test attendance rate calculation with attended and no-show users."""
    participants = [
        {"user_id": 1, "attendance": "present"},
        {"user_id": 2, "attendance": "present"},
        {"user_id": 3, "attendance": "present"},
        {"user_id": 4, "attendance": "no_show"},
    ]
    attended, no_shows, rate = calculate_attendance_stats(participants)
    assert attended == 3
    assert no_shows == 1
    assert rate == 75.0

def test_generate_events_csv():
    """Test converting event dictionaries to valid CSV formatted output."""
    events = [
        {
            "event_id": "EVT-101",
            "title": "Guild Raid",
            "creator_id": "123456",
            "start_time": 1780000000,
            "status": "active",
            "config_name": "mmo",
            "total_rsvps": 10,
            "no_shows": 1,
        }
    ]
    csv_str = generate_events_csv(events)
    reader = list(csv.reader(io.StringIO(csv_str)))
    assert len(reader) == 2 # Header + 1 row
    assert reader[0] == ["Event ID", "Title", "Creator ID", "Start Time", "Status", "Template", "Total RSVPs", "No-shows"]
    assert reader[1][0] == "EVT-101"
    assert reader[1][1] == "Guild Raid"
    assert reader[1][6] == "10"

def test_generate_rsvps_csv():
    """Test converting RSVP records into CSV data."""
    rsvps = [
        {
            "event_title": "Game Night",
            "user_id": "999888777",
            "status": "accepted",
            "joined_at": 1780000000,
            "attendance": "present",
        }
    ]
    csv_str = generate_rsvps_csv(rsvps)
    reader = list(csv.reader(io.StringIO(csv_str)))
    assert len(reader) == 2
    assert reader[0] == ["Event Title", "User ID", "Status", "Joined At", "Attendance"]
    assert reader[1][0] == "Game Night"
    assert reader[1][1] == "999888777"
    assert reader[1][2] == "accepted"

def test_normalize_rsvps():
    """Test normalizer function converting various tuple/dict structures into standard dict format."""
    raw_data = [
        {"user_id": 101, "status": "tank"},
        (102, "heal"),
        [103, "dps"],
    ]
    normalized = normalize_rsvps(raw_data)
    assert len(normalized) == 3
    assert normalized[0] == {"user_id": 101, "status": "tank"}
    assert normalized[1] == {"user_id": 102, "status": "heal"}
    assert normalized[2] == {"user_id": 103, "status": "dps"}

def test_create_csv_discord_file():
    """Test wrapping CSV data into a Discord File attachment."""
    csv_content = "col1,col2\nval1,val2\n"
    d_file = create_csv_discord_file(csv_content, "test_export.csv")
    assert isinstance(d_file, discord.File)
    assert d_file.filename == "test_export.csv"
