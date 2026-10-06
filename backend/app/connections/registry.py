"""Every external service a workspace can connect, its fields, and how to verify it.

A field with `setting` maps onto the matching `settings.<name>` inside the workspace, which is how
existing clients (JiraClient, CliqClient, LLMClient, ...) pick up per-workspace credentials.
"""

from __future__ import annotations

import json
import smtplib
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.clients.http import get


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    kind: str = "text"  # text | secret | url | email | number | bool | select | json | textarea
    setting: str = ""
    required: bool = False
    placeholder: str = ""
    help: str = ""
    default: Any = ""
    options: tuple[str, ...] = ()
    advanced: bool = False

    @property
    def secret(self) -> bool:
        return self.kind in {"secret", "json"} or (self.kind == "textarea" and "key" in self.key)


@dataclass
class TestResult:
    ok: bool
    message: str
    details: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Provider:
    id: str
    name: str
    category: str
    description: str
    help_url: str
    fields: tuple[Field, ...]
    test: Callable[[dict], TestResult]
    multiple: bool = False
    custom_ui: str = ""

    def field(self, key: str) -> Field | None:
        return next((f for f in self.fields if f.key == key), None)

    @property
    def secret_keys(self) -> set[str]:
        return {f.key for f in self.fields if f.secret}

    def missing(self, values: dict) -> list[str]:
        return [f.label for f in self.fields if f.required and not str(values.get(f.key) or "").strip()]


def _http_error(response) -> str:
    try:
        body = response.json()
    except Exception:
        body = {}
    if isinstance(body, dict):
        for key in ("message", "error_description", "error", "detail", "errorMessages"):
            value = body.get(key)
            if isinstance(value, list):
                value = "; ".join(str(v) for v in value)
            if isinstance(value, dict):
                value = value.get("message") or json.dumps(value)[:200]
            if value:
                return f"HTTP {response.status_code}: {value}"
    return f"HTTP {response.status_code}"


def _guard(fn: Callable[[dict], TestResult]) -> Callable[[dict], TestResult]:
    def wrapped(values: dict) -> TestResult:
        try:
            return fn(values)
        except Exception as exc:  # network errors, bad keys, malformed JSON
            return TestResult(False, str(exc)[:400] or exc.__class__.__name__)

    return wrapped


@_guard
def _test_jira(values: dict) -> TestResult:
    base = str(values.get("base_url") or "").rstrip("/")
    response = get(f"{base}/rest/api/3/myself", auth=(values.get("email") or "", values.get("api_token") or ""), timeout=20)
    if response.status_code != 200:
        return TestResult(False, _http_error(response))
    me = response.json()
    return TestResult(True, f"Signed in as {me.get('displayName') or me.get('emailAddress') or 'Jira user'}", {"account_id": me.get("accountId")})


@_guard
def _test_cliq(values: dict) -> TestResult:
    from app.clients.http import post

    accounts = str(values.get("accounts_url") or "https://accounts.zoho.in").rstrip("/")
    api = str(values.get("api_domain") or "https://cliq.zoho.in").rstrip("/")
    token = str(values.get("access_token") or "")
    refreshed = {}
    if values.get("refresh_token") and values.get("client_id") and values.get("client_secret"):
        response = post(
            f"{accounts}/oauth/v2/token",
            data={
                "grant_type": "refresh_token",
                "client_id": values["client_id"],
                "client_secret": values["client_secret"],
                "refresh_token": values["refresh_token"],
            },
            timeout=20,
        )
        data = response.json() if response.content else {}
        if not data.get("access_token"):
            return TestResult(False, f"Token refresh failed: {data.get('error') or _http_error(response)}. Reconnect Cliq.")
        token = data["access_token"]
        refreshed = {"access_token": token}
    if not token:
        return TestResult(False, "Not connected yet. Use Connect with Zoho to sign in.")
    response = get(f"{api}/api/v2/chats", params={"limit": 1}, headers={"Authorization": f"Zoho-oauthtoken {token}"}, timeout=20)
    if response.status_code != 200:
        return TestResult(False, _http_error(response))
    return TestResult(True, "Cliq chats are readable", {"refreshed": refreshed})


@_guard
def _test_llm(values: dict) -> TestResult:
    providers = values.get("providers") or {}
    keys = values.get("provider_keys") or {}
    if not providers:
        return TestResult(False, "Add at least one model provider.")
    checked: list[str] = []
    for pid, meta in providers.items():
        key = str(keys.get(pid) or "")
        if not key:
            return TestResult(False, f"{meta.get('label') or pid}: API key missing")
        protocol = str(meta.get("protocol") or "openai")
        base = str(meta.get("base_url") or "").rstrip("/")
        if protocol == "anthropic":
            url = (base or "https://api.anthropic.com/v1").rstrip("/")
            if not url.endswith("/v1"):
                url = url + "/v1"
            response = get(f"{url}/models", headers={"x-api-key": key, "anthropic-version": "2023-06-01"}, timeout=20)
        else:
            headers = {"Authorization": f"Bearer {key}"}
            if meta.get("project"):
                headers["OpenAI-Project"] = str(meta["project"])
            response = get(f"{base or 'https://api.openai.com/v1'}/models", headers=headers, timeout=20)
        if response.status_code != 200:
            return TestResult(False, f"{meta.get('label') or pid}: {_http_error(response)}")
        checked.append(str(meta.get("label") or pid))
    return TestResult(True, "Keys accepted: " + ", ".join(checked))


@_guard
def _test_google(values: dict) -> TestResult:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    info = json.loads(str(values.get("service_account_json") or "{}"))
    creds = service_account.Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/drive"])
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    about = drive.about().get(fields="user(emailAddress)").execute()
    folder = str(values.get("folder_id") or "").strip()
    if folder:
        drive.files().get(fileId=folder, fields="id,name", supportsAllDrives=True).execute()
    email = (about.get("user") or {}).get("emailAddress") or info.get("client_email") or "service account"
    return TestResult(True, f"Drive reachable as {email}", {"client_email": info.get("client_email") or email})


@_guard
def _test_smtp(values: dict) -> TestResult:
    host = str(values.get("host") or "")
    port = int(values.get("port") or 587)
    with smtplib.SMTP(host, port, timeout=15) as server:
        server.ehlo()
        if str(values.get("use_tls", True)).lower() not in {"false", "0", "no"}:
            server.starttls()
            server.ehlo()
        if values.get("user"):
            server.login(str(values["user"]), str(values.get("password") or ""))
    return TestResult(True, f"Signed in to {host}:{port}")


@_guard
def _test_cartesia(values: dict) -> TestResult:
    response = get(
        "https://api.cartesia.ai/voices",
        params={"limit": 1},
        headers={"X-API-Key": str(values.get("api_key") or ""), "Cartesia-Version": "2025-04-16"},
        timeout=20,
    )
    if response.status_code != 200:
        return TestResult(False, _http_error(response))
    return TestResult(True, "Cartesia key accepted")


@_guard
def _test_heygen(values: dict) -> TestResult:
    base = str(values.get("base_url") or "https://api.heygen.com").rstrip("/")
    response = get(f"{base}/v2/user/remaining_quota", headers={"X-Api-Key": str(values.get("api_key") or "")}, timeout=20)
    if response.status_code != 200:
        return TestResult(False, _http_error(response))
    data = (response.json() or {}).get("data") or {}
    return TestResult(True, "HeyGen key accepted", {"remaining_quota": data.get("remaining_quota")})


@_guard
def _test_elevenlabs(values: dict) -> TestResult:
    response = get("https://api.elevenlabs.io/v1/user/subscription", headers={"xi-api-key": str(values.get("api_key") or "")}, timeout=20)
    if response.status_code != 200:
        return TestResult(False, _http_error(response))
    tier = (response.json() or {}).get("tier") or "account"
    return TestResult(True, f"ElevenLabs {tier} plan")


def _git_api_user(provider: str, values: dict):
    token = str(values.get("access_token") or "")
    username = str(values.get("username") or "")
    if provider == "github":
        return get("https://api.github.com/user", headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}, timeout=20)
    if provider == "gitlab":
        base = str(values.get("base_url") or "https://gitlab.com").rstrip("/")
        return get(f"{base}/api/v4/user", headers={"PRIVATE-TOKEN": token}, timeout=20)
    if username and username != "x-token-auth":
        return get("https://api.bitbucket.org/2.0/user", auth=(username, token), timeout=20)
    return get("https://api.bitbucket.org/2.0/user", headers={"Authorization": f"Bearer {token}"}, timeout=20)


def _check_ssh_key(private_key: str) -> TestResult:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "key"
        path.write_text(private_key.strip() + "\n", encoding="utf-8")
        path.chmod(0o600)
        out = subprocess.run(["ssh-keygen", "-y", "-f", str(path)], capture_output=True, text=True, timeout=10)
    if out.returncode != 0:
        return TestResult(False, "The SSH private key could not be read (passphrase-protected keys are not supported).")
    public = out.stdout.strip()
    return TestResult(True, "SSH key is valid. Add the public key below as an access key on the repository.", {"public_key": public})


def _git_tester(provider: str) -> Callable[[dict], TestResult]:
    @_guard
    def tester(values: dict) -> TestResult:
        if str(values.get("auth_type") or "token") == "ssh_key":
            return _check_ssh_key(str(values.get("ssh_private_key") or ""))
        response = _git_api_user(provider, values)
        if response.status_code != 200:
            return TestResult(False, _http_error(response))
        data = response.json() or {}
        name = data.get("login") or data.get("username") or data.get("display_name") or "token owner"
        return TestResult(True, f"Token accepted for {name}")

    return tester


def _git_fields(provider: str) -> tuple[Field, ...]:
    token_help = {
        "bitbucket": "A repository or workspace access token with Repositories: Read. Leave username empty for access tokens.",
        "github": "A fine-grained token with Contents: Read on the repositories you add.",
        "gitlab": "A project or personal access token with read_repository.",
    }[provider]
    fields = [
        Field("auth_type", "Authentication", "select", default="token", options=("token", "ssh_key")),
        Field("username", "Username", placeholder="x-token-auth" if provider == "bitbucket" else "", help="Only for app passwords.", advanced=True),
        Field("access_token", "Access token", "secret", help=token_help),
        Field("ssh_private_key", "SSH private key", "textarea", help="A deploy key without a passphrase. Read access is enough."),
    ]
    if provider == "gitlab":
        fields.append(Field("base_url", "GitLab URL", "url", default="https://gitlab.com", advanced=True))
    return tuple(fields)


PROVIDERS: dict[str, Provider] = {}


def _register(provider: Provider) -> None:
    PROVIDERS[provider.id] = provider


_register(
    Provider(
        id="jira",
        name="Jira",
        category="Work tracking",
        description="Read tickets, epics and changelogs. Copilot writes only after you approve a plan.",
        help_url="https://id.atlassian.com/manage-profile/security/api-tokens",
        fields=(
            Field("base_url", "Site URL", "url", "jira_base_url", True, "https://your-team.atlassian.net"),
            Field("email", "Account email", "email", "jira_email", True),
            Field("api_token", "API token", "secret", "jira_api_token", True, help="Create one at id.atlassian.com → Security → API tokens."),
            Field("projects", "Projects", "text", "jira_projects", placeholder="PROD,SUP", help="Project keys to sync, comma separated."),
            Field("allowed_projects", "Writable projects", "text", "jira_allowed_projects", placeholder="PROD,SUP", help="Copilot may only write to these.", advanced=True),
        ),
        test=_test_jira,
    )
)
_register(
    Provider(
        id="cliq",
        name="Zoho Cliq",
        category="Chat",
        description="Read the chats you are in for the weekly briefing and release follow-ups.",
        help_url="https://api-console.zoho.in/",
        custom_ui="oauth",
        fields=(
            Field("client_id", "Client ID", "text", "cliq_client_id", True, help="Server-based app in the Zoho API console."),
            Field("client_secret", "Client secret", "secret", "cliq_client_secret", True),
            Field("api_domain", "Cliq API domain", "url", "cliq_api_domain", default="https://cliq.zoho.in", advanced=True),
            Field("accounts_url", "Accounts URL", "url", "cliq_accounts_url", default="https://accounts.zoho.in", advanced=True),
            Field("pm_email", "Your Cliq email", "email", "cliq_pm_email"),
            Field("pm_chat_id", "Briefing chat ID", "text", "cliq_pm_chat_id", help="Where the weekly briefing is posted.", advanced=True),
            Field("product_internal_chat_id", "Product channel ID", "text", "cliq_product_internal_chat_id", advanced=True),
            Field("wallet_chat_id", "Wallet requests channel ID", "text", "cliq_wallet_chat_id", advanced=True),
            Field("refresh_token", "Refresh token", "secret", "cliq_refresh_token", help="Set by Connect with Zoho.", advanced=True),
            Field("access_token", "Access token", "secret", "cliq_access_token", advanced=True),
        ),
        test=_test_cliq,
    )
)
_register(
    Provider(
        id="llm",
        name="AI models",
        category="AI",
        description="OpenAI-compatible and Anthropic providers, routed per task (briefing, prototypes, Copilot, docs, marketing).",
        help_url="https://platform.openai.com/api-keys",
        custom_ui="llm",
        fields=(),
        test=_test_llm,
    )
)
_register(
    Provider(
        id="google",
        name="Google Drive, Docs and Sheets",
        category="Documents",
        description="Publish release notes to Docs, store artifacts in Drive and sync the marketing sheet.",
        help_url="https://console.cloud.google.com/iam-admin/serviceaccounts",
        fields=(
            Field("service_account_json", "Service account key (JSON)", "json", "gdrive_key_json", True, help="Share your Drive folders with the service account email as Editor."),
            Field("folder_id", "Artifacts folder ID", "text", "gdrive_folder_id"),
            Field("assets_folder_id", "Assets folder ID", "text", "gdrive_assets_folder_id", advanced=True),
            Field("drive_root", "Marketing Drive root", "text", "marketing_drive_root", help="Folder ID where campaign folders are created."),
            Field("domain", "Share with domain", "text", "gdrive_domain", placeholder="your-company.com", advanced=True),
            Field("sheet_id", "Marketing sheet ID", "text", "marketing_sheet_id"),
            Field("sheet_tab", "Marketing sheet tab", "text", "marketing_sheet_tab", advanced=True),
            Field("release_note_template_doc_id", "Release note template Doc ID", "text", "release_note_template_doc_id", advanced=True),
        ),
        test=_test_google,
    )
)
_register(
    Provider(
        id="smtp",
        name="Email (SMTP)",
        category="Delivery",
        description="Send release-note and briefing emails.",
        help_url="https://support.google.com/a/answer/176600",
        fields=(
            Field("host", "SMTP host", "text", "smtp_host", True),
            Field("port", "Port", "number", "smtp_port", default=587),
            Field("user", "Username", "text", "smtp_user"),
            Field("password", "Password", "secret", "smtp_password"),
            Field("from_address", "From address", "email", "smtp_from"),
            Field("use_tls", "Use STARTTLS", "bool", "smtp_use_tls", default=True),
            Field("release_notes_email", "Release notes go to", "email", "release_notes_email"),
        ),
        test=_test_smtp,
    )
)
_register(
    Provider(
        id="cartesia",
        name="Cartesia",
        category="Voice",
        description="Narration for launch films and cloned voices for avatar videos.",
        help_url="https://play.cartesia.ai/keys",
        fields=(
            Field("api_key", "API key", "secret", "cartesia_api_key", True),
            Field("voice_id", "Narrator voice ID", "text", "cartesia_voice_id"),
            Field("model", "Model", "text", "cartesia_model", default="sonic-3", advanced=True),
            Field("marketing_voice_id", "Marketing narrator voice ID", "text", "marketing_cartesia_voice_id", advanced=True),
            Field("avatar_voice_id", "Avatar voice ID", "text", "avatar_cartesia_voice_id"),
            Field("avatar_voice_name", "Avatar voice name", "text", "avatar_cartesia_voice_name", advanced=True),
            Field("avatar_locale", "Avatar locale", "text", "avatar_cartesia_locale", default="en-IN", advanced=True),
            Field("avatar_accent", "Avatar accent", "text", "avatar_cartesia_accent", advanced=True),
        ),
        test=_test_cartesia,
    )
)
_register(
    Provider(
        id="heygen",
        name="HeyGen",
        category="Video",
        description="Presenter videos from your own photo avatar.",
        help_url="https://app.heygen.com/settings?nav=API",
        fields=(
            Field("api_key", "API key", "secret", "heygen_api_key", True),
            Field("base_url", "API URL", "url", "heygen_base_url", default="https://api.heygen.com", advanced=True),
            Field("voice_id", "Default voice ID", "text", "heygen_voice_id"),
            Field("voice_name", "Default voice name", "text", "heygen_voice_name", advanced=True),
        ),
        test=_test_heygen,
    )
)
_register(
    Provider(
        id="elevenlabs",
        name="ElevenLabs",
        category="Voice",
        description="Optional voice cloning for avatar videos.",
        help_url="https://elevenlabs.io/app/settings/api-keys",
        fields=(
            Field("api_key", "API key", "secret", "elevenlabs_api_key", True),
            Field("voice_id", "Voice ID", "text", "elevenlabs_voice_id"),
            Field("voice_name", "Voice name", "text", "elevenlabs_voice_name", advanced=True),
        ),
        test=_test_elevenlabs,
    )
)
for _git in ("bitbucket", "github", "gitlab"):
    _register(
        Provider(
            id=_git,
            name={"bitbucket": "Bitbucket", "github": "GitHub", "gitlab": "GitLab"}[_git],
            category="Code",
            description="Read access for repository mirrors, branches and release detection.",
            help_url={
                "bitbucket": "https://support.atlassian.com/bitbucket-cloud/docs/access-tokens/",
                "github": "https://github.com/settings/personal-access-tokens",
                "gitlab": "https://gitlab.com/-/user_settings/personal_access_tokens",
            }[_git],
            fields=_git_fields(_git),
            test=_git_tester(_git),
            multiple=True,
        )
    )


def get_provider(provider_id: str) -> Provider:
    provider = PROVIDERS.get(provider_id)
    if not provider:
        raise KeyError(f"Unknown provider: {provider_id}")
    return provider
