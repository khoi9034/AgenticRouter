from __future__ import annotations

import json
from urllib.request import Request, urlopen


payload = {
    "project_name": "Diana Test Project",
    "task_description": "Make hello world page prettier",
    "files_touched": ["index.html"],
    "mode": "advise",
}

request = Request(
    "http://127.0.0.1:8765/api/v1/route",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

with urlopen(request, timeout=10) as response:
    data = json.loads(response.read())

print(f"Recommended model: {data['recommended_model']} ({data['selected_model_alias']})")
