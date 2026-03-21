from __future__ import annotations


class StudyOrganizerError(Exception):
    pass


class ValidationError(StudyOrganizerError):
    pass


class ConflictError(StudyOrganizerError):
    pass


class NotFoundError(StudyOrganizerError):
    pass


class StorageError(StudyOrganizerError):
    pass
