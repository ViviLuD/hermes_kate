#!/opt/hermes/.venv/bin/python3
"""
MemPalace Search Index — Layer 1 of Progressive Disclosure.
Returns compact search results: IDs + wing:room + 80-char preview.
Token cost: ~80-120 tokens vs ~1000+ for full drawer content (~90% savings).

Usage:
  # Quick semantic search
  ./mempalace_search_index.py --query "quantum IP France"

  # Filter by wing and room
  ./mempalace_search_index.py --query "brevet" --room ip_strategy --limit 15

  # Strict matching (lower cosine distance = more relevant)
  ./mempalace_search_index.py --query "trade secret" --max-distance 0.8

  # JSON output for piping
  ./mempalace_search_index.py --query "licensing" --json

  # List distinct wings/rooms
  ./mempalace_search_index.py --list-rooms
"""

import argparse
import json
import sys
import os

# Ensure we use Hermes venv Chroma
CHROMA_PATH = "/opt/data/mempalace"


def get_client():
    import chromadb
    return chromadb.PersistentClient(path=CHROMA_PATH)


def list_rooms():
    """List all distinct wing:room combinations."""
    client = get_client()
    coll = client.get_collection("mempalace_drawers")
    count = coll.count()
    
    # Use query to get a broader sample
    wings_rooms = {}
    results = coll.get(include=["metadatas"], limit=min(count, 5000))
    if results.get("metadatas"):
        for m in results["metadatas"]:
            w = m.get("wing", "?")
            r = m.get("room", "?")
            key = f"{w}:{r}"
            wings_rooms[key] = wings_rooms.get(key, 0) + 1
    
    print(f"Total drawers: {count}")
    print(f"\n{'#':<4} {'Wing:Room':<50} {'Count':<8}")
    print("-" * 65)
    for i, (loc, cnt) in enumerate(sorted(wings_rooms.items(), key=lambda x: -x[1]), 1):
        print(f"{i:<4} {loc:<50} {cnt:<8}")
    return list(wings_rooms.keys())


def format_preview(text: str, max_len: int = 80) -> str:
    cleaned = text.replace("\n", " ").replace("\r", " ").strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[:max_len-3] + "..."


def search_index(query: str, wing: str = None, room: str = None,
                 limit: int = 10, max_distance: float = 1.5) -> list:
    """Layer 1: Compact semantic search index."""
    client = get_client()
    coll = client.get_collection("mempalace_drawers")

    # Build where filter
    where_filter = {}
    if wing and room:
        where_filter = {"$and": [{"wing": wing}, {"room": room}]}
    elif wing:
        where_filter = {"wing": wing}
    elif room:
        where_filter = {"room": room}

    # Query with nested filter handling
    where = where_filter if where_filter else None

    results = coll.query(
        query_texts=[query],
        n_results=limit,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    index = []
    if results.get("ids") and results["ids"][0]:
        ids = results["ids"][0]
        docs = results["documents"][0] if results.get("documents") else []
        metas = results["metadatas"][0] if results.get("metadatas") else []
        dists = results["distances"][0] if results.get("distances") else []

        for i in range(len(ids)):
            meta = metas[i] if i < len(metas) else {}
            dist = dists[i] if i < len(dists) else None
            doc = docs[i] if i < len(docs) else ""

            # Compute similarity (1 - distance/2 for cosine dist in [0,2])
            similarity = max(0, 1.0 - (dist / 2.0)) if dist is not None else None

            # Skip if distance exceeds max
            if dist is not None and dist > max_distance:
                continue

            index.append({
                "idx": i + 1,
                "id": ids[i],
                "wing": meta.get("wing", "?"),
                "room": meta.get("room", "?"),
                "loc": f"{meta.get('wing', '?')}:{meta.get('room', '?')}",
                "preview": format_preview(doc),
                "distance": round(dist, 4) if dist is not None else None,
                "similarity": round(similarity, 4) if similarity is not None else None,
            })

    return index


def print_index_table(index: list):
    if not index:
        print("(no results)")
        return

    print(f"{'#':<4} {'ID':<14} {'Location':<35} {'Sim':<6} {'Preview'}")
    print("-" * 130)
    for entry in index:
        sim = f"{entry['similarity']:.2f}" if entry['similarity'] else "?"
        eid = entry['id']
        if len(eid) > 13:
            eid = eid[:12] + "…"
        print(f"{entry['idx']:<4} {eid:<14} {entry['loc']:<35} {sim:<6} {entry['preview']}")

    print(f"\n{'─' * 20}")
    print(f"{len(index)} résultat(s)")
    print("Layer 2 → mempalace_timeline.py --ids <ids> (contexte chronologique)")
    print("Layer 3 → mempalace_get_drawer({'drawer_id': '<ID>'}) (contenu complet)")


def print_json(index: list):
    print(json.dumps(index, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(
        description="MemPalace Search Index — Layer 1: search results compacts"
    )
    parser.add_argument("--query", "-q", help="Requête sémantique")
    parser.add_argument("--wing", "-w", help="Filtrer par wing")
    parser.add_argument("--room", "-r", help="Filtrer par room")
    parser.add_argument("--limit", "-l", type=int, default=10, help="Max résultats (défaut: 10)")
    parser.add_argument("--max-distance", "-d", type=float, default=1.5,
                        help="Distance cosinus max (défaut: 1.5, plus bas = plus strict)")
    parser.add_argument("--json", "-j", action="store_true", help="Sortie JSON")
    parser.add_argument("--list-rooms", action="store_true", help="Lister les wing:room disponibles")

    args = parser.parse_args()

    if args.list_rooms:
        list_rooms()
        return

    if not args.query:
        parser.print_help()
        sys.exit(1)

    index = search_index(
        query=args.query,
        wing=args.wing,
        room=args.room,
        limit=args.limit,
        max_distance=args.max_distance,
    )

    if args.json:
        print_json(index)
    else:
        print_index_table(index)


if __name__ == "__main__":
    main()
