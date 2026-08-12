"""Default project task templates — engineering / CAD-CAM workshop presets."""
from __future__ import annotations

# Task fields:
#   title, type (2D CAD|CAD|CAM|Tools|Others), priority, effort (hours),
#   offset_start_days, duration_days, is_milestone, depends_on [indices]

DEFAULT_TEMPLATES = [
    {
        "id": "mechanical-cad-cam",
        "name": "Mechanical Part (CAD → CAM)",
        "description": "End-to-end: requirement → 2D → 3D → review → CAM → handoff",
        "tasks": [
            {"title": "Kickoff & requirement freeze", "type": "Tools", "priority": "High", "effort": 2, "offset_start_days": 0, "duration_days": 0, "is_milestone": True, "depends_on": []},
            {"title": "2D layout / drawing", "type": "2D CAD", "priority": "High", "effort": 8, "offset_start_days": 0, "duration_days": 3, "is_milestone": False, "depends_on": [0]},
            {"title": "3D model", "type": "CAD", "priority": "High", "effort": 16, "offset_start_days": 3, "duration_days": 5, "is_milestone": False, "depends_on": [1]},
            {"title": "Design review", "type": "Tools", "priority": "Medium", "effort": 4, "offset_start_days": 8, "duration_days": 1, "is_milestone": False, "depends_on": [2]},
            {"title": "CAM toolpath", "type": "CAM", "priority": "High", "effort": 12, "offset_start_days": 9, "duration_days": 4, "is_milestone": False, "depends_on": [3]},
            {"title": "NC verify & handoff", "type": "CAM", "priority": "High", "effort": 4, "offset_start_days": 13, "duration_days": 0, "is_milestone": True, "depends_on": [4]},
        ],
    },
    {
        "id": "2d-drawing-detailed",
        "name": "2D Drawing (Detailed)",
        "description": "Full drawing pack: title block, views, dims, balloon, check, release",
        "tasks": [
            {"title": "Drawing package kickoff", "type": "Tools", "priority": "High", "effort": 1, "offset_start_days": 0, "duration_days": 0, "is_milestone": True, "depends_on": []},
            {"title": "Title block & sheet format", "type": "2D CAD", "priority": "Medium", "effort": 2, "offset_start_days": 0, "duration_days": 1, "is_milestone": False, "depends_on": [0]},
            {"title": "Base views & layout", "type": "2D CAD", "priority": "High", "effort": 6, "offset_start_days": 1, "duration_days": 2, "is_milestone": False, "depends_on": [1]},
            {"title": "Dimensions & tolerances", "type": "2D CAD", "priority": "High", "effort": 8, "offset_start_days": 3, "duration_days": 3, "is_milestone": False, "depends_on": [2]},
            {"title": "Balloons / BOM callouts", "type": "2D CAD", "priority": "Medium", "effort": 4, "offset_start_days": 5, "duration_days": 1, "is_milestone": False, "depends_on": [3]},
            {"title": "Drawing self-check", "type": "Tools", "priority": "Medium", "effort": 2, "offset_start_days": 6, "duration_days": 1, "is_milestone": False, "depends_on": [4]},
            {"title": "Peer / lead review", "type": "Tools", "priority": "High", "effort": 3, "offset_start_days": 7, "duration_days": 1, "is_milestone": False, "depends_on": [5]},
            {"title": "Release drawing package", "type": "Tools", "priority": "High", "effort": 1, "offset_start_days": 8, "duration_days": 0, "is_milestone": True, "depends_on": [6]},
        ],
    },
    {
        "id": "jig-fixture-detailed",
        "name": "Jig / Fixture (Detailed)",
        "description": "Tooling: requirements → concept → 3D → fab drawings → BOM → tryout",
        "tasks": [
            {"title": "Tooling requirements & constraints", "type": "Tools", "priority": "High", "effort": 3, "offset_start_days": 0, "duration_days": 1, "is_milestone": False, "depends_on": []},
            {"title": "Concept sketches / options", "type": "Tools", "priority": "High", "effort": 4, "offset_start_days": 1, "duration_days": 2, "is_milestone": False, "depends_on": [0]},
            {"title": "Concept freeze", "type": "Tools", "priority": "High", "effort": 1, "offset_start_days": 3, "duration_days": 0, "is_milestone": True, "depends_on": [1]},
            {"title": "3D jig / fixture model", "type": "CAD", "priority": "High", "effort": 16, "offset_start_days": 3, "duration_days": 5, "is_milestone": False, "depends_on": [2]},
            {"title": "Interference & clamp check", "type": "CAD", "priority": "Medium", "effort": 4, "offset_start_days": 8, "duration_days": 1, "is_milestone": False, "depends_on": [3]},
            {"title": "Fabrication 2D drawings", "type": "2D CAD", "priority": "High", "effort": 10, "offset_start_days": 9, "duration_days": 3, "is_milestone": False, "depends_on": [4]},
            {"title": "BOM & hardware list", "type": "Tools", "priority": "Medium", "effort": 3, "offset_start_days": 11, "duration_days": 1, "is_milestone": False, "depends_on": [5]},
            {"title": "Tooling review & release", "type": "Tools", "priority": "High", "effort": 2, "offset_start_days": 12, "duration_days": 1, "is_milestone": False, "depends_on": [6]},
            {"title": "Shop tryout / buyoff", "type": "Tools", "priority": "High", "effort": 4, "offset_start_days": 13, "duration_days": 0, "is_milestone": True, "depends_on": [7]},
        ],
    },
    {
        "id": "cam-product",
        "name": "CAM Produk",
        "description": "Stock/setup → rough → finish → simulation → post → first article",
        "tasks": [
            {"title": "CAM job intake (model & material)", "type": "CAM", "priority": "High", "effort": 2, "offset_start_days": 0, "duration_days": 1, "is_milestone": False, "depends_on": []},
            {"title": "Stock, WCS & fixture setup", "type": "CAM", "priority": "High", "effort": 4, "offset_start_days": 1, "duration_days": 1, "is_milestone": False, "depends_on": [0]},
            {"title": "Roughing toolpaths", "type": "CAM", "priority": "High", "effort": 8, "offset_start_days": 2, "duration_days": 2, "is_milestone": False, "depends_on": [1]},
            {"title": "Finishing toolpaths", "type": "CAM", "priority": "High", "effort": 10, "offset_start_days": 4, "duration_days": 3, "is_milestone": False, "depends_on": [2]},
            {"title": "Toolpath simulation / collision check", "type": "CAM", "priority": "High", "effort": 4, "offset_start_days": 7, "duration_days": 1, "is_milestone": False, "depends_on": [3]},
            {"title": "Post-process NC code", "type": "CAM", "priority": "High", "effort": 2, "offset_start_days": 8, "duration_days": 1, "is_milestone": False, "depends_on": [4]},
            {"title": "NC package release", "type": "CAM", "priority": "High", "effort": 1, "offset_start_days": 9, "duration_days": 0, "is_milestone": True, "depends_on": [5]},
            {"title": "First-article / prove-out support", "type": "Tools", "priority": "Medium", "effort": 4, "offset_start_days": 9, "duration_days": 2, "is_milestone": False, "depends_on": [6]},
        ],
    },
    {
        "id": "setup-inspection",
        "name": "Setup & Inspection",
        "description": "Setup sheet → workholding → in-process check → final insp → report",
        "tasks": [
            {"title": "Setup sheet & operation plan", "type": "Tools", "priority": "High", "effort": 3, "offset_start_days": 0, "duration_days": 1, "is_milestone": False, "depends_on": []},
            {"title": "Workholding / fixture confirm", "type": "Tools", "priority": "High", "effort": 2, "offset_start_days": 1, "duration_days": 1, "is_milestone": False, "depends_on": [0]},
            {"title": "Tool list & offsets", "type": "Tools", "priority": "Medium", "effort": 2, "offset_start_days": 1, "duration_days": 1, "is_milestone": False, "depends_on": [0]},
            {"title": "Machine setup ready", "type": "Tools", "priority": "High", "effort": 1, "offset_start_days": 2, "duration_days": 0, "is_milestone": True, "depends_on": [1, 2]},
            {"title": "In-process inspection points", "type": "Tools", "priority": "High", "effort": 3, "offset_start_days": 2, "duration_days": 1, "is_milestone": False, "depends_on": [3]},
            {"title": "Final inspection", "type": "Tools", "priority": "High", "effort": 4, "offset_start_days": 3, "duration_days": 1, "is_milestone": False, "depends_on": [4]},
            {"title": "Inspection report & sign-off", "type": "Tools", "priority": "High", "effort": 2, "offset_start_days": 4, "duration_days": 0, "is_milestone": True, "depends_on": [5]},
        ],
    },
    {
        "id": "2d-drawing-pack",
        "name": "2D Drawing Pack (Short)",
        "description": "Compact drawing set — layout, detail, check, release",
        "tasks": [
            {"title": "Drawing package kickoff", "type": "Tools", "priority": "Medium", "effort": 1, "offset_start_days": 0, "duration_days": 0, "is_milestone": True, "depends_on": []},
            {"title": "Base layout", "type": "2D CAD", "priority": "High", "effort": 6, "offset_start_days": 0, "duration_days": 2, "is_milestone": False, "depends_on": [0]},
            {"title": "Detail drawings", "type": "2D CAD", "priority": "High", "effort": 10, "offset_start_days": 2, "duration_days": 4, "is_milestone": False, "depends_on": [1]},
            {"title": "Drawing check", "type": "Tools", "priority": "Medium", "effort": 3, "offset_start_days": 6, "duration_days": 1, "is_milestone": False, "depends_on": [2]},
            {"title": "Release package", "type": "Tools", "priority": "High", "effort": 2, "offset_start_days": 7, "duration_days": 0, "is_milestone": True, "depends_on": [3]},
        ],
    },
    {
        "id": "new-product",
        "name": "New Product",
        "description": "End-to-end: requirement → 2D → 3D → review → CAM → handoff (mechanical cad-cam basis)",
        "tasks": [
            {"title": "Kickoff & requirement freeze", "type": "Tools", "priority": "High", "effort": 2, "offset_start_days": 0, "duration_days": 0, "is_milestone": True, "depends_on": []},
            {"title": "2D layout / drawing", "type": "2D CAD", "priority": "High", "effort": 8, "offset_start_days": 0, "duration_days": 3, "is_milestone": False, "depends_on": [0]},
            {"title": "3D model", "type": "CAD", "priority": "High", "effort": 16, "offset_start_days": 3, "duration_days": 5, "is_milestone": False, "depends_on": [1]},
            {"title": "Design review", "type": "Tools", "priority": "Medium", "effort": 4, "offset_start_days": 8, "duration_days": 1, "is_milestone": False, "depends_on": [2]},
            {"title": "CAM toolpath", "type": "CAM", "priority": "High", "effort": 12, "offset_start_days": 9, "duration_days": 4, "is_milestone": False, "depends_on": [3]},
            {"title": "NC verify & handoff", "type": "CAM", "priority": "High", "effort": 4, "offset_start_days": 13, "duration_days": 0, "is_milestone": True, "depends_on": [4]},
        ],
    },
    {
        "id": "milestone-task",
        "name": "Milestone Task",
        "description": "Template untuk milestone task",
        "tasks": [
            {"title": "Milestone 1", "type": "Tools", "priority": "High", "effort": 1, "offset_start_days": 0, "duration_days": 0, "is_milestone": True, "depends_on": []},
            {"title": "Milestone 2", "type": "Tools", "priority": "High", "effort": 1, "offset_start_days": 7, "duration_days": 0, "is_milestone": True, "depends_on": [0]},
            {"title": "Milestone 3", "type": "Tools", "priority": "High", "effort": 1, "offset_start_days": 14, "duration_days": 0, "is_milestone": True, "depends_on": [1]},
        ],
    },
]
