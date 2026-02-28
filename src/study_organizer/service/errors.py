from __future__ import annotations


class StudyOrganizerError(Exception):
    """Base error for the application."""


class ValidationError(StudyOrganizerError):
    pass


class ConflictError(StudyOrganizerError):
    """Raised when something already exists (e.g., duplicate module code)."""


class NotFoundError(StudyOrganizerError):
    pass


class StorageError(StudyOrganizerError):
    """Raised when persistence layer fails unexpectedly."""
