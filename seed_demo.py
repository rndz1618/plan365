#!/usr/bin/env python3
"""Seed demo data for Plan365 (Design & Engineering / CAD-CAM).

Run: python seed_demo.py

Works with:
  - SQLite (default) — PLAN365_DB path
  - PostgreSQL — PLAN365_DB_BACKEND=postgresql + PLAN365_DATABASE_URL

Safe to re-run: re-seeds tasks for the 3 demo projects.
"""
from datetime import date, timedelta

from app.auth_utils import hash_pw
from app.database import db, init_db


def main():
    init_db()
    today = date.today()

    with db() as c:
        admin = c.execute("SELECT id FROM users WHERE username=?", ("admin",)).fetchone()
        if not admin:
            cur = c.execute(
                "INSERT INTO users (username,email,hashed_password,full_name,role) VALUES (?,?,?,?,?)",
                ("admin", "admin@plan365.local", hash_pw("admin123"), "Administrator", "admin"),
            )
            admin_id = cur.lastrowid
        else:
            admin_id = admin["id"]

        user_ids = {"admin": admin_id}
        for username, email, full_name in [
            ("andi", "andi@plan365.local", "Andi Pratama"),
            ("sari", "sari@plan365.local", "Sari Wijaya"),
            ("budi", "budi@plan365.local", "Budi Santoso"),
        ]:
            existing = c.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
            if existing:
                user_ids[username] = existing["id"]
            else:
                cur = c.execute(
                    "INSERT INTO users (username,email,hashed_password,full_name,role) VALUES (?,?,?,?,?)",
                    (username, email, hash_pw("password123"), full_name, "user"),
                )
                uid = cur.lastrowid
                user_ids[username] = uid
                c.execute("INSERT OR IGNORE INTO user_preferences (user_id) VALUES (?)", (uid,))

        projects_data = [
            ("Hydraulic Pump Housing", "3D CAD, 2D drawings, CAM for aluminum pump housing.", "#3b82f6", [
                ("Import customer STEP & clean geometry", "CAD", "Done", "High", -14, -10, 100, "andi"),
                ("Design mounting flange features", "CAD", "Done", "High", -10, -5, 100, "andi"),
                ("Create 2D detail drawing sheet 1", "2D CAD", "Review", "Medium", -3, 2, 80, "sari"),
                ("Create 2D section views & GD&T", "2D CAD", "In Progress", "High", 0, 5, 40, "sari"),
                ("CAM roughing strategy (face + pocket)", "CAM", "Todo", "High", 3, 8, 0, "budi"),
                ("CAM finishing & toolpath simulation", "CAM", "Todo", "Medium", 6, 12, 0, "budi"),
                ("Design inspection fixture", "Tools", "Todo", "Low", 8, 15, 0, "andi"),
                ("BOM & material order note", "Others", "Done", "Low", -12, -11, 100, "admin"),
            ]),
            ("CNC Fixture – Batch 24", "Modular fixture for stainless bracket series.", "#10b981", [
                ("Concept sketch modular base plate", "CAD", "Done", "Medium", -20, -15, 100, "andi"),
                ("3D model clamp assemblies", "CAD", "In Progress", "High", -5, 3, 55, "andi"),
                ("2D layout drawing for shop floor", "2D CAD", "Todo", "Medium", 2, 7, 0, "sari"),
                ("CAM for base plate (3-axis)", "CAM", "Todo", "High", 5, 10, 0, "budi"),
                ("Design locating pins & bushings", "Tools", "Review", "Medium", -2, 1, 90, "andi"),
                ("Handoff pack to production", "Others", "Handoff", "High", 10, 12, 0, "admin"),
            ]),
            ("Gearbox Cover Redesign", "Weight reduction + improved sealing.", "#f59e0b", [
                ("Benchmark existing cover mass & stress", "CAD", "Done", "High", -25, -18, 100, "andi"),
                ("Topology concept A/B", "CAD", "Done", "High", -18, -12, 100, "andi"),
                ("Detailed 3D ribbing & seal groove", "CAD", "In Progress", "High", -4, 4, 60, "andi"),
                ("2D manufacturing drawing set", "2D CAD", "Todo", "Medium", 4, 10, 0, "sari"),
                ("CAM 5-axis finishing trial", "CAM", "Blocked", "High", 8, 14, 10, "budi"),
                ("Prototype toolpath review meeting", "Others", "Todo", "Medium", 7, 8, 0, "admin"),
                ("Design assembly jig for cover", "Tools", "Todo", "Low", 12, 18, 0, "andi"),
            ]),
        ]

        for name, desc, color, tasks in projects_data:
            existing = c.execute("SELECT id FROM projects WHERE name=?", (name,)).fetchone()
            if existing:
                pid = existing["id"]
                c.execute("DELETE FROM tasks WHERE project_id=?", (pid,))
            else:
                cur = c.execute(
                    "INSERT INTO projects (name,description,color,created_by) VALUES (?,?,?,?)",
                    (name, desc, color, admin_id),
                )
                pid = cur.lastrowid
            for uname, role in [("admin", "owner"), ("andi", "editor"), ("sari", "editor"), ("budi", "editor")]:
                c.execute(
                    "INSERT OR IGNORE INTO project_members (project_id,user_id,role) VALUES (?,?,?)",
                    (pid, user_ids[uname], role),
                )
            for title, typ, status, priority, so, do, prog, assignee in tasks:
                c.execute(
                    """INSERT INTO tasks (project_id,title,type,status,priority,start_date,due_date,progress,assignee_id,created_by,labels)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        pid, title, typ, status, priority,
                        (today + timedelta(days=so)).isoformat(),
                        (today + timedelta(days=do)).isoformat(),
                        prog, user_ids[assignee], admin_id, "[]",
                    ),
                )

        n_proj = c.execute("SELECT COUNT(*) AS n FROM projects").fetchone()["n"]
        n_task = c.execute("SELECT COUNT(*) AS n FROM tasks").fetchone()["n"]
        print(f"Seed OK: {n_proj} projects, {n_task} tasks")
        print("Users: admin/admin123 | andi,sari,budi / password123")


if __name__ == "__main__":
    main()
