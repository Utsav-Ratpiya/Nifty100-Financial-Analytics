"""src/api/routers/peers.py — GET /api/v1/peers/{group_name} (Day 40)."""
from fastapi import APIRouter, Depends, HTTPException

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # -> src/api/, so 'services' resolves

import services

router = APIRouter()


def _db():
    conn = services.get_connection()
    try:
        yield conn
    finally:
        conn.close()


@router.get("/peers/{group_name}")
def get_peer_group(group_name: str, conn=Depends(_db)):
    """All companies in a peer group (one of the 11 groups in
    peer_groups.xlsx — e.g. 'IT Services', 'Private Banks') with their
    percentile rank for each of the 10 tracked metrics. 404 for an unknown
    group name."""
    result = services.get_peer_group(conn, group_name)
    if result is None:
        raise HTTPException(status_code=404, detail=f"unknown peer group: {group_name}")
    return result
