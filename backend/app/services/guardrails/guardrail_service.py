"""Guardrail on the chat layer.

Deterministically filters incoming chat queries BEFORE they reach retrieval or
the LLM. Covers three hard-fail categories:

- SECRET: requests for API keys, credentials, environment variables, config
  values, or the internal system prompt content.
- INJECTION: jailbreak / prompt-injection attempts that try to override the
  assistant's rules (e.g. "ignore all previous instructions").
- OUT_OF_SCOPE: requests to build unrelated websites/apps, write general-purpose
  code/scripts, install software, etc. — anything outside the AI Research &
  Knowledge Synthesis domain.

Queries that pass all three are returned as ``allowed`` and flow into the normal
RAG pipeline. Blocked queries carry a friendly-but-firm Indonesian refusal so the
routing code can answer them without an HTTP 500 or crashing the stream.
"""

import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Refusal copy (Bahasa Indonesia, friendly but firm).
# ---------------------------------------------------------------------------

_SECRET_REFUSAL = (
    "Maaf, saya tidak dapat membagikan, menampilkan, atau membocorkan kunci API, "
    "kredensial, variabel lingkungan, ataupun isi system prompt internal, dalam "
    "kondisi apa pun. Permintaan tersebut berada di luar cakupan tugas saya "
    "sebagai AI Research & Knowledge Synthesis Agent."
)

_INJECTION_REFUSAL = (
    "Maaf, saya tidak dapat memproses permintaan tersebut. Instruksi yang mencoba "
    "mengabaikan atau menimpa aturan sistem tidak akan saya layani, karena "
    "bertentangan dengan cakupan tugas saya sebagai AI Research & Knowledge "
    "Synthesis Agent. Silakan ajukan pertanyaan yang relevan dengan dokumen sumber."
)

_OUT_OF_SCOPE_REFUSAL = (
    "Maaf, permintaan Anda berada di luar cakupan tugas saya sebagai AI Research & "
    "Knowledge Synthesis Agent. Saya tidak dapat memproses perintah seperti "
    "pembuatan website luar atau membagikan kredensial/kunci API sistem."
)

_GENERIC_REFUSAL = _OUT_OF_SCOPE_REFUSAL


@dataclass(frozen=True)
class GuardrailVerdict:
    allowed: bool
    category: str
    message: str = ""


# ---------------------------------------------------------------------------
# Detection patterns (all matched case-insensitively on the raw query).
# Priority order when several match: injection > secret > out_of_scope.
# ---------------------------------------------------------------------------

# Pure jailbreak / rule-override attempts. These phrasings essentially never
# appear in a legitimate document-research question, so they are self-blocking.
# The .{0,40}? gap lets classical variants ("ignore all previous instructions",
# "ignore your rules", "disregard everything I said") all match cleanly.
_INJECTION_PATTERNS = re.compile(
    r"\bjailbreak\b"
    r"|\bdeveloper\s*mode\b"
    r"|\bmode\s*developer\b"
    r"|\bdo\s+anything\s+(now|you\s+want)\b"
    r"|\bignore\b.{0,40}?\b(instructions?|rules?)\b"
    r"|\babaikan\b.{0,40}?\b(instruksi|aturan|perintah)\b"
    r"|\blupakan\b.{0,40}?\b(instruksi|aturan|perintah)\b"
    r"|\b(disregard|override)\b.{0,40}?\b(instructions?|rules?|prompts?)\b"
    r"|\b(?:do\s+not|don'?t|stop)\s+(following|obeying|listen(ing)?\s+to)\b.{0,20}\b(instructions?|rules?)\b"
    r"|\bno\s+(restrictions?|rules?|limitations?|boundaries?)\b"
    r"|\bact\s+as\s+(if|though|a)\b.{0,60}\b(no\s+(restrictions?|rules|limitations)|unrestricted|anything\s+you\s+want)"
    r"|\bpretend\s+you\s+have\s+no\s+(restrictions?|rules|limitations)\b"
    r"|\byou\s+are\s+now\b.{0,40}\b(dan|developer\s+mode|unrestricted)\b",
    re.IGNORECASE,
)

# Terms that are only dangerous when the user is *asking for* the value. They
# still need an action verb or a reference to the assistant's own prompts.
_ACTION_VERB_PATTERN = re.compile(
    r"\b(berikan|tunjukkan|tampilkan|sebutkan|tulis(?:kan)?|keluarkan|salin|"
    r"bocorkan|buka|kirim|share|show|give|reveal|print|list|publish|expose|"
    r"dump|fetch|retrieve|send|get|spill|tell\s+me)\b",
    re.IGNORECASE,
)

_SELF_REFERENCE_PATTERN = re.compile(
    r"\b(your|kamu|kamu|anda|aku|saya|lu|elo)\b.{0,20}\b(key|kunci|token|password|credential|kredensial|secret|prompt|instruksi)\b"
    r"|\b(key|kunci|token|password|credential|kredensial|secret|prompt|instruksi)\b.{0,20}\b(kamu|anda|my|your)\b",
    re.IGNORECASE,
)

# Strong markers that are almost always an attack in this app (bare "system
# prompt", "api key", ".env", "backend key"). Definition-style questions are
# handled by _DEFINITION_PATTERN + _is_secret_request below and allowed to
# proceed as long as they are not asking to reveal the assistant's own secrets.
_SECRET_PATTERNS = re.compile(
    r"\bsystem[\s-]*prompt\b"
    r"|\bapi[\s_-]?key\b"
    r"|\bapikey\b"
    r"|\bkunci\s*api\b"
    r"|\bkunci\s*akses\b"
    r"|\bkredensial\b|credentials?\b"
    r"|\bsecret\s*key\b"
    r"|\bprivate\s*key\b"
    r"|\bsecrets?\b"
    r"|\baccess\s*token\b"
    r"|\btoken\s*akses\b"
    r"|\benvironment\s*variables?\b"
    r"|\bvariabel\s*(lingkungan|environment|env)\b"
    r"|(?:^|[\s\W])\.env(?:\b|$)"
    r"|\bback\s?end\s*keys?\b"
    r"|\bkeys?\s*(untuk|dari|backend|belakang)?\s*(server|backend|api)\b"
    r"|\bpassword\b|\bpasskey\b"
    r"|\bsandi\s*masuk\b"
    r"|(?:password|passwd|secret|token)\s*(?:kamu|anda|yang\s+anda)?\b",
    re.IGNORECASE,
)

# Requests that should be answered from the document context (e.g. a research
# question explaining what an API key is) are NOT treated as leaks.
_DEFINITION_PATTERN = re.compile(
    r"\b(apa\s+itu|apakah\s+yang\s+dimaksud|what\s+is|what\s+are|definisi|pengertian|"
    r"arti\s+|meaning\s+of|explain\s+what)\b.{0,50}\b(api\s?key|kunci\s*api|system\s*prompt|"
    r"credential|kredensial|token|password|secret|environment|env)\b",
    re.IGNORECASE,
)

# Out-of-scope build / code / tooling requests. Verbs are imperative creation
# verbs only, so legit summary verbs ("rangkum", "ringkas", "jelaskan") never
# trigger this.
_OUT_OF_SCOPE_PATTERNS = re.compile(
    r"\b(buatkan|buatin|buat\s+(?:saya|sebuah|kan|in|dia))?.{0,40}\b(website|web\s*app|"
    r"web\s*page|situs\s*web|e[- ]?commerce|ecommerce|toko\s*online|landing\s*page|"
    r"blog|webapp)\b"
    r"|\b(buatkan|buatin)\b.{0,40}\b(aplikasi|app|script|kode|code|program|python|"
    r"javascript|react|game|bot|extension|api)\b"
    r"|\b(create|build|develop|generate|make|write)\b.{0,40}\b(a\s+|the\s+|an\s+)?"
    r"(website|web\s*page|web\s*app|e[- ]?commerce|toko\s+online|landing\s*page|"
    r"script|program|python|javascript|react|game|bot|extension)\b"
    r"|\b(tulis|tuliskan|write)\b.{0,20}\b(kode|code|script|scripting|program)\b"
    r"|\b(perbaiki|perbaikin|fix|debug)\b.{0,40}\b(kode|code|script|program|bug|"
    r"kompilasi|compile|runtime|error\s+code)\b"
    r"|\b(cara|bagaimana\s+cara)\b.{0,40}\b(install|menginstal|pasang|deploy|"
    r"deployment|setup|konfigurasi\s+server)\b",
    re.IGNORECASE,
)

# A small list of queries whose only apparent goal is operational help outside
# the research domain; they are caught through the creation verbs above, so this
# extra constant exists mainly for logging/diagnostics.
_JUSTIFICATIONS = {
    "secret": _SECRET_REFUSAL,
    "injection": _INJECTION_REFUSAL,
    "out_of_scope": _OUT_OF_SCOPE_REFUSAL,
}


def evaluate_query(query: str) -> GuardrailVerdict:
    """Classify a chat query and return the verdict.

    Priority: injection > secret > out_of_scope. Definition-style questions
    about security terms are allowed through so genuine research questions are
    not falsely blocked.
    """
    if not query or not query.strip():
        return GuardrailVerdict(allowed=True, category="")

    text = query.strip()

    if _INJECTION_PATTERNS.search(text):
        return GuardrailVerdict(
            allowed=False,
            category="injection",
            message=_INJECTION_REFUSAL,
        )

    if _is_secret_request(text):
        return GuardrailVerdict(
            allowed=False,
            category="secret",
            message=_SECRET_REFUSAL,
        )

    if _OUT_OF_SCOPE_PATTERNS.search(text):
        return GuardrailVerdict(
            allowed=False,
            category="out_of_scope",
            message=_OUT_OF_SCOPE_REFUSAL,
        )

    return GuardrailVerdict(allowed=True, category="")


def _is_secret_request(text: str) -> bool:
    """True when the query asks for a credential/secret/system-prompt value."""
    strong_marker = _SECRET_PATTERNS.search(text)
    if not strong_marker:
        return False
    has_action = bool(_ACTION_VERB_PATTERN.search(text))
    has_self_reference = bool(_SELF_REFERENCE_PATTERN.search(text))
    # "apa itu API key?" is a conceptual question, not a leak — BUT only when it
    # does not also ask to reveal/surrender the value or reference the assistant's
    # own secrets ("what is YOUR api key? reveal it" is clearly an attack).
    if _DEFINITION_PATTERN.search(text) and not has_action and not has_self_reference:
        return False
    if has_action or has_self_reference:
        return True
    marker = strong_marker.group(0).lower()
    if "system prompt" in marker or "api key" in marker or "kunci api" in marker:
        return True
    return False