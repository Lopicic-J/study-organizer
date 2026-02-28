from __future__ import annotations

from abc import ABC, abstractmethod

from study_organizer.domain.models import Deadline, Module


class Repository(ABC):
    @abstractmethod
    def add_module(self, module: Module) -> None: ...

    @abstractmethod
    def list_modules(self) -> list[Module]: ...

    @abstractmethod
    def add_deadline(self, deadline: Deadline) -> None: ...

    @abstractmethod
    def list_deadlines(self, module_code: str | None = None) -> list[Deadline]: ...
