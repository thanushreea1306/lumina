# app/incident/audio_source.py
"""Audio Source Abstraction and Capability Matrix.

LUMINA is a call-protection product. The primary experience is:

  PHONE CALL
  → speech-to-text
  → conversation/pressure detection
  → victim intervention
  → trusted-contact assistance

This module establishes a clean abstraction for where audio comes from,
ensuring LUMINA never claims to be listening to a phone call unless it
genuinely receives that call's audio through a legitimate mechanism.

AUDIO SOURCE CATEGORIES:

  A. USER_PROVIDED_RECORDING
     A file the user explicitly selects and uploads (WAV, MP3, etc.)
     This is the highest-trust path: the user chose to share this audio.

  B. MICROPHONE
     Live microphone capture via browser MediaRecorder or Android RECORD_AUDIO.
     Captures the local device audio only — NOT the remote caller's audio
     unless the device is on speakerphone and the microphone picks it up.
     The UI must say "Recording microphone audio" not "Listening to your call".

  C. USER_DICTATED
     User types or dictates transcript text directly.

  D. MESSAGE_FORWARD
     User forwards a message or chat transcript.

  E. SYSTEM_CALL_AUDIO (FUTURE)
     Android does NOT provide a public API for capturing both sides of a
     cellular call to a third-party app. This source exists as a placeholder
     for future platform-supported integrations (e.g., Android 15+ CallAudio
     if Google opens it to third-party apps).

  F. VOIP_CALL_AUDIO (FUTURE)
     VoIP apps that expose audio streams (e.g., via AudioManager) could
     theoretically pipe audio to LUMINA. This requires app-specific
     integration and is not generally available.

CAPABILITY MATRIX:

  The matrix is a static data structure that documents what each platform
  and source can actually provide. It is NOT aspirational — it reflects
  the current verified state.

PLATFORM TRUTH (Android):

  - Cellular call audio: NOT available to third-party apps via public API
  - Speakerphone audio: Only what the microphone picks up (one-sided)
  - Bluetooth call audio: NOT available (AudioManager SCO is for VoIP only)
  - VoIP audio: Possible if the VoIP app exposes audio routing
  - Microphone: Available with RECORD_AUDIO permission
  - Call state: Available with READ_PHONE_STATE (already implemented)

PLATFORM TRUTH (Browser):

  - Microphone: Available with getUserMedia (already implemented)
  - System audio: NOT available (no captureSystemAudio API)
  - Tab audio: Available via getDisplayMedia (screen share with audio)
  - Remote call audio: NOT available

NEVER DO:

  - Use AccessibilityService to intercept call audio
  - Use hidden recording without visible indicator
  - Claim to monitor a call when only microphone is captured
  - Fabricate "both sides" of a conversation from one-sided audio
  - Pretend the remote caller's audio is available when it is not
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


# ---- Audio Source Types ----


class AudioSourceType(str, Enum):
    """Categories of audio input to LUMINA."""
    USER_PROVIDED_RECORDING = "USER_PROVIDED_RECORDING"
    MICROPHONE = "MICROPHONE"
    USER_DICTATED = "USER_DICTATED"
    MESSAGE_FORWARD = "MESSAGE_FORWARD"
    SYSTEM_CALL_AUDIO = "SYSTEM_CALL_AUDIO"
    VOIP_CALL_AUDIO = "VOIP_CALL_AUDIO"


class CapabilityStatus(str, Enum):
    """Whether a capability is actually available."""
    AVAILABLE = "AVAILABLE"
    PARTIALLY_AVAILABLE = "PARTIALLY_AVAILABLE"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    NOT_TESTED = "NOT_TESTED"


class AudioSide(str, Enum):
    """Which side(s) of a conversation the source captures."""
    LOCAL_ONLY = "LOCAL_ONLY"         # Only the local user's audio
    REMOTE_ONLY = "REMOTE_ONLY"       # Only the remote party's audio
    BOTH_SIDES = "BOTH_SIDES"         # Both sides (rare for third-party apps)
    UNKNOWN = "UNKNOWN"               # Cannot determine


# ---- Capability Matrix ----


@dataclass(frozen=True)
class SourceCapability:
    """Documents what a specific audio source can actually provide.

    This is a static truth document, not an aspirational feature list.
    """
    source_type: AudioSourceType
    platform: str
    status: CapabilityStatus
    audio_side: AudioSide
    requires_permission: str
    android_version_constraint: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "source_type": self.source_type.value,
            "platform": self.platform,
            "status": self.status.value,
            "audio_side": self.audio_side.value,
            "requires_permission": self.requires_permission,
            "android_version_constraint": self.android_version_constraint,
            "notes": self.notes,
        }


# Verified capability matrix — reflects actual platform capabilities
CAPABILITY_MATRIX: List[SourceCapability] = [
    # ---- Android ----
    SourceCapability(
        source_type=AudioSourceType.USER_PROVIDED_RECORDING,
        platform="android",
        status=CapabilityStatus.AVAILABLE,
        audio_side=AudioSide.UNKNOWN,  # Depends on what the user recorded
        requires_permission="none (user selects file)",
        notes="User explicitly uploads a recording. Highest trust path.",
    ),
    SourceCapability(
        source_type=AudioSourceType.MICROPHONE,
        platform="android",
        status=CapabilityStatus.AVAILABLE,
        audio_side=AudioSide.LOCAL_ONLY,
        requires_permission="RECORD_AUDIO",
        android_version_constraint="All versions",
        notes="Captures local microphone only. On speakerphone, may partially capture remote audio through the mic, but this is NOT guaranteed or reliable.",
    ),
    SourceCapability(
        source_type=AudioSourceType.USER_DICTATED,
        platform="android",
        status=CapabilityStatus.AVAILABLE,
        audio_side=AudioSide.UNKNOWN,
        requires_permission="none",
        notes="User types what was said. Text-only path.",
    ),
    SourceCapability(
        source_type=AudioSourceType.MESSAGE_FORWARD,
        platform="android",
        status=CapabilityStatus.AVAILABLE,
        audio_side=AudioSide.UNKNOWN,
        requires_permission="none",
        notes="User forwards chat messages. Text-only path.",
    ),
    SourceCapability(
        source_type=AudioSourceType.SYSTEM_CALL_AUDIO,
        platform="android",
        status=CapabilityStatus.NOT_AVAILABLE,
        audio_side=AudioSide.BOTH_SIDES,
        requires_permission="MODIFY_AUDIO_ROUTING (system signature only)",
        android_version_constraint="Android does not provide public API for third-party call audio capture",
        notes="Android does NOT expose cellular call audio to third-party apps. READ_CALL_LOG only gives metadata, not audio. AccessibilityService abuse is NOT used by LUMINA.",
    ),
    SourceCapability(
        source_type=AudioSourceType.VOIP_CALL_AUDIO,
        platform="android",
        status=CapabilityStatus.NOT_AVAILABLE,
        audio_side=AudioSide.BOTH_SIDES,
        requires_permission="app-specific audio routing integration",
        notes="Possible only if the VoIP app exposes audio streams. Requires per-app integration. Not generally available.",
    ),

    # ---- Browser ----
    SourceCapability(
        source_type=AudioSourceType.USER_PROVIDED_RECORDING,
        platform="browser",
        status=CapabilityStatus.AVAILABLE,
        audio_side=AudioSide.UNKNOWN,
        requires_permission="none (user selects file)",
        notes="User explicitly uploads a recording. Highest trust path.",
    ),
    SourceCapability(
        source_type=AudioSourceType.MICROPHONE,
        platform="browser",
        status=CapabilityStatus.AVAILABLE,
        audio_side=AudioSide.LOCAL_ONLY,
        requires_permission="getUserMedia (user grants microphone access)",
        notes="MediaRecorder captures local microphone only. Does NOT capture remote call audio. UI must say 'Recording microphone audio'.",
    ),
    SourceCapability(
        source_type=AudioSourceType.USER_DICTATED,
        platform="browser",
        status=CapabilityStatus.AVAILABLE,
        audio_side=AudioSide.UNKNOWN,
        requires_permission="none",
        notes="User types what was said. Text-only path.",
    ),
    SourceCapability(
        source_type=AudioSourceType.MESSAGE_FORWARD,
        platform="browser",
        status=CapabilityStatus.AVAILABLE,
        audio_side=AudioSide.UNKNOWN,
        requires_permission="none",
        notes="User forwards chat messages. Text-only path.",
    ),
    SourceCapability(
        source_type=AudioSourceType.SYSTEM_CALL_AUDIO,
        platform="browser",
        status=CapabilityStatus.NOT_AVAILABLE,
        audio_side=AudioSide.BOTH_SIDES,
        requires_permission="N/A",
        notes="Browsers have no API to capture phone call audio.",
    ),
]


def get_capability(source_type: AudioSourceType, platform: str) -> Optional[SourceCapability]:
    """Look up the capability for a specific source + platform."""
    for cap in CAPABILITY_MATRIX:
        if cap.source_type == source_type and cap.platform == platform:
            return cap
    return None


def get_available_sources(platform: str) -> List[SourceCapability]:
    """Get all available audio sources for a platform."""
    return [
        cap for cap in CAPABILITY_MATRIX
        if cap.platform == platform
        and cap.status in (CapabilityStatus.AVAILABLE, CapabilityStatus.PARTIALLY_AVAILABLE)
    ]


def get_unavailable_sources(platform: str) -> List[SourceCapability]:
    """Get all unavailable audio sources for a platform (for honest UI)."""
    return [
        cap for cap in CAPABILITY_MATRIX
        if cap.platform == platform
        and cap.status == CapabilityStatus.NOT_AVAILABLE
    ]


# ---- Audio Source Label Descriptions ----
#
# These labels are used in the UI. They must be truthful about what
# the audio source actually captures.

SOURCE_LABELS: Dict[AudioSourceType, Dict[str, str]] = {
    AudioSourceType.USER_PROVIDED_RECORDING: {
        "short": "Uploaded recording",
        "description": "Audio file you selected and uploaded",
        "ui_text": "Analyzing your uploaded recording",
    },
    AudioSourceType.MICROPHONE: {
        "short": "Microphone audio",
        "description": "Live microphone capture from your device",
        "ui_text": "Recording microphone audio",
    },
    AudioSourceType.USER_DICTATED: {
        "short": "Typed transcript",
        "description": "Text you typed or pasted",
        "ui_text": "Analyzing your transcript",
    },
    AudioSourceType.MESSAGE_FORWARD: {
        "short": "Forwarded message",
        "description": "Message or chat transcript you forwarded",
        "ui_text": "Analyzing forwarded messages",
    },
    AudioSourceType.SYSTEM_CALL_AUDIO: {
        "short": "System call audio",
        "description": "Both sides of a phone call (NOT available on this platform)",
        "ui_text": "System call audio is not available on this platform",
    },
    AudioSourceType.VOIP_CALL_AUDIO: {
        "short": "VoIP call audio",
        "description": "Audio from a VoIP application (requires integration)",
        "ui_text": "VoIP audio integration is not yet available",
    },
}


def get_honest_ui_text(source_type: AudioSourceType) -> str:
    """Get the honest, platform-truthful UI text for an audio source.

    This ensures LUMINA never claims to be doing something it cannot do.
    """
    labels = SOURCE_LABELS.get(source_type)
    if labels:
        return labels["ui_text"]
    return "Processing audio"
