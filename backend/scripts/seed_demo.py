"""Drive five very different users through three sessions each, over the HTTP API.

Everything lands in Neo4j and MongoDB exactly as a real user would leave it, so the
frontend shows five distinct brains rather than one synthetic-looking graph.

    python scripts/seed_demo.py [--api http://localhost:8000] [--model ...]
"""
import argparse, json, sys, time

import httpx

MODEL = "deepseek-v4.1-flash:cloud"

# Five lives that pull on different parts of the graph: career, health, money,
# family/education, and spiritual/relocation. Different languages and life stages too.
PROFILES = [
    {
        "user_id": "rahul", "name": "Rahul Menon", "dob": "1995-08-15", "tob": "04:30",
        "birth_place": "Delhi", "language": "English",
        "blurb": "30, software engineer, mid-career itch",
        "sessions": [
            ["I am a software engineer in Bangalore and I have been at the same company for six years.",
             "I am planning to switch jobs next year, ideally into product management.",
             "What should I focus on for my career?",
             "Why do you say that?"],
            ["What do you remember about my career goals?",
             "I had a product management interview last week and it went badly.",
             "Should I keep trying for PM roles or stay technical?"],
            ["Actually I have decided to stay technical and go for a staff engineer role instead.",
             "Does that change what my chart suggests?",
             "What should I focus on for the next six months?"],
        ],
    },
    {
        "user_id": "meera", "name": "Meera Nair", "dob": "1992-06-21", "tob": "19:10",
        "birth_place": "Kochi", "language": "English",
        "blurb": "34, doctor, health and burnout",
        "sessions": [
            ["I am a doctor working night shifts and I have a chronic back problem.",
             "I enjoy long distance running but I have not run in months.",
             "How is my health looking this year?"],
            ["What do you remember about my health?",
             "I am thinking of moving to a day-shift role to protect my sleep.",
             "Is this a good year for that kind of change?"],
            ["I started running again three times a week.",
             "I am also planning to get married next year.",
             "How do I balance my work, health and marriage?"],
        ],
    },
    {
        "user_id": "arjun", "name": "Arjun Shetty", "dob": "1999-02-03", "tob": "11:45",
        "birth_place": "Mumbai", "language": "English",
        "blurb": "27, founder, money and risk",
        "sessions": [
            ["I run a small logistics startup in Mumbai and I am the only earning member at home.",
             "I am interested in entrepreneurship and I want to raise funding this year.",
             "What do the stars say about my finances?"],
            ["What do you remember about my business?",
             "An investor offered a term sheet but the valuation is low.",
             "Should I take money at a low valuation or wait?"],
            ["I turned down the offer and I am bootstrapping instead.",
             "I am saving up to buy a house by 2028.",
             "Is property a good idea for me?"],
        ],
    },
    {
        "user_id": "priya", "name": "Priya Sharma", "dob": "1984-11-27", "tob": "06:20",
        "birth_place": "Lucknow", "language": "Hindi",
        "blurb": "41, teacher, family and study",
        "sessions": [
            ["I prefer replies in Hindi.",
             "I am a school teacher in Lucknow, married with one daughter.",
             "I am studying part time for an MBA so I can move into school administration.",
             "How will my studies go this year?"],
            ["What do you remember about my studies?",
             "My daughter is starting class ten and I am worried about her exams.",
             "How is my family life looking?"],
            ["I finished my first year of the MBA with good marks.",
             "Should I apply for a principal role now or wait until I finish?"],
        ],
    },
    {
        "user_id": "vikram", "name": "Vikram Rao", "dob": "1988-11-02", "tob": "23:05",
        "birth_place": "Chennai", "language": "English",
        "blurb": "37, ex-army consultant, relocation and meaning",
        "sessions": [
            ["I left the army two years ago and now I consult on logistics.",
             "I live in Delhi but my family is in Chennai.",
             "I meditate every morning and I read a lot about vedic astrology myself.",
             "What should I focus on spiritually this year?"],
            ["Actually I am moving to Bangalore next month for a new contract.",
             "What do you remember about where I live?",
             "Where should I settle down long term?"],
            ["I lost my father in March and I have been thinking about purpose a lot.",
             "Is this a good time for a bigger life change?",
             "What does my chart say about the next two years?"],
        ],
    },
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--reset", action="store_true", help="clear each user's memories first")
    args = ap.parse_args()

    c = httpx.Client(base_url=args.api, timeout=180)
    c.get("/health").raise_for_status()
    t0, turns = time.time(), 0

    for p in PROFILES:
        uid = p["user_id"]
        if args.reset:
            c.delete(f"/users/{uid}/memory")
        c.post("/users", json={k: p[k] for k in
                               ("user_id", "name", "dob", "tob", "birth_place", "language")})
        print(f"\n=== {p['name']}  ({p['blurb']}) ===", flush=True)

        for i, session in enumerate(p["sessions"], 1):
            sid = f"{uid}-s{i}"
            print(f"  session {sid}", flush=True)
            for msg in session:
                r = c.post("/chat", json={"user_id": uid, "session_id": sid,
                                          "message": msg, "provider": "ollama",
                                          "model": args.model})
                r.raise_for_status()
                d = r.json()
                turns += 1
                steps = {s["step"]: s for s in d["trace"]["steps"]}
                stored = [x["action"] for x in steps["update_memory"]["decisions"]
                          if x["action"] != "DISCARD"]
                print(f"    > {msg[:58]:60} ctx={len(d['context_used'])} "
                      f"{'+' + ','.join(stored) if stored else ''}", flush=True)

        g = c.get(f"/users/{uid}/brain").json()
        mem = [n for n in g["nodes"] if n["kind"] == "memory"]
        print(f"  -> {len(mem)} memories, "
              f"{len({n['label'] for n in g['nodes'] if n['kind']=='topic'})} topics", flush=True)

    print(f"\ndone: {len(PROFILES)} users, {turns} turns in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    sys.exit(main())
