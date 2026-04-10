from enum import StrEnum


class AIOperation(StrEnum):
    EMBED = "embed"
    EXTRACT = "extract"
    REASON = "reason"
    TRANSCRIBE = "transcribe"
