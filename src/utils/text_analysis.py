#region Imports
import re

#endregion


#region Constants

# Swear word patterns (comprehensive list with common misspellings)
SWEAR_PATTERNS = [
    # F-word variations
    r'\bf[u\*]c?k+(?:ing|ed|er|s)?\b',
    r'\bf+[aeiou]*c?k+\b',
    r'\bfck(?:ing|ed|er|s)?\b',
    r'\bfuk(?:ing|ed|er|s)?\b',
    r'\bphuck(?:ing|ed|er|s)?\b',

    # S-word variations
    r'\bsh[i\*]t+(?:ty|ting|ted|s)?\b',
    r'\bsht(?:ty|ting|ted|s)?\b',
    r'\bshyt(?:ty|ting|ted|s)?\b',
    r'\bcr[a\*]p+(?:py|ping|ped|s)?\b',

    # A-word variations
    r'\bass+h[o\*]le?s?\b',
    r'\ba+rse+(?:hole)?s?\b',

    # D-word variations
    r'\bd[a\*]mn+(?:ed|ing|s)?\b',
    r'\bd[a\*]m+(?:ed|ing|s)?\b',

    # B-word variations
    r'\bb[i\*]tch+(?:ing|ed|es|y)?\b',
    r'\bbstard+s?\b',

    # Other common variations
    r'\bhell+\b',
    r'\bpiss+(?:ed|ing|es)?\b',
    r'\bc[o\*]ck+(?:s)?\b',
    r'\bd[i\*]ck+(?:s|head)?\b',
    r'\btw[a\*]t+s?\b',
]

# Specific phrase patterns
PERFECT_PATTERNS = [
    r'\bperfect!',
    r'\bperfect\.',
    r'\bexcellent!',
    r'\bexcellent\.',
]

ABSOLUTELY_RIGHT_PATTERNS = [
    r"\byou'?re?\s+absolutely\s+right\b",
    r"\byou\s+are\s+absolutely\s+right\b",
]

# Politeness patterns
THANK_PATTERNS = [
    r'\bthank+(?:s|you|u)?\b',
    r'\bthn?x\b',
    r'\bty\b',
    r'\bthanku\b',
    r'\bthnk+s?\b',
]

PLEASE_PATTERNS = [
    r'\bplease\b',
    r'\bpl[sz]e?\b',
    r'\bples[ae]?\b',
    r'\bpls\b',
]

#endregion


#region Functions


def count_swears(text: str | None) -> int:
    """
    Count swear words in text using comprehensive pattern matching.

    Args:
        text: Text to analyze

    Returns:
        Count of swear words found

    Reasons for failure:
        - None (returns 0 if text is None/empty)
    """
    if not text:
        return 0

    text_lower = text.lower()
    count = 0

    for pattern in SWEAR_PATTERNS:
        matches = re.findall(pattern, text_lower)
        count += len(matches)

    return count


def count_perfect_phrases(text: str | None) -> int:
    """
    Count instances of "Perfect!" in text.

    Args:
        text: Text to analyze

    Returns:
        Count of "Perfect!" phrases found
    """
    if not text:
        return 0

    text_lower = text.lower()
    count = 0

    for pattern in PERFECT_PATTERNS:
        matches = re.findall(pattern, text_lower)
        count += len(matches)

    return count


def count_absolutely_right_phrases(text: str | None) -> int:
    """
    Count instances of "You're absolutely right!" in text.

    Args:
        text: Text to analyze

    Returns:
        Count of "You're absolutely right!" phrases found
    """
    if not text:
        return 0

    text_lower = text.lower()
    count = 0

    for pattern in ABSOLUTELY_RIGHT_PATTERNS:
        matches = re.findall(pattern, text_lower)
        count += len(matches)

    return count


def count_thank_phrases(text: str | None) -> int:
    """
    Count instances of "thank you" and variations in text.

    Args:
        text: Text to analyze

    Returns:
        Count of thank you phrases found
    """
    if not text:
        return 0

    text_lower = text.lower()
    count = 0

    for pattern in THANK_PATTERNS:
        matches = re.findall(pattern, text_lower)
        count += len(matches)

    return count


def count_please_phrases(text: str | None) -> int:
    """
    Count instances of "please" and variations in text.

    Args:
        text: Text to analyze

    Returns:
        Count of please phrases found
    """
    if not text:
        return 0

    text_lower = text.lower()
    count = 0

    for pattern in PLEASE_PATTERNS:
        matches = re.findall(pattern, text_lower)
        count += len(matches)

    return count


def get_character_count(text: str | None) -> int:
    """
    Get character count of text.

    Args:
        text: Text to analyze

    Returns:
        Number of characters
    """
    if not text:
        return 0

    return len(text)


#endregion
