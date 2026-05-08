#!/opt/hermes/.venv/bin/python3
"""
MemPalace Timeline — Layer 2 of Progressive Disclosure.
Shows chronological context around a specific drawer or query result.

Usage:
  # Timeline for a specific drawer ID
  ./mempalace_timeline.py --id flatmem_hermes_memory_01_48df6fe4dd75

  # Timeline for recent content in a room
  ./mempalace_timeline.py --room ip_strategy --limit 20

  # Timeline with cross-room tunnel context
  ./mempalace_timeline.py --id <id> --expand-tunnels

  # Combined: query then timeline on first result
  ./mempalace_search_index.py --query "quantum" --json | \
    python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['id'] if d else '')" | \
    xargs -r ./mempalace_timeline.py --id
"""

import argparse
import json
import subprocess
import sys

CHROMA_PATH = "/opt/data/mempalace"


def get_client():
    import chromadb
    return chromadb.PersistentClient(path=CHROMA_PATH)


def format_preview(text: str, max_len: int = 100) -> str:
    cleaned = text.replace("\n", " ").replace("\r", " ").strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[:max_len-3] + "..."


def get_timeline_for_id(drawer_id: str, limit: int = 20):
    """Get chronological context for a specific drawer."""
    client = get_client()
    coll = client.get_collection("mempalace_drawers")

    # First, get the target drawer's metadata
    target = coll.get(
        ids=[drawer_id],
        include=["documents", "metadatas"],
    )

    if not target.get("ids"):
        return {"error": f"Drawer '{drawer_id}' not found", "target": None, "timeline": []}

    meta = target["metadatas"][0] if target.get("metadatas") else {}
    doc = target["documents"][0] if target.get("documents") else ""
    wing = meta.get("wing", "?")
    room = meta.get("room", "?")

    # Get all drawers in the same wing:room (timeline context)
    same_room = coll.get(
        where={"$and": [{"wing": wing}, {"room": room}]},
        include=["documents", "metadatas"],
        limit=limit,
    )

    # Build timeline — Chroma returns in insertion order, we sort by chunk_index or id
    timeline = []
    if same_room.get("ids"):
        for i in range(len(same_room["ids"])):
            m = same_room["metadatas"][i] if same_room.get("metadatas") else {}
            d = same_room["documents"][i] if same_room.get("documents") else ""
            tid = same_room["ids"][i]
            timeline.append({
                "id": tid,
                "preview": format_preview(d),
                "chunk_index": m.get("chunk_index", 0),
                "source": m.get("source", "?"),
                "is_target": tid == drawer_id,
            })

    # Sort by chunk_index if available, otherwise by id
    timeline.sort(key=lambda x: (
        x["chunk_index"] if isinstance(x["chunk_index"], (int, float)) else 0
    ))

    return {
        "target": {
            "id": drawer_id,
            "location": f"{wing}:{room}",
            "preview": format_preview(doc, 200),
        },
        "timeline": timeline,
    }


def get_timeline_for_room(wing: str, room: str, limit: int = 50):
    """Get timeline for all content in a wing:room."""
    client = get_client()
    coll = client.get_collection("mempalace_drawers")

    results = coll.get(
        where={"$and": [{"wing": wing}, {"room": room}]},
        include=["documents", "metadatas"],
        limit=limit,
    )

    timeline = []
    if results.get("ids"):
        for i in range(len(results["ids"])):
            m = results["metadatas"][i] if results.get("metadatas") else {}
            d = results["documents"][i] if results.get("documents") else ""
            timeline.append({
                "id": results["ids"][i],
                "preview": format_preview(d),
                "chunk_index": m.get("chunk_index", 0),
                "source": m.get("source", "?"),
            })

    timeline.sort(key=lambda x: (
        x["chunk_index"] if isinstance(x["chunk_index"], (int, float)) else 0
    ))

    return {
        "room": f"{wing}:{room}",
        "total": len(timeline),
        "timeline": timeline,
    }


def print_timeline(data: dict):
    if data.get("error"):
        print(f"ERREUR: {data['error']}")
        return

    if "target" in data and data["target"]:
        t = data["target"]
        print(f"═══ DRAWER CIBLE ═══")
        print(f"  ID:       {t['id']}")
        print(f"  Location: {t['location']}")
        print(f"  Preview:  {t['preview']}")
        print()

    location = data.get("room") or data.get("target", {}).get("location", "?")
    timeline = data.get("timeline", [])
    
    print(f"═══ TIMELINE — {location} ═══")
    print(f"  {len(timeline)} drawer(s) dans ce room")
    print()
    
    print(f"{'#':<4} {'ID':<14} {'Source':<18} {'Preview'}")
    print("-" * 110)
    for i, entry in enumerate(timeline):
        eid = entry["id"]
        if len(eid) > 13:
            eid = eid[:12] + "…"
        marker = " ← CIBLE" if entry.get("is_target") else " "
        source = entry.get("source", "?")[:17]
        print(f"{i+1:<4} {eid:<14} {source:<18} {entry['preview']}{marker}")

    print(f"\n{'─' * 20}")
    print("Layer 3 → mempalace_get_drawer({'drawer_id': '<ID>'}) pour contenu complet")
    print("Cross-room → mempalace_follow_tunnels({'wing': '<wing>', 'room': '<room>'})")


def main():
    parser = argparse.ArgumentParser(
        description="MemPalace Timeline — Layer 2: contexte chronologique"
    )
    parser.add_argument("--id", help="ID du drawer cible")
    parser.add_argument("--wing", "-w", default="benjamin_delsol", help="Wing (défaut: benjamin_delsol)")
    parser.add_argument("--room", "-r", help="Room pour timeline complète")
    parser.add_argument("--limit", "-l", type=int, default=20, help="Max entrées (défaut: 20)")
    parser.add_argument("--json", "-j", action="store_true", help="Sortie JSON")

    args = parser.parse_args()

    if args.id:
        data = get_timeline_for_id(args.id, limit=args.limit)
    elif args.room:
        data = get_timeline_for_room(args.wing, args.room, limit=args.limit)
    else:
        parser.print_help()
        sys.exit(1)

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print_timeline(data)


if __name__ == "__main__":
    main()
