"""GUI pages package — page classes for the application."""
from semetra.gui.pages.focus import FocusPage
from semetra.gui.pages.dashboard import DashboardPage
from semetra.gui.pages.modules import ModulesPage
from semetra.gui.pages.tasks import TasksPage
from semetra.gui.pages.calendar_page import CalendarPage
from semetra.gui.pages.timeline import TimelinePage
from semetra.gui.pages.study_plan import StudyPlanPage
from semetra.gui.pages.knowledge import KnowledgePage
from semetra.gui.pages.timer import TimerPage
from semetra.gui.pages.exam import ExamPage
from semetra.gui.pages.grades import GradesPage
from semetra.gui.pages.settings import SettingsPage
from semetra.gui.pages.credits import CreditsPage
from semetra.gui.pages.stundenplan import StundenplanPage
from semetra.gui.pages.coach import _CoachEngine, StudienChatPanel

__all__ = [
    "FocusPage",
    "DashboardPage",
    "ModulesPage",
    "TasksPage",
    "CalendarPage",
    "TimelinePage",
    "StudyPlanPage",
    "KnowledgePage",
    "TimerPage",
    "ExamPage",
    "GradesPage",
    "SettingsPage",
    "CreditsPage",
    "StundenplanPage",
    "_CoachEngine",
    "StudienChatPanel",
]
