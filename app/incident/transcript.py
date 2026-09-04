# app/incident/transcript.py
"""Transcript domain model and deterministic evidence extraction.

A transcript is a piece of text that may contain signals relevant to an
incident. The TextEvidenceExtractor parses it into structured observations
with full provenance.

IMPORTANT:
  - This is NOT a scam classifier
  - It does NOT produce scam_probability or risk scores
  - It extracts WHAT WAS SAID, not whether it is malicious
  - A request in a transcript is a FACT (someone said it), not a VERDICT
  - User actions remain separate from requests

Context and negation:
  - "Never share your OTP" -> NOT an OTP request (advice/warning)
  - "I sent the OTP" -> CLAIMED user action (first-person), UNCONFIRMED
  - "Give me the OTP" -> OTP request
  - "The bank asked for my OTP" -> report of someone requesting OTP

SAFETY RULE: transcript claim != explicit user confirmation.
A first-person phrase ("I shared the OTP") produces a structured candidate
(ExtractedAction / CLAIMED_USER_ACTION) that is an INFERENCE, NOT proof the
user acted. It is surfaced for the user to explicitly confirm. The extractor
does NOT itself create a confirmed UserAction; that is solely the job of the
explicit confirmation path (record_user_action).

Conservative extraction:
  - False positives are worse than missing weak evidence
  - When uncertain: no observation
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from app.evidence.models import UserObservationType
from app.incident.transcript_provider import TranscriptSegment


# ---- Transcript model ----

class TranscriptSource(str, Enum):
    USER_TYPED = "USER_TYPED"
    USER_DICTATED = "USER_DICTATED"
    STT_PROVIDER = "STT_PROVIDER"
    MESSAGE_FORWARD = "MESSAGE_FORWARD"


@dataclass(frozen=True)
class Transcript:
    transcript_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    incident_id: str = ""
    source: TranscriptSource = TranscriptSource.USER_TYPED
    text: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    segments: List[TranscriptSegment] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)
    batch_id: Optional[str] = None  # For idempotency

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transcript_id": self.transcript_id,
            "incident_id": self.incident_id,
            "source": self.source.value,
            "text": self.text,
            "created_at": self.created_at,
            "segments": [s.to_dict() for s in self.segments],
            "provenance": self.provenance,
            "batch_id": self.batch_id,
        }

    def get_speaker_for_segment(self, segment: TranscriptSegment) -> Optional[str]:
        """Return the speaker label for a segment, or None if unknown."""
        return segment.speaker

    def get_text_with_speaker_context(self) -> str:
        """Return full text with speaker annotations for extraction.

        If segments have speaker labels, annotates the text like:
          [CALLER] Give me your OTP
          [USER] I shared it

        If no segments or no speaker labels, returns plain text.
        """
        if not self.segments:
            return self.text

        annotated_parts = []
        for seg in self.segments:
            if seg.speaker:
                annotated_parts.append(f"[{seg.speaker}] {seg.text}")
            else:
                annotated_parts.append(seg.text)
        return " ".join(annotated_parts)


# ---- Extracted evidence ----

@dataclass(frozen=True)
class ExtractedObservation:
    observation_type: UserObservationType
    confidence_in_extraction: float
    text_span: str
    span_start: int
    span_end: int
    extraction_method: str
    epistemic_note: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observation_type": self.observation_type.value,
            "confidence_in_extraction": self.confidence_in_extraction,
            "text_span": self.text_span,
            "span_start": self.span_start,
            "span_end": self.span_end,
            "extraction_method": self.extraction_method,
            "epistemic_note": self.epistemic_note,
        }


@dataclass(frozen=True)
class ExtractedAction:
    """A first-person action CLAIM detected in the transcript.

    This is a structured CANDIDATE (CLAIMED_USER_ACTION), NOT a confirmed
    UserAction. It is an inference drawn from text such as "I shared the OTP".
    It must be explicitly confirmed by the user before it becomes a real
    UserAction (epistemic_status=FACT) and escalates exposure to
    USER_CONFIRMED_EXPOSED / incident status RECOVERING.
    """
    action_type: str
    description: str
    text_span: str
    span_start: int
    span_end: int
    extraction_method: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "description": self.description,
            "text_span": self.text_span,
            "span_start": self.span_start,
            "span_end": self.span_end,
            "extraction_method": self.extraction_method,
        }


@dataclass(frozen=True)
class ExtractionResult:
    transcript_id: str
    observations: List[ExtractedObservation]
    user_actions: List[ExtractedAction]
    raw_text: str
    extraction_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transcript_id": self.transcript_id,
            "observations": [o.to_dict() for o in self.observations],
            "user_actions": [a.to_dict() for a in self.user_actions],
            "raw_text": self.raw_text,
            "extraction_timestamp": self.extraction_timestamp,
        }


# ---- Sentence splitting ----

def _split_sentences(text: str) -> List[Tuple[str, int]]:
    sentences: List[Tuple[str, int]] = []
    pattern = re.compile(r'(?<=[.!?])\s+|\n+')
    pos = 0
    for match in pattern.finditer(text):
        end = match.start()
        sentence = text[pos:end].strip()
        if sentence:
            sentences.append((sentence, pos))
        pos = match.end()
    remaining = text[pos:].strip()
    if remaining:
        sentences.append((remaining, pos))
    return sentences


# ---- Negation detection ----

_NEGATION_WORDS = {
    "not", "never", "don't", "do not", "dont", "shouldn't", "should not",
    "won't", "will not", "can't", "cannot", "mustn't", "must not",
    "no", "neither", "nor", "without", "avoid", "donot",
}

_ADVICE_INDICATORS = {
    "never", "should not", "shouldn't",
    "avoid", "warning", "be careful", "be aware", "tip",
    "advice", "remember",
}


def _has_negation_near(text: str, keyword_start: int, keyword_end: int, window: int = 40) -> bool:
    search_start = max(0, keyword_start - window)
    search_end = min(len(text), keyword_end + window)
    context = text[search_start:search_end].lower()
    for neg in _NEGATION_WORDS:
        # Use word boundary matching to avoid false positives like "no" in "now"
        pattern = r'\b' + re.escape(neg) + r'\b'
        if re.search(pattern, context):
            return True
    return False


def _is_advice_context(sentence: str) -> bool:
    lower = sentence.lower()
    for indicator in _ADVICE_INDICATORS:
        if indicator in lower:
            return True
    return False


# ---- Speaker detection ----

def _is_user_speaking(text: str, sentence: str) -> bool:
    lower = sentence.lower().strip()
    user_patterns = [
        r'\bi\s+(shared|sent|gave|told|provided|installed|clicked|logged|transferred|paid|bought|sent|did|was|had|received|got| saw| know|think|feel|went|called|refused|declined)',
        r'\bmy\s+(account|password|otp|code|bank|money|phone|number|name|address)',
        r'\bi\s+already',
        r'\bi\s+have\s+(already|sent|shared|given|told|provided)',
        r'\bi\s+just\s+(shared|sent|gave|told|installed|clicked)',
        r'\bi\s+told\s+them\s+no',
    ]
    for pattern in user_patterns:
        if re.search(pattern, lower):
            return True
    return False


def _is_caller_speaking(text: str, sentence: str) -> bool:
    lower = sentence.lower().strip()
    caller_patterns = [
        r'\bgive\s+(me|us)\s+(the|your|my)?',
        r'\bsend\s+(me|us)\s+(the|your|my)?',
        r'\btell\s+(me|us)\s+(the|your|my)?',
        r'\bshare\s+(your|the|my)?\s+',
        r'\bprovide\s+(your|the|my)?\s+',
        r'\benter\s+(your|the|my)?\s+',
        r'\binstall\s+(this|the|our|a|my)?\s+',
        r'\bdownload\s+(this|the|our|a|my)?\s+',
        r'\bopen\s+(this|the|our|a|my)?\s+',
        r'\bI\s+am\s+calling\s+from',
        r'\bthis\s+is\s+(the\s+)?(police|bank|government|court|department)',
        r'\byou\s+must\s+(share|give|send|tell|provide|install|download|enter|pay|transfer)',
        r'\byou\s+have\s+to\s+(share|give|send|tell|provide|install|download|enter|pay|transfer)',
        r'\bwe\s+need\s+(you\s+to\s+)?(share|give|send|tell|provide|enter)',
        r'\bdo\s+not\s+tell\s+(anyone|nobody|your\s+family)',
        r'\bkeep\s+this\s+(secret|between)',
        r'\bwhat\s+is\s+(your|the)\s+(otp|password|code)',
        r'\bneed\s+(your|the)\s+(otp|password|code)',
        r'\bmust\s+(have|know|get)\s+(your|the)\s+(otp|password|code)',
    ]
    for pattern in caller_patterns:
        if re.search(pattern, lower, re.IGNORECASE):
            return True
    return False


# ---- Extraction rules ----

@dataclass(frozen=True)
class ExtractionRule:
    name: str
    observation_type: Optional[UserObservationType]
    action_type: Optional[str]
    patterns: List[str]
    requires_caller_context: bool = False
    requires_user_context: bool = False
    negation_sensitive: bool = True
    advice_sensitive: bool = True
    confidence: float = 0.8
    epistemic_note: str = ""

    def matches(self, text: str, sentence: str, sentence_start: int) -> List[Tuple[str, int, int]]:
        matches = []
        for pattern in self.patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                matched_text = match.group()
                start = match.start()
                end = match.end()

                if self.negation_sensitive and _has_negation_near(text, start, end):
                    continue
                if self.advice_sensitive and _is_advice_context(sentence):
                    continue
                # Caller context: if not user speech, treat as caller/other-party speech
                if self.requires_caller_context and _is_user_speaking(text, sentence):
                    continue
                if self.requires_user_context and not _is_user_speaking(text, sentence):
                    continue

                matches.append((matched_text, start, end))
        return matches


# ---- Rule definitions ----

_RULES: List[ExtractionRule] = [
    # OTP / Verification code requests
    ExtractionRule(
        name="otp_request",
        observation_type=UserObservationType.OTP_REQUEST,
        action_type=None,
        patterns=[
            r'\bgive\s+(me|us)\s+(the|your|my)?\s*(otp|one[- ]?time\s+password|verification\s+code|security\s+code|code)',
            r'\bshare\s+(me|us|your|the|my)?\s*(otp|one[- ]?time\s+password|verification\s+code|security\s+code|code)',
            r'\btell\s+(me|us)\s+(the|your|my)?\s*(otp|one[- ]?time\s+password|verification\s+code|security\s+code|code)',
            r'\bwhat\s+is\s+(the|your|my)?\s*(otp|one[- ]?time\s+password|verification\s+code|security\s+code)',
            r'\benter\s+(the|your|my)?\s*(otp|one[- ]?time\s+password|verification\s+code|security\s+code|code)',
            r'\bsend\s+(me|us)\s+(the|your|my)?\s*(otp|one[- ]?time\s+password|verification\s+code|security\s+code|code)',
            r'\bneed\s+(the|your|my)?\s*(otp|one[- ]?time\s+password|verification\s+code|security\s+code|code)',
            r'\bmust\s+(have|know|get)\s+(the|your|my)?\s*(otp|one[- ]?time\s+password|verification\s+code|security\s+code|code)',
            r'\bcode\s+(now|immediately|asap|quickly|hurry)',
        ],
        requires_caller_context=True,
        negation_sensitive=False,  # OTP patterns are specific enough; nearby negation from other sentences is irrelevant
        confidence=0.9,
        epistemic_note="Speaker requested OTP/verification code from the user",
    ),

    # Password requests
    ExtractionRule(
        name="password_request",
        observation_type=UserObservationType.PASSWORD_REQUEST,
        action_type=None,
        patterns=[
            r'\bgive\s+(me|us)\s+(the|your|my)?\s*password',
            r'\bshare\s+(me|us|your|the|my)?\s*password',
            r'\btell\s+(me|us)\s+(the|your|my)?\s*password',
            r'\bwhat\s+is\s+(the|your|my)?\s*password',
            r'\benter\s+(the|your|my)?\s*password',
            r'\bsend\s+(me|us)\s+(the|your|my)?\s*password',
            r'\bneed\s+(the|your|my)?\s*password',
        ],
        requires_caller_context=True,
        confidence=0.9,
        epistemic_note="Speaker requested password from the user",
    ),

    # Money requests
    ExtractionRule(
        name="money_request",
        observation_type=UserObservationType.MONEY_REQUEST,
        action_type=None,
        patterns=[
            r'\bsend\s+(me|us)\s+(the\s+)?(money|payment|amount|fee|fine)',
            r'\btransfer\s+(the\s+)?(money|payment|amount|fee|fine)\s+(to|into)',
            r'\bpay\s+(the\s+)?(fee|fine|amount|money|penalty)',
            r'\bdeposit\s+(the\s+)?(money|amount|fee)',
            r'\bneed\s+(you\s+to\s+)?(send|transfer|pay)\s+(the\s+)?(money|payment|fee|fine|amount)',
            r'\bmust\s+(send|transfer|pay)\s+(the\s+)?(money|payment|fee|fine|amount)',
            r'\byou\s+must\s+(send|transfer|pay)',
            r'\bhave\s+you\s+(sent|transferred|paid)',
            r'\bwhen\s+(will\s+you|are\s+you\s+going\s+to)\s+(send|transfer|pay)',
        ],
        requires_caller_context=True,
        confidence=0.85,
        epistemic_note="Speaker requested money transfer/payment from the user",
    ),

    # Bank transfer requests
    ExtractionRule(
        name="bank_transfer_request",
        observation_type=UserObservationType.BANK_TRANSFER_REQUEST,
        action_type=None,
        patterns=[
            r'\btransfer\s+(to)\s+(the\s+)?(account|bank|number)',
            r'\bbank\s+(transfer|details|account\s+number|account)',
            r'\bsend\s+to\s+(this|the)\s+(account|bank|number)',
            r'\baccount\s+number\s+(is|:)',
            r'\bIFSC\s+(code\s+(is|:)|[A-Z]{4}\d{7})',
            r'\bneft|rtgs|imps|upi',
        ],
        requires_caller_context=True,
        confidence=0.85,
        epistemic_note="Speaker requested bank transfer or shared bank details",
    ),

    # Remote access requests
    ExtractionRule(
        name="remote_access_request",
        observation_type=UserObservationType.REMOTE_ACCESS_REQUEST,
        action_type=None,
        patterns=[
            r'\binstall\s+(this|the|our|a|any)\s+(app|application|software|tool)',
            r'\bdownload\s+(this|the|our|a|any)\s+(app|application|software|tool)',
            r'\bshare\s+(your\s+)?screen',
            r'\bgrant\s+(remote\s+)?access',
            r'\ballow\s+(remote\s+)?access',
            r'\bteamviewer|anydesk|ultraviewer|splashtop|logmein|remote\s+desktop',
            r'\bscreen\s+sharing',
            r'\bremote\s+(control|access|support|connection)',
        ],
        requires_caller_context=True,
        confidence=0.9,
        epistemic_note="Speaker requested remote access or app installation",
    ),

    # App install requests
    ExtractionRule(
        name="app_install_request",
        observation_type=UserObservationType.APP_INSTALL_REQUEST,
        action_type=None,
        patterns=[
            r'\binstall\s+(this|the|our|a)\s+(app|application)',
            r'\bdownload\s+(this|the|our|a)\s+(app|application)',
            r'\bgo\s+to\s+(the\s+)?(play\s+store|app\s+store)',
            r'\bsearch\s+for\s+(this|the|our)\s+(app|application)',
        ],
        requires_caller_context=True,
        confidence=0.85,
        epistemic_note="Speaker requested app installation",
    ),

    # Identity document requests
    ExtractionRule(
        name="identity_document_request",
        observation_type=UserObservationType.IDENTITY_DOCUMENT_REQUEST,
        action_type=None,
        patterns=[
            r'\bshare\s+(the|your|my)?\s*(id|aadhaar|pan|passport|driver.s?\s+license|identity|document)',
            r'\bsend\s+(the|your|my)?\s*(id|aadhaar|pan|passport|driver.s?\s+license|identity|document)',
            r'\btell\s+(me|us)\s+(the|your|my)?\s*(id|aadhaar|pan|passport|document)\s+number',
            r'\bneed\s+(the|your|my)?\s*(id|aadhaar|pan|passport|identity|document)',
            r'\bverify\s+(the|your|my)?\s*(id|identity|document)',
            r'\bphoto\s+of\s+(the|your|my)?\s*(id|aadhaar|pan|passport|document)',
        ],
        requires_caller_context=True,
        confidence=0.9,
        epistemic_note="Speaker requested identity document from the user",
    ),

    # Authority claims
    ExtractionRule(
        name="authority_claim",
        observation_type=UserObservationType.AUTHORITY_CLAIM,
        action_type=None,
        patterns=[
            r'\bI\s+am\s+(calling\s+from\s+)?(the\s+)?(police|bank|government|court|department|agency|rbi|cyber\s+crime|tax\s+department|income\s+tax|cbi|enforcement\s+director)',
            r'\bthis\s+is\s+(the\s+)?(police|bank|government|court|department|agency)',
            r'\bI\s+(am|represent)\s+(the\s+)?(police|bank|government|court|department)',
            r'\bofficial\s+(police|bank|government|court|department|notice|call)',
            r'\bauthori[zs]ed\s+(by\s+)?(the\s+)?(police|bank|government|court)',
            r'\byour\s+(account|case)\s+is\s+(under\s+)?(investigation|review|scrutiny|being\s+checked)',
            r'\b(cyber|crime|fraud)\s+department',
        ],
        requires_caller_context=True,
        confidence=0.9,
        epistemic_note="Speaker claimed to be from an authority organization",
    ),

    # Threats
    ExtractionRule(
        name="threat_of_arrest",
        observation_type=UserObservationType.THREAT_OF_ARREST,
        action_type=None,
        patterns=[
            r'\b(arrest|jail|imprison|detain)\s+(you|your)',
            r'\bwill\s+(be\s+)?arrested',
            r'\bwarrant\s+(has\s+been\s+)?issued',
            r'\bpolice\s+(will|are\s+going\s+to|are\s+coming)',
            r'\byou\s+will\s+(be\s+)?(arrested|jailed|detained)',
            r'\bfbi|cbi|police\s+are\s+(coming|on\s+the\s+way)',
        ],
        requires_caller_context=True,
        negation_sensitive=False,  # "arrested if you do not comply" is still a threat
        confidence=0.9,
        epistemic_note="Speaker threatened arrest or legal detention",
    ),

    ExtractionRule(
        name="threat_of_legal_action",
        observation_type=UserObservationType.THREAT_OF_LEGAL_ACTION,
        action_type=None,
        patterns=[
            r'\b(legal|court)\s+(action|case|notice|proceeding|consequence)',
            r'\bsue\s+(you|your)',
            r'\bfine\s+(you|your)',
            r'\bpenalty',
            r'\bwill\s+(take\s+)?legal\s+action',
            r'\bcourt\s+(order|notice|summons)',
        ],
        requires_caller_context=True,
        negation_sensitive=False,  # Legal threats contain conditionals with negation
        confidence=0.85,
        epistemic_note="Speaker threatened legal action or court proceedings",
    ),

    # Urgency
    ExtractionRule(
        name="urgency",
        observation_type=UserObservationType.URGENCY,
        action_type=None,
        patterns=[
            r'\bright\s+now',
            r'\bimmediately',
            r'\bwithin\s+(\d+\s+)?(minutes?|hours?|seconds?)',
            r'\btime\s+(is\s+)?(running\s+out|up|limited)',
            r'\bhurry',
            r'\blast\s+chance',
            r'\bfinal\s+warning',
            r'\bdo\s+it\s+now',
            r'\bquickly',
            r'\bhave\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten|fifteen|twenty|thirty)\s+minutes',
        ],
        requires_caller_context=True,
        negation_sensitive=False,  # Urgency words can appear near other negation without being negated
        confidence=0.8,
        epistemic_note="Speaker created urgency or time pressure",
    ),

    # Secrecy
    ExtractionRule(
        name="secrecy_request",
        observation_type=UserObservationType.SECRECY_REQUEST,
        action_type=None,
        patterns=[
            r'\bdo\s+not\s+tell\s+(anyone|nobody|your\s+(family|wife|husband|parents|friends))',
            r'\bkeep\s+this\s+(between\s+us|secret|confidential|private)',
            r'\bdon.t\s+tell\s+(anyone|nobody|your)',
            r'\bthis\s+is\s+confidential',
            r'\bdo\s+not\s+discuss\s+(this|it)\s+with',
            r'\bno\s+one\s+should\s+know',
        ],
        requires_caller_context=True,
        negation_sensitive=False,  # "do not tell anyone" IS the secrecy request
        confidence=0.85,
        epistemic_note="Speaker requested secrecy or discouraged telling others",
    ),

    # Call transfer
    ExtractionRule(
        name="call_transfer",
        observation_type=UserObservationType.CALL_BACK_INSTRUCTION,
        action_type=None,
        patterns=[
            r'\bcall\s+(me|us)\s+back\s+(on|at|to)',
            r'\bdial\s+(this|the)\s+number',
            r'\bphone\s+(me|us)\s+back',
            r'\bcall\s+(this|the)\s+(number|line)',
        ],
        requires_caller_context=True,
        confidence=0.8,
        epistemic_note="Speaker instructed to call back on a specific number",
    ),

    # User confirmed actions (first person)

    ExtractionRule(
        name="user_shared_otp",
        observation_type=None,
        action_type="SHARED_OTP",
        patterns=[
            r'\bi\s+(shared|gave|told|sent|provided)\s+(them\s+)?(the\s+)?(otp|code|password|number)',
            r'\bi\s+(have\s+)?already\s+(shared|gave|sent|told|provided)\s+(the\s+)?(otp|code|number)',
            r'\bi\s+(just\s+)?(shared|gave|told|sent)\s+(the\s+)?(otp|code)',
            r'\bi\s+sent\s+the\s+(otp|code)',
            r'\byes\s+i\s+(shared|gave|sent|told)',
            r'\bi\s+already\s+(did|sent|shared|gave)',
        ],
        requires_user_context=True,
        negation_sensitive=True,
        advice_sensitive=True,
        confidence=0.85,
        epistemic_note="User confirmed they shared an OTP or verification code",
    ),

    ExtractionRule(
        name="user_shared_password",
        observation_type=None,
        action_type="SHARED_PASSWORD",
        patterns=[
            r'\bi\s+(shared|gave|told|sent|provided)\s+(them\s+)?(my\s+)?password',
            r'\bi\s+(have\s+)?already\s+(shared|gave|sent|told|provided)\s+(my\s+)?password',
            r'\bi\s+(just\s+)?(shared|gave|told|sent)\s+(my\s+)?password',
        ],
        requires_user_context=True,
        negation_sensitive=True,
        advice_sensitive=True,
        confidence=0.85,
        epistemic_note="User confirmed they shared a password",
    ),

    ExtractionRule(
        name="user_sent_money",
        observation_type=None,
        action_type="SENT_MONEY",
        patterns=[
            r'\bi\s+(sent|transferred|paid|paid\s+the)\s+(them\s+)?(the\s+)?(money|amount|fee|fine)',
            r'\bi\s+(have\s+)?already\s+(sent|transferred|paid)',
            r'\bi\s+(just\s+)?(sent|transferred|paid)',
            r'\bthe\s+money\s+(has\s+been\s+)?(sent|transferred|paid)',
        ],
        requires_user_context=True,
        negation_sensitive=True,
        advice_sensitive=True,
        confidence=0.85,
        epistemic_note="User confirmed they sent money or made a transfer",
    ),

    ExtractionRule(
        name="user_shared_document",
        observation_type=None,
        action_type="SHARED_DOCUMENT",
        patterns=[
            r'\bi\s+(shared|sent|gave|provided)\s+(them\s+)?(my\s+)?(id|aadhaar|pan|passport|document|photo|copy)',
            r'\bi\s+(have\s+)?already\s+(shared|sent|gave|provided)\s+(my\s+)?(id|document)',
        ],
        requires_user_context=True,
        negation_sensitive=True,
        advice_sensitive=True,
        confidence=0.85,
        epistemic_note="User confirmed they shared identity documents",
    ),

    ExtractionRule(
        name="user_installed_app",
        observation_type=None,
        action_type="INSTALLED_APPLICATION",
        patterns=[
            r'\bi\s+(installed|downloaded|opened)\s+(the\s+)?(app|application|software)',
            r'\bi\s+(have\s+)?already\s+(installed|downloaded)',
        ],
        requires_user_context=True,
        negation_sensitive=True,
        advice_sensitive=True,
        confidence=0.85,
        epistemic_note="User confirmed they installed an application",
    ),

    ExtractionRule(
        name="user_granted_remote",
        observation_type=None,
        action_type="GRANTED_REMOTE_ACCESS",
        patterns=[
            r'\bi\s+(gave|granted|allowed)\s+(them\s+)?(remote\s+)?(access|control|permission)',
            r'\bi\s+(have\s+)?already\s+(gave|granted|allowed)\s+(remote\s+)?access',
            r'\bi\s+(shared|started)\s+(my\s+)?screen\s+sharing',
        ],
        requires_user_context=True,
        negation_sensitive=True,
        advice_sensitive=True,
        confidence=0.85,
        epistemic_note="User confirmed they granted remote access",
    ),

    ExtractionRule(
        name="user_declined",
        observation_type=None,
        action_type="DECLINED_REQUEST",
        patterns=[
            r'\bi\s+(refused|declined|said\s+no|didn.t\s+(share|give|send|tell|install|download|pay|transfer))',
            r'\bi\s+(did\s+not|didn.t)\s+(share|give|send|tell|install|download|pay|transfer)',
            r'\bi\s+told\s+them\s+no',
            r'\bi\s+didn.t\s+do\s+(it|that|anything)',
        ],
        requires_user_context=True,
        negation_sensitive=False,
        advice_sensitive=False,
        confidence=0.85,
        epistemic_note="User confirmed they declined a request",
    ),
]


_ACTION_DESCRIPTIONS = {
    "SHARED_OTP": "Shared OTP or verification code",
    "SHARED_PASSWORD": "Shared password",
    "SENT_MONEY": "Sent money or made a transfer",
    "SHARED_DOCUMENT": "Shared identity document",
    "INSTALLED_APPLICATION": "Installed an application",
    "GRANTED_REMOTE_ACCESS": "Granted remote access",
    "DECLINED_REQUEST": "Declined the request",
}


# ---- Main extractor ----

class TextEvidenceExtractor:
    """Deterministic, rule-based evidence extractor for transcript text.

    This is NOT a scam classifier. It extracts WHAT WAS SAID and
    WHAT THE USER DID based on the transcript text.

    Supports:
      - Plain text extraction (original behavior)
      - Segment-based extraction with speaker metadata
      - Incremental extraction (new segments don't reprocess old ones)
    """

    def extract(self, transcript: Transcript) -> ExtractionResult:
        """Extract evidence from a transcript.

        If the transcript has segments with speaker metadata, uses that
        to improve extraction accuracy. Otherwise falls back to plain
        text extraction.
        """
        if transcript.segments:
            return self._extract_from_segments(transcript)
        return self._extract_from_text(transcript)

    def _extract_from_text(self, transcript: Transcript) -> ExtractionResult:
        """Original plain-text extraction."""
        text = transcript.text
        sentences = _split_sentences(text)

        observations: List[ExtractedObservation] = []
        user_actions: List[ExtractedAction] = []

        seen_observations: Set[UserObservationType] = set()
        seen_actions: Set[str] = set()

        for sentence, sentence_start in sentences:
            for rule in _RULES:
                matches = rule.matches(text, sentence, sentence_start)

                for matched_text, start, end in matches:
                    if rule.observation_type is not None:
                        if rule.observation_type not in seen_observations:
                            obs = ExtractedObservation(
                                observation_type=rule.observation_type,
                                confidence_in_extraction=rule.confidence,
                                text_span=matched_text,
                                span_start=start,
                                span_end=end,
                                extraction_method=rule.name,
                                epistemic_note=rule.epistemic_note,
                            )
                            observations.append(obs)
                            seen_observations.add(rule.observation_type)

                    elif rule.action_type is not None:
                        if rule.action_type not in seen_actions:
                            action = ExtractedAction(
                                action_type=rule.action_type,
                                description=_ACTION_DESCRIPTIONS.get(
                                    rule.action_type, rule.action_type
                                ),
                                text_span=matched_text,
                                span_start=start,
                                span_end=end,
                                extraction_method=rule.name,
                            )
                            user_actions.append(action)
                            seen_actions.add(rule.action_type)

        return ExtractionResult(
            transcript_id=transcript.transcript_id,
            observations=observations,
            user_actions=user_actions,
            raw_text=text,
        )

    def _extract_from_segments(self, transcript: Transcript) -> ExtractionResult:
        """Extract evidence using segment-level speaker metadata.

        When segments have speaker labels, we use them to improve
        extraction accuracy:
          - [CALLER] segments: caller context rules apply
          - [USER] segments: user context rules apply
          - No speaker: fall back to original heuristic detection

        The extraction is deterministic: the same input always produces
        the same output, regardless of segment ordering.
        """
        observations: List[ExtractedObservation] = []
        user_actions: List[ExtractedAction] = []

        seen_observations: Set[UserObservationType] = set()
        seen_actions: Set[str] = set()

        for segment in transcript.segments:
            speaker = segment.speaker
            text = segment.text.strip()
            if not text:
                continue

            sentences = _split_sentences(text)

            # Track the original character offset for this segment
            # within the full transcript text
            segment_offset = transcript.text.find(text)
            if segment_offset < 0:
                segment_offset = 0

            for sentence, sentence_start in sentences:
                absolute_start = segment_offset + sentence_start

                for rule in _RULES:
                    # If we have speaker metadata, use it to determine context
                    if speaker == "CALLER" and rule.requires_caller_context:
                        # Caller is speaking, so caller context is satisfied
                        # Don't check heuristic user-speech detection
                        matches = self._matches_without_speaker_check(
                            rule, transcript.text, sentence, absolute_start
                        )
                    elif speaker == "USER" and rule.requires_user_context:
                        # User is speaking, so user context is satisfied
                        matches = self._matches_without_speaker_check(
                            rule, transcript.text, sentence, absolute_start
                        )
                    elif speaker == "USER" and rule.requires_caller_context:
                        # User is speaking but rule requires caller context
                        # Skip this rule for this segment
                        continue
                    elif speaker == "CALLER" and rule.requires_user_context:
                        # Caller is speaking but rule requires user context
                        # Skip this rule for this segment
                        continue
                    else:
                        # No speaker metadata or unknown speaker
                        # Fall back to original heuristic detection
                        matches = rule.matches(
                            transcript.text, sentence, absolute_start
                        )

                    for matched_text, start, end in matches:
                        if rule.observation_type is not None:
                            if rule.observation_type not in seen_observations:
                                obs = ExtractedObservation(
                                    observation_type=rule.observation_type,
                                    confidence_in_extraction=rule.confidence,
                                    text_span=matched_text,
                                    span_start=start,
                                    span_end=end,
                                    extraction_method=rule.name,
                                    epistemic_note=rule.epistemic_note,
                                )
                                observations.append(obs)
                                seen_observations.add(rule.observation_type)

                        elif rule.action_type is not None:
                            if rule.action_type not in seen_actions:
                                action = ExtractedAction(
                                    action_type=rule.action_type,
                                    description=_ACTION_DESCRIPTIONS.get(
                                        rule.action_type, rule.action_type
                                    ),
                                    text_span=matched_text,
                                    span_start=start,
                                    span_end=end,
                                    extraction_method=rule.name,
                                )
                                user_actions.append(action)
                                seen_actions.add(rule.action_type)

        return ExtractionResult(
            transcript_id=transcript.transcript_id,
            observations=observations,
            user_actions=user_actions,
            raw_text=transcript.text,
        )

    def _matches_without_speaker_check(
        self,
        rule: ExtractionRule,
        full_text: str,
        sentence: str,
        sentence_start: int,
    ) -> List[Tuple[str, int, int]]:
        """Match a rule without checking speaker heuristics.

        Used when we already know the speaker from segment metadata.
        Still applies negation and advice checks.
        """
        matches: List[Tuple[str, int, int]] = []
        for pattern in rule.patterns:
            for match in re.finditer(pattern, full_text, re.IGNORECASE):
                matched_text = match.group()
                start = match.start()
                end = match.end()

                if rule.negation_sensitive and _has_negation_near(full_text, start, end):
                    continue
                if rule.advice_sensitive and _is_advice_context(sentence):
                    continue

                matches.append((matched_text, start, end))
        return matches
