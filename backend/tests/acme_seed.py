"""A fictional workspace seed for tests, shaped like `scripts/<name>_seed.py`."""

PROFILE = {
    "product_name": "Acme Voice",
    "company_name": "Acme",
    "product_modules": "Voice,Engage",
    "product_module_keywords": {"Engage": ["whatsapp", "campaign", "agentic"]},
    "product_description": "an AI phone / voice-agent platform (campaigns, outbound/inbound agents, KB, widgets)",
    "competitor_focus": "Ignore Auto QA / conversation-intelligence QA rivals.",
    "brand_rules": "Voice is the product name customers see. Do not brand customer copy as Engage.",
    "pm_personas": "CSMs, operators and sales leaders at contact-centre and collections teams",
    "jira_allowed_projects": "AC,PS",
    "jira_scope_rules": "Voice is AC-only. Product Support (PS) tickets count only when they mention Voice.",
    "support_email": "support@acme.test",
    "newsletter_sender": "Dana",
}

CONNECTION_DEFAULTS = {
    "smtp": {"release_notes_email": "pm@acme.test"},
    "jira": {"projects": "AC,PS", "allowed_projects": "AC,PS"},
    "cliq": {"product_internal_chat_id": "CT_1000000000000000000_10000000000"},
    "google": {"domain": "acme.test"},
}

REPOSITORY = {
    "name": "services",
    "provider": "bitbucket",
    "default_branch": "main",
    "release_pattern": "release/YYYY-MM-DD",
    "merge_format": "bitbucket",
    "path_scopes": ["acme-engage/"],
    "ui_path": "acme-engage/static",
}

PEOPLE = [
    {"name": "Sam Carter", "short": "Sam", "role": "dev", "jira_account_id": "acc-sam", "cliq_user_id": "10000000101", "aliases": ["sam"]},
    {"name": "Ravi Shah", "short": "Ravi", "role": "dev", "jira_account_id": "acc-ravi", "cliq_user_id": "10000000102", "aliases": ["ravi"]},
    {"name": "Jonathan Reed", "short": "Jonathan", "role": "dev", "jira_account_id": "acc-jonathan", "cliq_user_id": "10000000103", "aliases": ["jonathan", "jon", "jonathon"]},
    {"name": "Maya Lin", "short": "Maya", "role": "dev", "jira_account_id": "acc-maya", "cliq_user_id": "10000000104", "aliases": ["maya"]},
    {"name": "Asha Patel", "short": "Asha", "role": "qa", "jira_account_id": "acc-asha", "aliases": ["asha"]},
    {"name": "Alex", "short": "Alex", "role": "notes_pm", "email": "alex@example.com", "cliq_user_id": "10000000107", "cliq_chat_id": "2000000000000000007", "aliases": ["alex"]},
    {"name": "Priya", "short": "Priya", "role": "notes_pm", "email": "priya.rao@example.com", "cliq_user_id": "10000000108", "cliq_chat_id": "2000000000000000008", "aliases": ["priya", "pria"]},
    {"name": "Omar", "short": "Omar", "role": "other", "cliq_user_id": "10000000109", "aliases": ["omar"]},
    {"name": "Arsalaan", "short": "Arsalaan", "role": "pm", "email": "pm@acme.test", "cliq_user_id": "10000000001", "aliases": ["arsalaan"]},
]
