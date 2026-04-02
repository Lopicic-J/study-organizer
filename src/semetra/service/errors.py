from __future__ import annotations


class SemetraError(Exception):
    pass


class ValidationError(SemetraError):
    pass


class ConflictError(SemetraError):
    pass


class NotFoundError(SemetraError):
    pass


class StorageError(SemetraError):
    pass
