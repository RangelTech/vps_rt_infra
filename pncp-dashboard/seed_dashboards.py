"""Idempotent Metabase seed for the two public dashboards (PNCP procurement, SIOPE education spending).

Registers the public Postgres as a Metabase database (read-only role), creates native SQL questions over the
small aggregate views in schema `bi` and over the SIOPE tables, builds two dashboards, enables their public
links and prints the UUIDs. Standard library only; secrets come from the environment and are never printed.

Environment: MB_URL, METABASE_ADMIN_EMAIL, METABASE_ADMIN_PASSWORD, PG_HOST, PG_DB, PG_USER, PG_PASSWORD.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DB_NAME = "Public catalogue (Postgres)"
CUTOFF = os.environ.get("PNCP_CUTOFF", "2026-07-31")

PNCP_CARDS = [
    ("PNCP notices published per month", "line", "SELECT month, notices FROM bi.pncp_notices_by_month ORDER BY month"),
    ("PNCP notices by modality", "bar", "SELECT modality, notices FROM bi.pncp_by_modality LIMIT 12"),
    ("PNCP notices by state", "bar", "SELECT uf, notices FROM bi.pncp_by_uf ORDER BY notices DESC LIMIT 27"),
    ("PNCP notices by category", "bar", "SELECT category, notices FROM bi.pncp_by_category LIMIT 15"),
    ("PNCP estimated value by year (BRL, notice level)", "bar", "SELECT year::text AS year, estimated_value_brl FROM bi.pncp_value_by_year ORDER BY year"),
    ("PNCP top contracting organizations", "row", "SELECT organization, notices FROM bi.pncp_top_organizations ORDER BY notices DESC LIMIT 15"),
    ("PNCP notices by status", "bar", "SELECT status, notices FROM bi.pncp_by_status LIMIT 10"),
]
PNCP_LAYOUT = [(0, 0, 24, 7), (7, 0, 12, 8), (7, 12, 12, 8), (15, 0, 12, 8), (15, 12, 12, 8), (23, 0, 12, 9), (23, 12, 12, 9)]

SIOPE_CARDS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "siope_cards.json"), encoding="utf-8"))
SIOPE_LAYOUT = [(0, 0, 12, 8), (0, 12, 12, 8), (8, 0, 12, 8), (8, 12, 12, 8)]


class Metabase:
    def __init__(self, base: str) -> None:
        self.base, self.session = base.rstrip("/"), None

    def call(self, method: str, path: str, body: Any = None) -> Any:
        headers = {"Content-Type": "application/json"}
        if self.session:
            headers["X-Metabase-Session"] = self.session
        request = Request(self.base + path, json.dumps(body).encode() if body is not None else None, headers, method=method)
        try:
            with urlopen(request, timeout=120) as response:
                raw = response.read()
        except HTTPError as error:
            raise SystemExit(f"{method} {path}: HTTP {error.code} {error.read()[:300].decode('utf-8', 'replace')}") from None
        return json.loads(raw) if raw else None


def env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"missing {name}")
    return value


def wait_healthy(mb: Metabase) -> None:
    for _ in range(40):
        try:
            with urlopen(mb.base + "/api/health", timeout=5) as r:
                if json.loads(r.read()).get("status") == "ok":
                    return
        except (URLError, HTTPError, OSError, ValueError):
            pass
        time.sleep(5)
    raise SystemExit("Metabase not healthy")


def ensure_database(mb: Metabase) -> int:
    listing = mb.call("GET", "/api/database")
    for db in listing["data"] if isinstance(listing, dict) else listing:
        if db["name"] == DB_NAME:
            return db["id"]
    created = mb.call("POST", "/api/database", {
        "engine": "postgres", "name": DB_NAME, "is_full_sync": False, "is_on_demand": False,
        "details": {"host": env("PG_HOST"), "port": 5432, "dbname": env("PG_DB"), "user": env("PG_USER"),
                    "password": env("PG_PASSWORD"), "ssl": False}})
    return created["id"]


def ensure_card(mb: Metabase, db_id: int, existing: list, name: str, display: str, sql: str) -> int:
    body = {"name": name, "display": display, "description": "Seed pncp-siope-dashboards-v1.",
            "visualization_settings": {}, "dataset_query": {"type": "native", "database": db_id, "native": {"query": sql}}}
    card = next((c for c in existing if c.get("name") == name and not c.get("archived")), None)
    if card:
        mb.call("PUT", f"/api/card/{card['id']}", body)
        return card["id"]
    return mb.call("POST", "/api/card", body)["id"]


def ensure_dashboard(mb: Metabase, name: str, description: str, banner: str, card_ids: list[int], layout: list) -> str:
    dashboards = mb.call("GET", "/api/dashboard?f=all")
    dash = next((d for d in dashboards if d.get("name") == name and not d.get("archived")), None)
    if dash is None:
        dash = mb.call("POST", "/api/dashboard", {"name": name, "description": description})
    offset = 3
    dashcards = [{"id": -1, "card_id": None, "row": 0, "col": 0, "size_x": 24, "size_y": 3, "parameter_mappings": [],
                  "visualization_settings": {"virtual_card": {"name": None, "display": "text", "visualization_settings": {},
                                                               "dataset_query": {}, "archived": False}, "text": banner}}]
    for i, (card_id, (row, col, w, h)) in enumerate(zip(card_ids, layout)):
        dashcards.append({"id": -(i + 2), "card_id": card_id, "row": row + offset, "col": col, "size_x": w, "size_y": h,
                          "parameter_mappings": [], "visualization_settings": {}})
    mb.call("PUT", f"/api/dashboard/{dash['id']}", {"dashcards": dashcards})
    try:
        return mb.call("POST", f"/api/dashboard/{dash['id']}/public_link", {})["uuid"]
    except SystemExit:
        return mb.call("GET", f"/api/dashboard/{dash['id']}")["public_uuid"]


def main() -> None:
    mb = Metabase(env("MB_URL"))
    wait_healthy(mb)
    mb.session = mb.call("POST", "/api/session", {"username": env("METABASE_ADMIN_EMAIL"), "password": env("METABASE_ADMIN_PASSWORD")})["id"]
    db_id = ensure_database(mb)
    mb.call("POST", f"/api/database/{db_id}/sync_schema", {})
    existing = mb.call("GET", "/api/card?f=all")
    pncp_ids = [ensure_card(mb, db_id, existing, n, d, q) for n, d, q in PNCP_CARDS]
    uuid = ensure_dashboard(
        mb, "PNCP public procurement", "Aggregates over the PNCP notices, cutoff " + CUTOFF, (
            f"**Scope:** every notice in the public PNCP catalogue with data through {CUTOFF}. Counts describe the released records only "
            "and do not certify current procurement status. Values are shown as published, including implausible estimated values, which dominate the sums by year; each notice is counted once."),
        pncp_ids, PNCP_LAYOUT)
    print(f"pncp_dashboard_uuid={uuid}")
    if SIOPE_CARDS:
        existing = mb.call("GET", "/api/card?f=all")
        ids = [ensure_card(mb, db_id, existing, c["name"], c["display"], c["sql"]) for c in SIOPE_CARDS]
        uuid = ensure_dashboard(
            mb, "SIOPE education spending", "Municipal education finance declarations (SIOPE/FNDE)", (
                "**Scope:** municipal education budget declarations published through SIOPE (FNDE), joined to IBGE municipality codes. "
                "Values are declared amounts in BRL, nominal, not adjusted for inflation. Each municipality counts once per year, using the latest reporting period it filed; 2025 is a partial year."), ids, SIOPE_LAYOUT[: len(ids)])
        print(f"siope_dashboard_uuid={uuid}")


if __name__ == "__main__":
    main()
