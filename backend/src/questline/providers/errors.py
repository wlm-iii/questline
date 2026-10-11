class ProviderUnavailable(Exception):
    """Client-safe message only; never embed credentials, transcripts, or upstream errors."""
