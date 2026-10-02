import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Prototype, PrototypeFile
from app.services.prototype import export_zip
from app.services.prototype_handoff import ASSETS, handoff_files


def test_handoff_is_bound_to_exact_current_source():
    files = {"package.json": '{"dependencies":{"tailwindcss":"4.2.1"}}',
             "src/pages/Example.jsx": '<div className="px-6 max-w-[1600px]" />',
             "src/styles.css": "body {font-family: Figtree}", "PORTING.md": "Old instructions"}
    out = handoff_files(2, "Example", files)
    manifest = json.loads(out["handoff/manifest.json"])
    assert manifest["files"]["src/pages/Example.jsx"] == hashlib.sha256(files["src/pages/Example.jsx"].encode()).hexdigest()
    assert manifest["geometry_sources"][0]["line"] == 1
    assert manifest["verification"] == "unmeasured"
    assert out["handoff/previous-porting.md"] == "Old instructions"
    changed = handoff_files(2, "Example", {**files, "src/styles.css": "body {padding: 1rem}"})
    assert json.loads(changed["handoff/manifest.json"])["source_fingerprint"] != manifest["source_fingerprint"]


def test_export_has_one_authoritative_porting_guide_and_no_source_mutation():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        row = Prototype(title="Current design")
        db.add(row)
        db.flush()
        source = PrototypeFile(prototype_id=row.id, path="src/pages/Example.jsx", content='<div className="gap-6" />')
        db.add_all([source, PrototypeFile(prototype_id=row.id, path="PORTING.md", content="Old guide")])
        db.commit()
        blob = export_zip(db, row.id)
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            assert archive.namelist().count("PORTING.md") == 1
            assert archive.read("handoff/previous-porting.md") == b"Old guide"
            assert archive.read(source.path).decode() == source.content
            assert "handoff/build-styles.mjs" in archive.namelist()
        assert db.query(PrototypeFile).count() == 2
    engine.dispose()


def test_comparison_fails_for_drift_missing_landmarks_and_mismatched_viewports(tmp_path):
    node = "/usr/local/bin/node"
    data = {"viewport": {"width": 1440, "height": 900}, "devicePixelRatio": 1, "scroll": {"x": 0, "y": 0}, "fonts": "loaded",
            "elements": {"content": {"rect": {"x": 96, "y": 88, "width": 1320, "height": 600}, "style": {"fontSize": "14px", "gap": "24px"}}}}
    reference = tmp_path / "reference.json"
    actual = tmp_path / "actual.json"
    reference.write_text(json.dumps(data))
    def compare(value):
        actual.write_text(json.dumps(value))
        return subprocess.run([node, str(ASSETS / "compare-layout.mjs"), str(reference), str(actual)], capture_output=True, text=True)
    assert compare(data).returncode == 0
    changed = json.loads(json.dumps(data))
    changed["elements"]["content"]["rect"]["width"] = 1200
    assert "content.width" in compare(changed).stdout
    assert compare(changed).returncode == 1
    assert compare({**data, "elements": {}}).returncode == 1
    assert compare({**data, "viewport": {"width": 390, "height": 844}}).returncode == 1
