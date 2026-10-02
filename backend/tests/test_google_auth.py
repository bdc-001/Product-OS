import json

from app.services import google_auth
from app.services.marketing import drive_destination, drive_root

KEY = {"type": "service_account", "client_email": "bot@proj.iam.gserviceaccount.com", "private_key": "x", "token_uri": "https://oauth2.googleapis.com/token"}


def test_connection_json_wins_over_key_file(workspace_context, tmp_path):
    other = tmp_path / "key.json"
    other.write_text(json.dumps({**KEY, "client_email": "file@proj.iam.gserviceaccount.com"}))
    workspace_context.values.update(gdrive_key_json=json.dumps(KEY), gdrive_key_file=str(other))
    assert google_auth.google_configured()
    assert google_auth.service_email() == KEY["client_email"]


def test_key_file_is_the_local_fallback(workspace_context, tmp_path):
    key = tmp_path / "key.json"
    key.write_text(json.dumps(KEY))
    workspace_context.values.update(gdrive_key_json="", gdrive_key_file=str(key))
    assert google_auth.google_configured()
    assert google_auth.service_email() == KEY["client_email"]


def test_unconfigured_workspace_reports_not_connected(workspace_context):
    workspace_context.values.update(gdrive_key_json="", gdrive_key_file="", marketing_drive_root="", gdrive_folder_id="", gdrive_assets_folder_id="")
    assert not google_auth.google_configured()
    assert drive_root() == ""
    assert drive_destination() == {"configured": False, "url": "", "folder_id": ""}


def test_drive_root_comes_from_the_google_connection(workspace_context):
    workspace_context.values.update(gdrive_key_json=json.dumps(KEY), marketing_drive_root="root-folder", gdrive_folder_id="artifacts")
    assert drive_root() == "root-folder"
    assert drive_destination()["configured"] is True
