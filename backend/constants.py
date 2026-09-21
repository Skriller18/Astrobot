"""All tunable constants, bucketed by where they are used.

Tags: [DERIVED] structural, [JUDGEMENT] reasoned, [PRIOR] tune via evals.
See docs/architecture.md section 8 for the formulas these feed.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# backend/.env -- loaded before anything reads a setting below.
# Real environment variables win over the file, so CI and Docker can override it.
load_dotenv(Path(__file__).parent / ".env", override=False)

# ------------------------------------------------------------- environment
# Every env-derived setting lives here; nothing else in the codebase calls
# os.getenv, so this block is the whole list of what .env can set.
API_KEYS = {
    "openai": os.getenv("OPENAI_API_KEY"),
    "anthropic": os.getenv("ANTHROPIC_API_KEY"),
    "gemini": os.getenv("GEMINI_API_KEY"),
    "openrouter": os.getenv("OPENROUTER_API_KEY"),
}
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
# When set, Ollama Cloud is used instead of the local daemon.
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
OLLAMA_CLOUD_URL = "https://ollama.com"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "astrobot123")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

# "neo4j"/"mongo" to use the real stores, "memory" to force the in-process ones
BRAIN = os.getenv("BRAIN", "neo4j")
SESSIONS = os.getenv("SESSIONS", "mongo")

# default provider when a request does not name one; blank walks the chain
LLM_PROVIDER = os.getenv("LLM_PROVIDER") or None
LLM_FALLBACK = [p.strip() for p in os.getenv("LLM_FALLBACK", "").split(",") if p.strip()]


# ---------------------------------------------------------------- memory types
# half_life in months (None = never decays), cardinality, promotion+retrieval priors
TYPES = {
    "IDENTITY":   {"half_life": None, "single": True,  "util": 1.00, "imp": 1.00},
    "PREFERENCE": {"half_life": 24,   "single": True,  "util": 0.80, "imp": 0.70},
    "ATTRIBUTE":  {"half_life": 18,   "single": True,  "util": 0.85, "imp": 0.80},
    "INTEREST":   {"half_life": 12,   "single": False, "util": 0.60, "imp": 0.60},
    "GOAL":       {"half_life": 9,    "single": False, "util": 0.90, "imp": 0.90},
    "EVENT":      {"half_life": 6,    "single": False, "util": 0.50, "imp": 0.50},
    "STATE":      {"half_life": 0,    "single": False, "util": 0.00, "imp": 0.00},
}
PROMOTABLE = [t for t in TYPES if t != "STATE"]

# life domains the product actually reasons about -> utility.topic_supported
CORE_TOPICS = ["career", "health", "relationships", "finance", "family", "education", "spiritual"]
ADJACENT_TOPICS = ["travel", "lifestyle", "hobbies", "creativity"]

TOPIC_KEYWORDS = {
    "career": "job work career office promotion salary business startup interview role company switch switching resign quit hiring manager",
    "health": "health fitness illness sleep energy diet exercise anxiety stress body",
    "relationships": "relationship marriage partner love spouse dating girlfriend boyfriend",
    "finance": "money finance invest savings loan wealth property debt",
    "family": "family parents mother father children kids siblings home",
    "education": "study exam college degree course learning school university",
    "spiritual": "spiritual meditation puja temple dharma karma astrology horoscope",
    "travel": "travel trip abroad relocate move city shift",
    "lifestyle": "lifestyle food cooking routine habit",
    "hobbies": "hobby music sports reading gaming",
    "creativity": "art writing design painting creative",
}

# ------------------------------------------------------------------- promotion
PROMOTION_WEIGHTS = {"durability": 0.35, "specificity": 0.25, "utility": 0.25, "extraction": 0.15}
PROMOTION_THRESHOLD = 0.55          # [PRIOR] tune first
DURABILITY_HORIZON = 12             # [JUDGEMENT] months
SPECIFICITY_WEIGHTS = {"concrete": 0.45, "qualifier": 0.30, "length": 0.25}
UTILITY_TOPIC_WEIGHT = 0.60
EXTRACTION_WEIGHTS = {"self_report": 0.40, "grounding": 0.40, "slots": 0.20}
VALUE_TOKEN_BAND = (2, 8)

# -------------------------------------------------------------------- matching
# [PRIOR] Calibrated for the hashed bag-of-words embedder in utils.embed, which scores
# a one-word difference around 0.67 -- far below what a semantic model would give.
# Refit BOTH of these when swapping in a real embedding model.
SIM_SAME = 0.85                     # >= this means same meaning -> reinforce
SIM_RELATED = 0.55                  # below this means unrelated -> create

# ------------------------------------------------------------------ confidence
REINFORCE_RATE = 0.15               # [PRIOR] c += rate * (1 - c)
CONTRADICT_FACTOR = 0.70            # [PRIOR] c *= factor
SUPERSEDE_FLOOR = 0.75              # corrections are deliberate, so trusted

# ------------------------------------------------------------------- retrieval
RETRIEVAL_FLOOR = 0.40              # [PRIOR] below this, no context is used
TOP_K = 3
COSINE_BAND = (0.55, 0.95)          # [PRIOR] refit per embedding model
TOPIC_MATCH_SCORES = {"exact": 1.0, "parent": 0.6, "sibling": 0.3, "none": 0.0}

# ------------------------------------------------------------------- follow-up
FOLLOWUP_WEIGHTS = {"no_new_content": 0.40, "anaphora": 0.30, "short": 0.20, "why": 0.10}
FOLLOWUP_THRESHOLD = 0.50
FOLLOWUP_SHORT_TOKENS = 6
ANAPHORA = {"that", "it", "this", "they", "those", "these", "them"}
WHY_OPENERS = ("why", "how come", "explain", "what do you mean", "says who")

# --------------------------------------------------------------- context budget
BUDGET = {"system": 300, "profile": 300, "memories": 900, "history": 900, "message": 300}
WINDOW_TURNS = 6
MEMORY_CHARS = 600                  # ~150 tokens per memory

# ---------------------------------------------------------------------- vectors
EMBED_DIM = 256                     # ponytail: hashed bag-of-words, swap for a real
                                    # embedding model when semantic recall matters

# -------------------------------------------------------------------- astrology
ZODIAC = [(1, 20, "Capricorn"), (2, 19, "Aquarius"), (3, 21, "Pisces"), (4, 20, "Aries"),
          (5, 21, "Taurus"), (6, 21, "Gemini"), (7, 23, "Cancer"), (8, 23, "Leo"),
          (9, 23, "Virgo"), (10, 23, "Libra"), (11, 22, "Scorpio"), (12, 22, "Sagittarius"),
          (12, 31, "Capricorn")]
ELEMENTS = {"Aries": "Fire", "Leo": "Fire", "Sagittarius": "Fire",
            "Taurus": "Earth", "Virgo": "Earth", "Capricorn": "Earth",
            "Gemini": "Air", "Libra": "Air", "Aquarius": "Air",
            "Cancer": "Water", "Scorpio": "Water", "Pisces": "Water"}

# ------------------------------------------------------------------- providers
# First entry in each list is that provider's default.
PROVIDER_MODELS = {
    # Verified against each provider's docs. NOTE: there is no Claude Sonnet 4.7 --
    # the Sonnet line runs 4.5 -> 4.6 -> 5, so Sonnet 4.6 is used in its place.
    "anthropic":  ["claude-sonnet-5", "claude-opus-5", "claude-sonnet-4-6", "claude-opus-4-8"],
    "openai":     ["gpt-5.6-luna", "gpt-5.5", "gpt-5.6-terra"],
    "gemini":     ["gemini-3.8-flash", "gemini-3.7-flash"],
    "openrouter": ["anthropic/claude-sonnet-5", "openai/gpt-5.6-luna",
                   "google/gemini-3.8-flash", "deepseek/deepseek-v4-pro"],
    # All Ollama models here are cloud-hosted (:cloud tag) and need OLLAMA_API_KEY.
    "ollama":     ["deepseek-v4-flash:cloud", "deepseek-v4.1-flash:cloud",
                   "glm-5.3-flash:cloud", "glm-5.3:cloud", "deepseek-v4-pro:cloud"],
    "mock":       ["mock-1"],
}
DEFAULT_MODEL = {p: m[0] for p, m in PROVIDER_MODELS.items()}

# Streaming ------------------------------------------------------------------
STREAM_CHUNK_MIN = 1      # characters before a token event is flushed
MOCK_STREAM_DELAY = 0.03  # seconds between mock words, so the UI effect is visible
DEFAULT_FALLBACK = LLM_FALLBACK or ["anthropic", "openai", "gemini", "openrouter", "ollama", "mock"]
LLM_TIMEOUT = 45
