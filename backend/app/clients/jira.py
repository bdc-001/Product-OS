from __future__ import annotations

from datetime import datetime
from typing import Any

from app.clients.http import client as http_client
from app.config import settings
from app.services.jira_fields import FIELD_NAME_EXACT, FIELD_NAME_MATCH
from app.services.jira_scope import involvement_jql, is_aborted_status, matches_pm, not_aborted_jql

ALLOWED_PROJECTS = {"AC", "PS"}
ALLOWED_CREATE_KINDS = {
    "task": ("Task",),
    "bug": ("Bug", "Defect"),
    "report": (
        "Product/Report Requirement",
        "Product Report Requirement",
        "Report Requirement",
        "Product Requirement",
    ),
}
DENIED_TRANSITION_TOKENS = (
    "abort",
    "cancelled",
    "canceled",
    "cancel",
    "archive",
    "delete",
    "won't do",
    "wont do",
    "won't-do",
)
SYSTEM_FIELD_IDS = {
    "summary": "summary",
    "description": "description",
    "priority": "priority",
    "assignee": "assignee",
    "labels": "labels",
    "due_date": "duedate",
    "parent": "parent",
}


def to_adf(text: str) -> dict:
    lines = (text or "").replace("\r\n", "\n").split("\n")
    content = []
    for line in lines:
        if line:
            content.append({"type": "paragraph", "content": [{"type": "text", "text": line[:8000]}]})
        else:
            content.append({"type": "paragraph", "content": []})
    if not content:
        content = [{"type": "paragraph", "content": [{"type": "text", "text": " "}]}]
    return {"type": "doc", "version": 1, "content": content}


def _jira_error(response) -> str:
    try:
        data = response.json()
        messages = [str(item) for item in (data.get("errorMessages") or []) if item]
        errors = data.get("errors") or {}
        if isinstance(errors, dict):
            messages.extend(f"{key}: {value}" for key, value in errors.items() if value)
        if messages:
            return "; ".join(messages)[:800]
    except Exception:
        pass
    text = (getattr(response, "text", None) or "")[:800]
    return text or f"Jira HTTP {getattr(response, 'status_code', '')}"


def create_kind(issue_type: str) -> str:
    text = (issue_type or "").strip().lower()
    if any(needle in text for needle in ("report", "product requirement", "product/report")):
        return "report"
    if text in {"bug", "defect", "incident"}:
        return "bug"
    return "task"


def _adf_to_text(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return " ".join(_adf_to_text(item) for item in node if item)
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text") or ""
        if node.get("type") == "mention":
            attrs = node.get("attrs") or {}
            return str(attrs.get("text") or attrs.get("id") or "")
        if "content" in node:
            return " ".join(_adf_to_text(child) for child in node["content"])
        if "body" in node:
            return _adf_to_text(node["body"])
    return ""


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = [_scalar(item) for item in value if item]
        return ", ".join(p for p in parts if p)
    if isinstance(value, dict):
        for key in ("displayName", "name", "value", "emailAddress", "key"):
            if value.get(key):
                return str(value[key]).strip()
        if value.get("content"):
            return _adf_to_text(value)
        if value.get("url"):
            return str(value["url"])
    return ""


class JiraClient:
    def __init__(self) -> None:
        self.base = settings.jira_base_url.rstrip("/")
        self.email = settings.jira_email
        self.token = settings.jira_api_token

    @property
    def configured(self) -> bool:
        return bool(self.base and self.email and self.token)

    def _client(self):
        return http_client(
            base_url=self.base,
            auth=(self.email, self.token),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )

    def _raw_client(self):
        return http_client(
            base_url=self.base,
            auth=(self.email, self.token),
            headers={"Accept": "application/json"},
        )

    def _raise(self, response) -> None:
        if response.status_code >= 400:
            raise RuntimeError(_jira_error(response))

    def search(self, jql: str, fields: list[str], expand: list[str] | None = None, max_results: int = 100) -> list[dict]:
        issues: list[dict] = []
        next_page_token = None
        with self._client() as client:
            while True:
                payload: dict[str, Any] = {
                    "jql": jql,
                    "maxResults": max_results,
                    "fields": fields,
                }
                if expand:
                    payload["expand"] = ",".join(expand)
                if next_page_token:
                    payload["nextPageToken"] = next_page_token
                response = client.post("/rest/api/3/search/jql", json=payload)
                response.raise_for_status()
                data = response.json()
                issues.extend(data.get("issues") or [])
                next_page_token = data.get("nextPageToken")
                if not next_page_token or data.get("isLast", False):
                    break
                if len(issues) >= 400:
                    break
        return issues

    def is_in_scope(self, issue: dict) -> bool:
        fields = issue.get("fields") or {}
        status = ((fields.get("status") or {}).get("name") or "")
        if is_aborted_status(status):
            return False
        assignee = fields.get("assignee") or {}
        if matches_pm(assignee.get("displayName") or "") or matches_pm(assignee.get("emailAddress") or ""):
            return True
        mapping = self.field_map()
        for fid, logical in mapping.items():
            if logical in {"product_manager", "developer"} and matches_pm(_scalar(fields.get(fid))):
                return True
        for comment in ((fields.get("comment") or {}).get("comments") or []):
            if matches_pm(_adf_to_text(comment.get("body"))):
                return True
        return False

    def _search_scoped(self, jql: str, fields: list[str], expand: list[str] | None = None, max_results: int = 100) -> list[dict]:
        try:
            found = self.search(jql, fields=fields, expand=expand, max_results=max_results)
        except Exception:
            fallback = jql.replace('OR "Developer" = currentUser() ', "").replace("OR comment ~ currentUser()", "")
            found = self.search(fallback, fields=fields, expand=expand, max_results=max_results)
        return [issue for issue in found if not is_aborted_status(((issue.get("fields") or {}).get("status") or {}).get("name") or "")]

    def field_map(self) -> dict[str, str]:
        """customfield_xxxx -> logical name from FIELD_NAME_MATCH."""
        if getattr(self, "_field_map", None):
            return self._field_map
        mapping: dict[str, str] = {}
        try:
            with self._client() as client:
                response = client.get("/rest/api/3/field")
                response.raise_for_status()
                catalog = response.json() or []
        except Exception:
            self._field_map = mapping
            return mapping
        for field in catalog:
            fid = field.get("id") or ""
            name = (field.get("name") or "").strip().lower()
            if not fid.startswith("customfield_"):
                continue
            if name in FIELD_NAME_EXACT:
                mapping[fid] = FIELD_NAME_EXACT[name]
                continue
            for logical, needles in FIELD_NAME_MATCH.items():
                if any(needle in name for needle in needles):
                    mapping[fid] = logical
                    break
        self._field_map = mapping
        return mapping

    def _search_fields(self) -> list[str]:
        base = [
            "summary",
            "status",
            "assignee",
            "reporter",
            "creator",
            "description",
            "priority",
            "issuetype",
            "created",
            "updated",
            "duedate",
            "resolutiondate",
            "labels",
            "comment",
            "issuelinks",
            "parent",
        ]
        return base + list(self.field_map().keys())

    def fetch_pm_issues(self, updated_since: str | None = None) -> list[dict]:
        projects = settings.jira_projects or "AC,PS"
        jql = f"project in ({projects}) AND {not_aborted_jql()} AND {involvement_jql()}"
        if updated_since:
            jql += f' AND updated >= "{updated_since}"'
        jql += " ORDER BY priority DESC, updated ASC"
        return self._search_scoped(jql, fields=self._search_fields(), expand=["changelog"])

    def fetch_open_board_issues(self) -> list[dict]:
        projects = settings.jira_projects or "AC,PS"
        jql = (
            f"project in ({projects}) AND statusCategory != Done AND {not_aborted_jql()} "
            f"AND {involvement_jql()} ORDER BY priority DESC, updated ASC"
        )
        return self._search_scoped(jql, fields=self._search_fields(), expand=["changelog"], max_results=100)

    def fetch_by_keys(self, keys: list[str], scoped: bool = True) -> list[dict]:
        unique = []
        for key in keys:
            key = (key or "").strip().upper()
            if key and key not in unique:
                unique.append(key)
        if not unique:
            return []
        found: list[dict] = []
        involvement = f" AND {involvement_jql()}" if scoped else ""
        for i in range(0, len(unique), 40):
            chunk = unique[i : i + 40]
            quoted = ", ".join(f'"{key}"' for key in chunk)
            jql = f"key in ({quoted}) AND {not_aborted_jql()}{involvement} ORDER BY updated DESC"
            found.extend(self._search_scoped(jql, fields=self._search_fields(), expand=["changelog"]))
        return found

    def fetch_pm_workflow_issues(self) -> list[dict]:
        """Done / Staging / QA In Progress tickets where the signed-in user is PM."""
        from app.services.team import qa_person

        projects = settings.jira_projects or "AC,PS"
        pm = '"Product Manager" = currentUser()'
        qa_id = (qa_person() or {}).get("account_id") or ""
        jqls = [
            (
                f"project in ({projects}) AND {pm} AND {not_aborted_jql()} "
                f'AND status in (Done, STAGING, Staging, UAT, "STAGING->QA", Completed)'
            ),
            (
                f"project in ({projects}) AND assignee = currentUser() AND {not_aborted_jql()} "
                "AND status in (Done, Completed)"
            ),
        ]
        if qa_id:
            jqls.append(
                (
                    f"project in ({projects}) AND {pm} AND assignee = \"{qa_id}\" "
                    f'AND statusCategory = "In Progress" AND {not_aborted_jql()}'
                )
            )
        seen: set[str] = set()
        found: list[dict] = []
        for jql in jqls:
            try:
                rows = self._search_scoped(
                    jql + " ORDER BY updated DESC",
                    fields=self._search_fields(),
                    expand=["changelog"],
                    max_results=80,
                )
            except Exception:
                continue
            for issue in rows:
                key = issue.get("key") or ""
                if key and key not in seen:
                    seen.add(key)
                    found.append(issue)
        return found

    def fetch_dev_in_progress(self) -> list[dict]:
        from app.services.team import developer_account_ids, jql_account_list

        projects = settings.jira_projects or "AC,PS"
        ids = jql_account_list(developer_account_ids())
        if not ids:
            return []
        jql = (
            f"project in ({projects}) AND assignee in ({ids}) "
            f'AND statusCategory = "In Progress" AND issuetype not in (Epic, Subtask, Sub-task) '
            f"AND {not_aborted_jql()} ORDER BY updated DESC"
        )
        try:
            return self.search(jql, fields=["summary", "status", "assignee", "issuetype"], max_results=100)
        except Exception:
            return []

    def fetch_summary_matches(self, phrase: str) -> list[dict]:
        import re

        words = [word for word in re.findall(r"[A-Za-z0-9]+", phrase or "") if len(word) >= 3]
        if len(words) < 2:
            return []
        query = " AND ".join(f'summary ~ "{word}"' for word in words[:5])
        projects = settings.jira_projects or "AC,PS"
        jql = (
            f"project in ({projects}) AND {not_aborted_jql()} AND {query} "
            f'AND "Product Manager" = currentUser() ORDER BY updated DESC'
        )
        try:
            return self._search_scoped(jql, fields=self._search_fields(), expand=["changelog"], max_results=10)
        except Exception:
            return []

    def fetch_released_ac_tasks(self, after_date: str) -> list[dict]:
        """AC Task tickets currently Released, unscoped to Arsalaan. after_date is YYYY-MM-DD IST."""
        fields = self._search_fields()
        expand = ["changelog"]
        queries = [
            (
                "project = AC AND issuetype = Task AND status = Released "
                f'AND status changed to Released AFTER "{after_date}" ORDER BY resolutiondate DESC'
            ),
            (
                "project = AC AND issuetype = Task AND status = Released "
                f'AND resolutiondate >= "{after_date}" ORDER BY resolutiondate DESC'
            ),
        ]
        last_error: Exception | None = None
        for jql in queries:
            try:
                return self.search(jql, fields=fields, expand=expand, max_results=100)
            except Exception as exc:
                last_error = exc
                print(f"jira released-ac JQL failed: {jql}: {exc}")
        if last_error:
            raise last_error
        return []

    def normalize(self, issue: dict) -> dict:
        fields = issue.get("fields") or {}
        key = issue.get("key") or ""
        comments = []
        for comment in ((fields.get("comment") or {}).get("comments") or []):
            comments.append(
                {
                    "id": comment.get("id"),
                    "author": ((comment.get("author") or {}).get("displayName")) or "",
                    "body": _adf_to_text(comment.get("body")),
                    "created": comment.get("created"),
                    "updated": comment.get("updated"),
                }
            )
        changelog = []
        for history in ((issue.get("changelog") or {}).get("histories") or []):
            for item in history.get("items") or []:
                changelog.append(
                    {
                        "id": history.get("id"),
                        "author": ((history.get("author") or {}).get("displayName")) or "",
                        "created": history.get("created"),
                        "field": item.get("field") or "",
                        "from": item.get("fromString") or "",
                        "to": item.get("toString") or "",
                    }
                )
        extras: dict[str, Any] = {}
        mapping = self.field_map()
        for fid, logical in mapping.items():
            raw_val = fields.get(fid)
            text = _scalar(raw_val)
            if text:
                extras[logical] = text
            if logical == "product_manager" and isinstance(raw_val, dict) and raw_val.get("emailAddress"):
                extras["product_manager_email"] = str(raw_val["emailAddress"]).strip()
        links = []
        aborted = []
        for link in fields.get("issuelinks") or []:
            inward = link.get("inwardIssue") or link.get("outwardIssue") or {}
            linked_key = inward.get("key") or ""
            linked_status = ((inward.get("fields") or {}).get("status") or {}).get("name") or ""
            linked_summary = ((inward.get("fields") or {}).get("summary") or "")
            if linked_key:
                links.append(f"{linked_key} ({linked_status or 'Unknown'}) {linked_summary}".strip())
                if linked_status.lower() in {"aborted", "cancelled", "canceled", "won't do", "wont do"}:
                    aborted.append(linked_key)
        if links:
            extras["linked_issues"] = links
        if aborted:
            extras["aborted_links"] = aborted
        reporter = fields.get("reporter") or {}
        extras["reporter"] = reporter.get("displayName") or ""
        resolutiondate = fields.get("resolutiondate") or ""
        if resolutiondate:
            extras["resolution_date"] = str(resolutiondate)[:10]
        parent = fields.get("parent") or {}
        parent_key = parent.get("key") or extras.get("epic_link") or ""
        if parent_key:
            extras["parent_key"] = parent_key
            extras["parent_summary"] = _scalar((parent.get("fields") or {}).get("summary")) or extras.get("epic_name") or ""
            extras["parent_type"] = _scalar((parent.get("fields") or {}).get("issuetype"))
        extras["epic_key"] = extras.get("epic_link") or parent_key
        assignee = fields.get("assignee") or {}
        creator = fields.get("creator") or {}
        status = fields.get("status") or {}
        due = fields.get("duedate")
        priority = extras.get("priority_level") or _scalar(fields.get("priority")) or ""
        return {
            "issue_key": key,
            "jira_id": str(issue.get("id") or ""),
            "summary": fields.get("summary") or "",
            "description": _adf_to_text(fields.get("description")),
            "status": (status.get("name") or ""),
            "status_category": ((status.get("statusCategory") or {}).get("key") or ""),
            "priority": priority,
            "issue_type": ((fields.get("issuetype") or {}).get("name") or ""),
            "assignee": assignee.get("displayName") or "",
            "assignee_id": assignee.get("accountId") or "",
            "creator": creator.get("displayName") or extras.get("reporter") or "",
            "labels": ",".join(fields.get("labels") or []),
            "created_at": _parse_dt(fields.get("created")),
            "updated_at": _parse_dt(fields.get("updated")),
            "due_date": _parse_dt(f"{due}T00:00:00") if due else None,
            "comments_json": comments,
            "changelog_json": changelog,
            "extra_json": extras,
            "url": f"{self.base}/browse/{key}",
        }

    def fetch_sense_epics(self) -> list[dict]:
        """AC Epics created by, assigned to, or PM'd by the current Jira user."""
        jql = (
            "project = AC AND issuetype = Epic AND "
            f"{not_aborted_jql()} AND ("
            "assignee = currentUser() OR creator = currentUser() OR reporter = currentUser() "
            'OR "Product Manager" = currentUser()'
            ") ORDER BY updated DESC"
        )
        return self._search_scoped(jql, fields=self._search_fields(), max_results=80)

    def fetch_epic_children(self, epic_keys: list[str]) -> list[dict]:
        keys = [key.strip().upper() for key in epic_keys if (key or "").strip()]
        if not keys:
            return []
        quoted = ", ".join(f'"{key}"' for key in keys[:40])
        fields = self._search_fields()
        jqls = [
            (
                f"project = AC AND issuetype != Epic AND {not_aborted_jql()} "
                f'AND (parent in ({quoted}) OR "Epic Link" in ({quoted})) '
                "ORDER BY updated DESC"
            ),
            (
                f"project = AC AND issuetype != Epic AND {not_aborted_jql()} "
                f"AND parent in ({quoted}) ORDER BY updated DESC"
            ),
        ]
        for jql in jqls:
            try:
                return self._search_scoped(jql, fields=fields, max_results=200)
            except Exception:
                continue
        return []

    def myself(self) -> dict:
        if getattr(self, "_myself", None):
            return self._myself
        with self._client() as client:
            response = client.get("/rest/api/3/myself")
            self._raise(response)
            data = response.json() or {}
        self._myself = {
            "account_id": data.get("accountId") or "",
            "name": data.get("displayName") or "",
            "email": data.get("emailAddress") or "",
        }
        return self._myself

    def get_issue(self, key: str) -> dict:
        issue_key = (key or "").strip().upper()
        if not issue_key:
            raise RuntimeError("Ticket key is required.")
        with self._client() as client:
            response = client.get(
                f"/rest/api/3/issue/{issue_key}",
                params={"fields": ",".join(self._search_fields()), "expand": "changelog"},
            )
            self._raise(response)
            return response.json()

    def _fields_meta(self) -> dict[str, dict]:
        if getattr(self, "_fields_meta_cache", None):
            return self._fields_meta_cache
        meta: dict[str, dict] = {}
        try:
            with self._client() as client:
                response = client.get("/rest/api/3/field")
                self._raise(response)
                catalog = response.json() or []
        except Exception:
            self._fields_meta_cache = meta
            return meta
        for field in catalog:
            fid = field.get("id") or ""
            schema = field.get("schema") or {}
            if not fid:
                continue
            meta[fid] = {
                "id": fid,
                "name": field.get("name") or "",
                "type": schema.get("type") or "string",
                "items": schema.get("items") or "",
            }
        self._fields_meta_cache = meta
        return meta

    def _logical_ids(self) -> dict[str, str]:
        mapping = {logical: fid for fid, logical in self.field_map().items()}
        mapping.update(SYSTEM_FIELD_IDS)
        return mapping

    def _issue_types(self, project: str) -> list[dict]:
        cache = getattr(self, "_issue_types_cache", None) or {}
        if project in cache:
            return cache[project]
        with self._client() as client:
            response = client.get(f"/rest/api/3/project/{project}")
            self._raise(response)
            types = response.json().get("issueTypes") or []
        cache[project] = types
        self._issue_types_cache = cache
        return types

    def resolve_issue_type(self, project: str, issue_type: str) -> dict:
        kind = create_kind(issue_type)
        names = ALLOWED_CREATE_KINDS[kind]
        lowered = {name.lower() for name in names}
        for item in self._issue_types(project):
            name = (item.get("name") or "").strip()
            if name.lower() in lowered:
                return {"id": item.get("id") or "", "name": name, "kind": kind}
        raise RuntimeError(f"{project} has no allowed issue type matching {issue_type}.")

    def _encode_value(self, field_id: str, value: Any, account_id: str = "") -> Any:
        if value is None or value == "":
            return None
        meta = self._fields_meta().get(field_id) or {}
        ftype = meta.get("type") or ("string" if field_id.startswith("customfield_") else field_id)
        items = meta.get("items") or ""
        if field_id == "description":
            return value if isinstance(value, dict) else to_adf(str(value))
        if field_id == "summary":
            return str(value)[:255]
        if field_id == "priority":
            return value if isinstance(value, dict) else {"name": str(value)}
        if field_id == "assignee":
            aid = account_id or str(value)
            return {"accountId": aid} if aid else None
        if field_id == "labels":
            if isinstance(value, list):
                return [str(item).strip() for item in value if str(item).strip()][:20]
            return [part.strip() for part in str(value).split(",") if part.strip()][:20]
        if field_id == "duedate":
            return str(value)[:10]
        if field_id == "parent":
            return {"key": str(value).strip().upper()}
        if ftype in {"string", "any"}:
            return str(value)[:8000]
        if ftype == "number":
            try:
                return float(value) if "." in str(value) else int(value)
            except (TypeError, ValueError):
                return None
        if ftype == "date":
            return str(value)[:10]
        if ftype == "datetime":
            return str(value)
        if ftype == "option":
            return value if isinstance(value, dict) else {"value": str(value)}
        if ftype == "priority":
            return value if isinstance(value, dict) else {"name": str(value)}
        if ftype == "user":
            aid = account_id or str(value)
            return {"accountId": aid} if aid else None
        if ftype == "array":
            values = value if isinstance(value, list) else [part.strip() for part in str(value).split(",") if part.strip()]
            if items == "option":
                return [{"value": str(item)} for item in values if item]
            if items == "user":
                return [{"accountId": str(item)} for item in values if item]
            return [str(item) for item in values if item]
        return str(value)[:8000]

    def encode_logical_fields(self, fields: dict[str, Any], *, users: dict[str, str] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        ids = self._logical_ids()
        users = users or {}
        for logical, value in (fields or {}).items():
            key = (logical or "").strip()
            if key in {"status", "issue_type", "reporter", "issuetype", "project"}:
                continue
            field_id = ids.get(key) or (key if key.startswith("customfield_") or key in SYSTEM_FIELD_IDS.values() else "")
            if not field_id:
                continue
            encoded = self._encode_value(field_id, value, account_id=users.get(key) or "")
            if encoded is not None:
                payload[field_id] = encoded
        return payload

    def create_issue(
        self,
        *,
        project: str,
        issue_type: str,
        summary: str,
        description: str = "",
        fields: dict | None = None,
        assignee_id: str = "",
        parent_key: str = "",
        users: dict[str, str] | None = None,
    ) -> dict:
        project_key = (project or "").strip().upper()
        if project_key not in ALLOWED_PROJECTS:
            raise RuntimeError("Copilot can only create tickets on AC or PS.")
        title = (summary or "").strip()
        if not title:
            raise RuntimeError("Summary is required to create a ticket.")
        resolved = self.resolve_issue_type(project_key, issue_type)
        payload_fields: dict[str, Any] = {
            "project": {"key": project_key},
            "issuetype": {"id": resolved["id"]} if resolved.get("id") else {"name": resolved["name"]},
            "summary": title[:255],
        }
        if description:
            payload_fields["description"] = to_adf(description)
        if assignee_id:
            payload_fields["assignee"] = {"accountId": assignee_id}
        extras = self.encode_logical_fields(
            fields or {},
            users=users or ({"assignee": assignee_id} if assignee_id else {}),
        )
        extras.pop("parent", None)
        extras.pop("summary", None)
        extras.pop("description", None)
        extras.pop("assignee", None)
        payload_fields.update(extras)
        parent = (parent_key or "").strip().upper()
        if parent:
            payload_fields["parent"] = {"key": parent}
        with self._client() as client:
            response = client.post("/rest/api/3/issue", json={"fields": payload_fields})
            if response.status_code >= 400 and parent:
                payload_fields.pop("parent", None)
                response = client.post("/rest/api/3/issue", json={"fields": payload_fields})
            self._raise(response)
            created = response.json() or {}
        key = created.get("key") or ""
        if not key:
            raise RuntimeError("Jira created an issue without a key.")
        if parent:
            try:
                self.set_parent(key, parent)
            except RuntimeError:
                pass
        return self.get_issue(key)

    def add_comment(self, key: str, body: str) -> dict:
        issue_key = (key or "").strip().upper()
        text = (body or "").strip()
        if not issue_key or not text:
            raise RuntimeError("Comment needs a ticket key and a body.")
        with self._client() as client:
            response = client.post(
                f"/rest/api/3/issue/{issue_key}/comment",
                json={"body": to_adf(text)},
            )
            self._raise(response)
            return response.json()

    def assign_issue(self, key: str, account_id: str) -> None:
        issue_key = (key or "").strip().upper()
        aid = (account_id or "").strip()
        if not issue_key or not aid:
            raise RuntimeError("Assign needs a ticket key and a person.")
        with self._client() as client:
            response = client.put(f"/rest/api/3/issue/{issue_key}/assignee", json={"accountId": aid})
            self._raise(response)

    def update_fields(self, key: str, fields: dict[str, Any], *, assignee_id: str = "") -> dict:
        issue_key = (key or "").strip().upper()
        encoded = self.encode_logical_fields(fields or {}, users={"assignee": assignee_id} if assignee_id else None)
        if not issue_key or not encoded:
            raise RuntimeError("Nothing allowed to update on that ticket.")
        with self._client() as client:
            response = client.put(f"/rest/api/3/issue/{issue_key}", json={"fields": encoded})
            self._raise(response)
        return self.get_issue(issue_key)

    def list_transitions(self, key: str) -> list[dict]:
        issue_key = (key or "").strip().upper()
        with self._client() as client:
            response = client.get(f"/rest/api/3/issue/{issue_key}/transitions")
            self._raise(response)
            rows = response.json().get("transitions") or []
        out = []
        for row in rows:
            name = row.get("name") or ""
            dest = ((row.get("to") or {}).get("name") or "")
            out.append({"id": str(row.get("id") or ""), "name": name, "to": dest})
        return out

    def transition_issue(self, key: str, name_or_id: str) -> dict:
        issue_key = (key or "").strip().upper()
        wanted = (name_or_id or "").strip().lower()
        if not issue_key or not wanted:
            raise RuntimeError("Transition needs a ticket and a status.")
        if any(token in wanted for token in DENIED_TRANSITION_TOKENS):
            raise RuntimeError("That transition is not allowed.")
        allowed = self.list_transitions(issue_key)
        match = None
        for row in allowed:
            if row["id"] == wanted or (row["name"] or "").strip().lower() == wanted or (row["to"] or "").strip().lower() == wanted:
                match = row
                break
        if not match:
            names = ", ".join(row["name"] for row in allowed if row.get("name")) or "none"
            raise RuntimeError(f"Jira does not allow that transition. Allowed: {names}.")
        hay = f"{match.get('name') or ''} {match.get('to') or ''}".lower()
        if any(token in hay for token in DENIED_TRANSITION_TOKENS) or is_aborted_status(match.get("to") or ""):
            raise RuntimeError("That transition is not allowed.")
        with self._client() as client:
            response = client.post(
                f"/rest/api/3/issue/{issue_key}/transitions",
                json={"transition": {"id": match["id"]}},
            )
            self._raise(response)
        return self.get_issue(issue_key)

    def set_parent(self, key: str, parent_key: str) -> dict:
        issue_key = (key or "").strip().upper()
        epic = (parent_key or "").strip().upper()
        if not issue_key.startswith("AC-") or not epic.startswith("AC-"):
            raise RuntimeError("Parent epic can only be set on AC tickets.")
        if issue_key == epic:
            raise RuntimeError("A ticket cannot be its own epic.")
        with self._client() as client:
            response = client.put(f"/rest/api/3/issue/{issue_key}", json={"fields": {"parent": {"key": epic}}})
            if response.status_code >= 400:
                epic_field = self._logical_ids().get("epic_link")
                if not epic_field:
                    self._raise(response)
                response = client.put(
                    f"/rest/api/3/issue/{issue_key}",
                    json={"fields": {epic_field: epic}},
                )
            self._raise(response)
        return self.get_issue(issue_key)

    def attach_image(self, key: str, *, filename: str, data: bytes, mime: str) -> dict:
        issue_key = (key or "").strip().upper()
        if not issue_key:
            raise RuntimeError("Attach needs a ticket key.")
        if not data:
            raise RuntimeError("Image is empty.")
        name = (filename or "image.png").rsplit("/", 1)[-1]
        with self._raw_client() as client:
            response = client.post(
                f"/rest/api/3/issue/{issue_key}/attachments",
                headers={"X-Atlassian-Token": "no-check"},
                files={"file": (name, data, mime or "application/octet-stream")},
            )
            self._raise(response)
            payload = response.json()
        return payload[0] if isinstance(payload, list) and payload else (payload or {})

