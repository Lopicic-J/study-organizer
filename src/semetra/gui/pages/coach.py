"""Coach and study chat functionality."""
from __future__ import annotations
import os

from typing import Optional, List, Dict
import json

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QTextEdit, QMessageBox, QFrame, QScrollArea, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QFont, QColor

from semetra.repo.sqlite_repo import SqliteRepo
from semetra.gui.widgets import make_scroll
from semetra.gui.i18n import tr
from semetra.gui.colors import _tc, get_accent_color
from semetra.gui.helpers import days_until
from semetra.gui.platform import _open_url_safe



class _CoachEngine:
    """
    Smarte Coach-Engine: Analysiert Studentendaten + Freitext-Input,
    navigiert direkt zu App-Tabs, öffnet YouTube-Videos und Web-Ressourcen.
    Aktions-Format in Quick-Replies: "ACTION|data|Label"
      NAV|<idx>|Label   → navigiert zur Seite idx und schließt Chat
      YT|<query>|Label  → öffnet YouTube-Suche im Browser
      WEB|<url>|Label   → öffnet URL im Browser
      (kein Präfix)     → wird als Textnachricht verarbeitet
    """

    # Seitenindizes (entsprechen SidebarWidget.NAV_ITEMS)
    PAGE_DASHBOARD    = 0
    PAGE_MODULE       = 1
    PAGE_AUFGABEN     = 2
    PAGE_KALENDER     = 3
    PAGE_STUNDENPLAN  = 4   # NEW
    PAGE_STUDIENPLAN  = 5
    PAGE_WISSEN       = 6
    PAGE_TIMER        = 7
    PAGE_PRÜFUNGEN    = 8
    PAGE_NOTEN        = 9
    PAGE_EINSTELLUNGEN = 10

    INTENTS = {
        "panic":      ["prüfung morgen", "prüfung übermorgen", "exam morgen", "keine zeit",
                       "zu spät", "panic", "panik", "deadline", "abgabe morgen",
                       "klausur morgen", "klausur übermorgen", "alles vergessen"],
        "start":      ["weiß nicht wo", "wo anfangen", "nicht wissen", "keine ahnung",
                       "überfordert", "zu viel", "chaos", "verloren", "nicht klar",
                       "wo fange ich an", "was soll ich tun", "was zuerst"],
        "motivation": ["keine lust", "nicht motiviert", "unmotiviert", "faul", "müde",
                       "aufgegeben", "hoffnungslos", "sinn", "warum", "bored", "langweilig"],
        "progress":   ["wie stehe ich", "fortschritt", "wie weit", "schafft das",
                       "schaffe ich das", "reicht das", "genug gelernt", "auf kurs"],
        "time":       ["keine zeit", "zu beschäftigt", "wenig zeit", "nur kurz",
                       "heute keine", "5 minuten", "schnell", "kurz"],
        "grade":      ["note", "durchschnitt", "ziel", "bestehen", "punktzahl",
                       "wie viel brauche", "wie gut muss", "nicht bestanden"],
        "greeting":   ["hallo", "hi", "hey", "guten morgen", "guten tag", "servus",
                       "was kann", "wie funktioniert", "hilf mir", "was bist du"],
        "youtube":    ["youtube", "video", "videos", "tutorial", "erklär", "erklärung",
                       "vorlesung", "lernvideo", "schauen", "anschauen", "vl zu"],
        "resource":   ["website", "webseite", "artikel", "blog", "buch", "materialien",
                       "ressourcen", "quellen", "links", "wo lerne ich", "wo finde ich",
                       "lernmaterial", "unterlagen", "skript"],
        "explain":    ["wie funktioniert", "wie funktionieren", "was ist", "was sind",
                       "erkläre mir", "erkläre", "erklär mir", "wie geht", "wie macht man",
                       "was bedeutet", "definition von", "einführung", "grundlagen von",
                       "zeig mir wie", "ich verstehe nicht", "ich check nicht"],
        "exam_entry": ["prüfung am", "klausur am", "exam am", "prüfungstermin",
                       "prüfung eintragen", "klausur eintragen", "trage.*prüfung",
                       "trage.*ein", "füge.*prüfung", "merk dir", "merke dir",
                       "habe eine prüfung", "hab eine prüfung"],
        "navigate":   ["öffne", "gehe zu", "zeig mir die", "navigiere", "wechsel",
                       "zum timer", "zu den aufgaben", "zur noten", "zum kalender",
                       "zum studienplan", "zum wissen", "zum dashboard"],
        "exam_plan":  ["lernplan", "plan erstellen", "studienplan", "wie lerne ich",
                       "lernstrategie", "vorbereitung", "crashplan", "wie bereite ich"],
        "timer_req":  ["timer starten", "pomodoro starten", "session starten",
                       "lerneinheit starten", "starte timer", "starte pomodoro"],
    }

    # Fach-Erkennungsmuster → (Anzeigename, Suchbegriffe)
    SUBJECTS = [
        ("Mathematik",         ["mathematik", "mathe", "math", "maths"]),
        ("Analysis",           ["analysis", "differential", "integral", "ableitung"]),
        ("Lineare Algebra",    ["lineare algebra", "vektoren", "matrizen", "matrix"]),
        ("Statistik",          ["statistik", "wahrscheinlichkeit", "stochastik", "statistisch"]),
        ("Algorithmen",        ["algorithmen", "algorithmus", "datenstrukturen", "komplexität", "big o"]),
        ("Programmierung",     ["python", "java", "c++", "c#", "programmier", "coding", "code schreiben"]),
        ("Datenbanken",        ["sql", "datenbank", "database", "nosql", "mongodb", "relational"]),
        ("Netzwerke",          ["netzwerk", "tcp", "ip", "routing", "osi", "protokoll", "netzwerktechnik"]),
        ("Betriebssysteme",    ["betriebssystem", "operating system", "prozesse", "threads", "kernel"]),
        ("Webentwicklung",     ["html", "css", "javascript", "webentwicklung", "react", "frontend"]),
        ("Software Engineering",["software engineering", "design pattern", "architektur", "agile", "scrum"]),
        ("Machine Learning",   ["machine learning", "ki", "neural", "deep learning", "ml", "künstliche intelligenz"]),
        ("Physik",             ["physik", "mechanik", "thermodynamik", "elektrodynamik"]),
        ("Informatik",         ["informatik", "computer science"]),
    ]

    # Kuratierte Ressourcen pro Fach (inkl. Wikipedia-Links)
    RESOURCES: dict = {
        "Mathematik": [
            ("📐 Khan Academy Mathe", "https://de.khanacademy.org/math"),
            ("📐 Mathebibel", "https://www.mathebibel.de"),
            ("📖 Wikipedia: Mathematik", "https://de.wikipedia.org/wiki/Mathematik"),
            ("📐 Mathe online", "https://www.matheonline.at"),
        ],
        "Analysis": [
            ("📐 Khan Academy Calculus", "https://www.khanacademy.org/math/calculus-1"),
            ("📖 Wikipedia: Analysis", "https://de.wikipedia.org/wiki/Analysis"),
            ("📖 Wikipedia: Differentialrechnung", "https://de.wikipedia.org/wiki/Differentialrechnung"),
            ("📖 Wikipedia: Integralrechnung", "https://de.wikipedia.org/wiki/Integralrechnung"),
        ],
        "Lineare Algebra": [
            ("🔢 3Blue1Brown – Essence of LA", "https://www.youtube.com/playlist?list=PLZHQObOWTQDPD3MizzM2xVFitgF8hE_ab"),
            ("🔢 Khan Academy Linear Algebra", "https://www.khanacademy.org/math/linear-algebra"),
            ("📖 Wikipedia: Lineare Algebra", "https://de.wikipedia.org/wiki/Lineare_Algebra"),
        ],
        "Statistik": [
            ("📊 Khan Academy Statistics", "https://www.khanacademy.org/math/statistics-probability"),
            ("📊 StatistikGuru", "https://statistikguru.de"),
            ("📖 Wikipedia: Statistik", "https://de.wikipedia.org/wiki/Statistik"),
            ("📊 Crashkurs Statistik (YT)", "https://www.youtube.com/results?search_query=statistik+crashkurs+deutsch"),
        ],
        "Algorithmen": [
            ("🔍 Visualgo – Algorithmen visualisiert", "https://visualgo.net/de"),
            ("🔍 Big-O Cheat Sheet", "https://www.bigocheatsheet.com"),
            ("📖 Wikipedia: Algorithmus", "https://de.wikipedia.org/wiki/Algorithmus"),
            ("🔍 CS50 Harvard (kostenlos)", "https://cs50.harvard.edu/x"),
        ],
        "Programmierung": [
            ("💻 Python Dokumentation", "https://docs.python.org/3/"),
            ("💻 W3Schools", "https://www.w3schools.com"),
            ("📖 Wikipedia: Programmierung", "https://de.wikipedia.org/wiki/Programmierung"),
            ("💻 freeCodeCamp", "https://www.freecodecamp.org"),
        ],
        "Datenbanken": [
            ("🗄 SQLZoo – interaktiv SQL üben", "https://sqlzoo.net"),
            ("🗄 SQL Tutorial", "https://www.sqltutorial.org"),
            ("📖 Wikipedia: Relationale Datenbank", "https://de.wikipedia.org/wiki/Relationale_Datenbank"),
            ("📖 Wikipedia: SQL", "https://de.wikipedia.org/wiki/SQL"),
        ],
        "Netzwerke": [
            ("🌐 Cisco Networking Academy", "https://www.netacad.com"),
            ("📖 Wikipedia: Computernetz", "https://de.wikipedia.org/wiki/Computernetz"),
            ("📖 Wikipedia: OSI-Modell", "https://de.wikipedia.org/wiki/OSI-Modell"),
            ("🌐 Computerphile – Netzwerke (YT)", "https://www.youtube.com/results?search_query=netzwerke+grundlagen+deutsch"),
        ],
        "Betriebssysteme": [
            ("📖 Wikipedia: Betriebssystem", "https://de.wikipedia.org/wiki/Betriebssystem"),
            ("📖 Wikipedia: Prozess (Informatik)", "https://de.wikipedia.org/wiki/Prozess_(Informatik)"),
            ("💡 OSDev Wiki", "https://wiki.osdev.org/Main_Page"),
        ],
        "Webentwicklung": [
            ("🌐 MDN Web Docs", "https://developer.mozilla.org/de/"),
            ("🌐 W3Schools", "https://www.w3schools.com"),
            ("📖 Wikipedia: Webentwicklung", "https://de.wikipedia.org/wiki/Webentwicklung"),
            ("🌐 The Odin Project", "https://www.theodinproject.com"),
        ],
        "Machine Learning": [
            ("🤖 fast.ai (kostenlos)", "https://www.fast.ai"),
            ("🤖 Google ML Crash Course", "https://developers.google.com/machine-learning/crash-course"),
            ("📖 Wikipedia: Maschinelles Lernen", "https://de.wikipedia.org/wiki/Maschinelles_Lernen"),
            ("🤖 3Blue1Brown – Neural Networks", "https://www.youtube.com/playlist?list=PLZHQObOWTQDNU6R1_67000Dx_ZCJB-3pi"),
        ],
        "Software Engineering": [
            ("⚙ Refactoring Guru – Design Patterns", "https://refactoring.guru/design-patterns"),
            ("📖 Wikipedia: Software Engineering", "https://de.wikipedia.org/wiki/Software_Engineering"),
            ("📖 Wikipedia: Entwurfsmuster", "https://de.wikipedia.org/wiki/Entwurfsmuster"),
            ("⚙ Clean Code – Zusammenfassung", "https://www.youtube.com/results?search_query=clean+code+deutsch"),
        ],
        "Informatik": [
            ("📖 Wikipedia: Informatik", "https://de.wikipedia.org/wiki/Informatik"),
            ("🔍 CS50 Harvard (kostenlos)", "https://cs50.harvard.edu/x"),
            ("💻 freeCodeCamp", "https://www.freecodecamp.org"),
        ],
        "Physik": [
            ("📖 Wikipedia: Physik", "https://de.wikipedia.org/wiki/Physik"),
            ("📐 Khan Academy Physik", "https://www.khanacademy.org/science/physics"),
            ("📖 Wikipedia: Mechanik", "https://de.wikipedia.org/wiki/Mechanik"),
        ],
    }

    # Modul-Code → (YouTube-Suchbegriffe, Web-Ressourcen)
    # Maßgeschneidert für FFHS Informatik BSc
    MODULE_RESOURCES: dict = {
        "AnPy": (
            ["Analysis mit Python scipy numpy", "Python numerische Methoden Tutorial Deutsch",
             "Analysis Grundlagen FH Deutsch"],
            [("🐍 scipy Docs", "https://docs.scipy.org/doc/scipy/"),
             ("🐍 numpy Tutorial", "https://numpy.org/doc/stable/user/quickstart.html")],
        ),
        "BDN": (
            ["Big Data Hadoop Spark Grundlagen Deutsch", "NoSQL MongoDB Tutorial Deutsch",
             "Big Data Architektur erklärt"],
            [("🗄 MongoDB Docs", "https://www.mongodb.com/docs/manual/"),
             ("📊 Apache Spark", "https://spark.apache.org/docs/latest/")],
        ),
        "C++": (
            ["C++ Tutorial Deutsch FH Grundlagen", "C++ Objektorientierung erklärt",
             "C++ Zeiger Pointer erklärt Deutsch"],
            [("💻 cppreference", "https://de.cppreference.com/w/"),
             ("💻 learncpp.com", "https://www.learncpp.com")],
        ),
        "ClCo": (
            ["Cloud Computing Grundlagen Deutsch AWS Azure", "IaaS PaaS SaaS erklärt",
             "Cloud Architecture Tutorial"],
            [("☁ AWS Grundlagen", "https://aws.amazon.com/de/getting-started/"),
             ("☁ Azure Fundamentals", "https://learn.microsoft.com/de-de/azure/")],
        ),
        "DBS": (
            ["SQL Tutorial Deutsch Grundlagen FH", "Datenbanksysteme ER-Modell erklärt",
             "SQL Joins GROUP BY erklärt Deutsch"],
            [("🗄 SQLZoo Übungen", "https://sqlzoo.net"),
             ("🗄 SQL Tutorial", "https://www.sqltutorial.org"),
             ("🗄 DB-Fiddle", "https://www.db-fiddle.com")],
        ),
        "D&A": (
            ["Datenstrukturen Algorithmen FH Deutsch", "Big-O Notation erklärt Deutsch",
             "Sortieralgorithmen Visualisierung"],
            [("🔍 Visualgo", "https://visualgo.net/de"),
             ("🔍 Big-O Cheatsheet", "https://www.bigocheatsheet.com"),
             ("🔍 CS50 Harvard", "https://cs50.harvard.edu/x")],
        ),
        "DevOps": (
            ["DevOps Grundlagen Deutsch CI/CD", "Docker Tutorial Deutsch Grundlagen",
             "Git Workflow DevOps erklärt"],
            [("⚙ Docker Docs", "https://docs.docker.com/get-started/"),
             ("⚙ GitHub Actions", "https://docs.github.com/de/actions")],
        ),
        "DMathLS": (
            ["Diskrete Mathematik FH Deutsch Grundlagen", "Graphentheorie erklärt Deutsch",
             "Lineare Systeme Signalverarbeitung FH"],
            [("📐 Diskrete Mathe – Khanacademy", "https://www.khanacademy.org/computing/computer-science/cryptography"),
             ("📐 Mathebibel", "https://www.mathebibel.de/diskrete-mathematik")],
        ),
        "GTI": (
            ["Grundlagen Technische Informatik FH Deutsch", "Logikgatter Schaltkreise erklärt",
             "Von-Neumann-Architektur erklärt Deutsch"],
            [("💡 nand2tetris", "https://www.nand2tetris.org"),
             ("💡 Rechnerarchitektur Wikipedia", "https://de.wikipedia.org/wiki/Rechnerarchitektur")],
        ),
        "ISich": (
            ["Informationssicherheit Grundlagen FH Deutsch", "IT-Sicherheit CIA-Prinzip erklärt",
             "Kryptographie Grundlagen Deutsch"],
            [("🔒 BSI Grundschutz", "https://www.bsi.bund.de/DE/Themen/Unternehmen-und-Organisationen/Standards-und-Zertifizierung/IT-Grundschutz/IT-Grundschutz-Kompendium/it-grundschutz-kompendium_node.html"),
             ("🔒 OWASP Top 10", "https://owasp.org/www-project-top-ten/")],
        ),
        "INSich": (
            ["Internetsicherheit TLS HTTPS erklärt Deutsch", "Netzwerksicherheit Firewall VPN",
             "Ethical Hacking Grundlagen"],
            [("🔒 OWASP", "https://owasp.org"),
             ("🔒 TryHackMe", "https://tryhackme.com")],
        ),
        "JAF": (
            ["Java Tutorial Deutsch Grundlagen FH", "Java OOP erklärt Deutsch",
             "Java Collections Streams Tutorial"],
            [("☕ Java Docs Oracle", "https://docs.oracle.com/javase/tutorial/"),
             ("☕ Baeldung Java", "https://www.baeldung.com")],
        ),
        "JEA": (
            ["Java Enterprise Spring Framework Tutorial", "JEE Jakarta EE Deutsch",
             "Spring Boot Tutorial Deutsch"],
            [("☕ Spring.io Guides", "https://spring.io/guides"),
             ("☕ Baeldung Spring", "https://www.baeldung.com/spring-tutorial")],
        ),
        "JPL": (
            ["Java Projektarbeit Best Practices", "Clean Code Java Tutorial",
             "Java Design Patterns erklärt Deutsch"],
            [("☕ Refactoring Guru", "https://refactoring.guru/de/design-patterns/java"),
             ("☕ Baeldung", "https://www.baeldung.com")],
        ),
        "LinAlg": (
            ["Lineare Algebra FH Deutsch Grundlagen", "Matrizen Vektoren erklärt Deutsch",
             "Lineare Algebra 3Blue1Brown Deutsch"],
            [("🔢 3Blue1Brown LA", "https://www.youtube.com/playlist?list=PLZHQObOWTQDPD3MizzM2xVFitgF8hE_ab"),
             ("🔢 Khan Academy", "https://www.khanacademy.org/math/linear-algebra")],
        ),
        "MaLe": (
            ["Machine Learning Grundlagen Deutsch FH", "Supervised Learning erklärt Deutsch",
             "Neural Networks Grundlagen Deutsch"],
            [("🤖 fast.ai", "https://www.fast.ai"),
             ("🤖 Google ML Crash Course", "https://developers.google.com/machine-learning/crash-course"),
             ("🤖 Kaggle Learn", "https://www.kaggle.com/learn")],
        ),
        "MCI": (
            ["Mensch-Computer-Interaktion HCI Grundlagen", "Usability UX Design Grundlagen Deutsch",
             "User Interface Design Prinzipien"],
            [("🖥 Nielsen Norman Group", "https://www.nngroup.com/articles/"),
             ("🖥 Material Design", "https://m3.material.io")],
        ),
        "OEM": (
            ["Mathematik Grundlagen FH Vorkurs Deutsch", "Analysis Grundlagen Studium Einstieg",
             "Mathe Vorkurs Studium"],
            [("📐 Khan Academy Mathe", "https://de.khanacademy.org/math"),
             ("📐 Mathebibel", "https://www.mathebibel.de")],
        ),
        "PMG": (
            ["Projektmanagement Grundlagen Deutsch FH", "PRINCE2 Agile Scrum Grundlagen",
             "Projektplanung Gantt-Diagramm"],
            [("📋 PMBOK Guide", "https://www.pmi.org/pmbok-guide-standards"),
             ("📋 Scrum.org", "https://www.scrum.org/resources/what-is-scrum")],
        ),
        "RN": (
            ["Rechnernetze Grundlagen FH Deutsch", "OSI-Modell alle Schichten erklärt Deutsch",
             "TCP/IP Routing Grundlagen Deutsch"],
            [("🌐 Computernetze Wikipedia", "https://de.wikipedia.org/wiki/Computernetz"),
             ("🌐 Cisco Networking Basics", "https://www.netacad.com/catalog/networking")],
        ),
        "SWEM": (
            ["Software Engineering Modellierung UML FH", "UML Klassendiagramm erklärt Deutsch",
             "Anforderungsanalyse Use Case Diagram"],
            [("⚙ UML Tutorial", "https://www.uml.org"),
             ("⚙ Draw.io UML", "https://app.diagrams.net")],
        ),
        "SWEA": (
            ["Software Architektur Design Patterns FH Deutsch", "Microservices vs Monolith erklärt",
             "Clean Architecture Robert Martin"],
            [("⚙ Refactoring Guru", "https://refactoring.guru/de/design-patterns"),
             ("⚙ Martin Fowler", "https://martinfowler.com/architecture/")],
        ),
        "SWQ": (
            ["Software Qualität Testing FH Deutsch", "Unit Tests JUnit Deutsch Tutorial",
             "Code Review Best Practices"],
            [("🔬 JUnit 5 Docs", "https://junit.org/junit5/docs/current/user-guide/"),
             ("🔬 Clean Code Zusammenfassung", "https://www.google.com/search?q=clean+code+zusammenfassung+deutsch")],
        ),
        "VSA": (
            ["Verteilte Systeme Grundlagen FH Deutsch", "REST API Microservices Tutorial Deutsch",
             "Kafka RabbitMQ Message Queue erklärt"],
            [("🌐 Distributed Systems Primer", "https://github.com/donnemartin/system-design-primer"),
             ("🌐 REST API Tutorial", "https://restfulapi.net")],
        ),
        "WS": (
            ["Wahrscheinlichkeitsrechnung Statistik FH Deutsch", "Normalverteilung erklärt Deutsch",
             "Statistik Hypothesentest Grundlagen"],
            [("📊 Khan Academy Statistik", "https://www.khanacademy.org/math/statistics-probability"),
             ("📊 StatistikGuru", "https://statistikguru.de")],
        ),
        "WebE": (
            ["Web Engineering Full-Stack Tutorial Deutsch", "REST API JavaScript Node.js Tutorial",
             "Web Architektur HTTP erklärt Deutsch"],
            [("🌐 MDN Web Docs", "https://developer.mozilla.org/de/"),
             ("🌐 The Odin Project", "https://www.theodinproject.com")],
        ),
        "WebG": (
            ["HTML CSS Grundlagen Tutorial Deutsch FH", "JavaScript Grundlagen Tutorial Deutsch",
             "Responsive Design CSS Flexbox erklärt"],
            [("🌐 MDN Web Docs", "https://developer.mozilla.org/de/"),
             ("🌐 W3Schools", "https://www.w3schools.com"),
             ("🌐 freeCodeCamp", "https://www.freecodecamp.org")],
        ),
        "WiAr": (
            ["Wissenschaftliches Arbeiten FH Deutsch", "Literaturrecherche Zitieren Hochschule",
             "Hausarbeit schreiben Tipps"],
            [("📝 Zitation – Uni Oldenburg", "https://www.uni-oldenburg.de/studium/schreibwerkstatt/"),
             ("📝 Citavi", "https://www.citavi.com/de")],
        ),
        "EnAr": (
            ["Enterprise Architecture TOGAF Grundlagen Deutsch", "IT-Architektur Framework FH",
             "Business Architecture Tutorial"],
            [("🏢 TOGAF", "https://www.opengroup.org/togaf"),
             ("🏢 Enterprise Architecture Wikipedia", "https://de.wikipedia.org/wiki/Enterprise-Architektur")],
        ),
        "IKS": (
            ["Linux Server Konfiguration Tutorial Deutsch", "Apache Nginx Installation Linux",
             "Server Administration Deutsch FH"],
            [("🖥 Linux Documentation", "https://www.kernel.org/doc/html/latest/"),
             ("🖥 DigitalOcean Tutorials", "https://www.digitalocean.com/community/tutorials")],
        ),
        "InnT": (
            ["Innovation Management Technologie FH Deutsch", "Design Thinking Agile FH",
             "Startup Methoden Lean Canvas"],
            [("💡 IDEO Design Thinking", "https://designthinking.ideo.com"),
             ("💡 Lean Startup", "http://theleanstartup.com")],
        ),
    }

    def __init__(self, repo: SqliteRepo):
        self.repo = repo

    # ── Hilfsmethoden ────────────────────────────────────────────────────────

    def _intent(self, text: str) -> str:
        import re as _re
        t = text.lower()
        # exam_entry: check regex patterns first (date in text = strong signal)
        if _re.search(r"\d{1,2}[./]\d{1,2}[./]\d{2,4}", t) and any(
                kw in t for kw in ["prüfung", "klausur", "exam", "trage", "eintrag"]):
            return "exam_entry"
        for intent, keywords in self.INTENTS.items():
            if any(kw in t for kw in keywords):
                return intent
        return "generic"

    def _detect_subject(self, text: str) -> Optional[str]:
        """Gibt den erkannten Fachnamen zurück, oder None."""
        t = text.lower()
        for subject, keywords in self.SUBJECTS:
            if any(kw in t for kw in keywords):
                return subject
        return None

    def _match_module(self, text: str) -> Optional[dict]:
        """
        Versucht, einen konkreten DB-Modul-Eintrag aus dem Freitext zu erkennen.
        Gibt das Modul-Dict zurück oder None.
        Scoring: jedes Wort des Modulnamens, das im Text vorkommt, zählt +1.
        Modulcode-Treffer zählt +5.
        """
        t = text.lower()
        best_mod = None
        best_score = 0
        all_modules = self.repo.list_modules("all")
        for m in all_modules:
            if not (int(m["in_plan"] or 1) if "in_plan" in m.keys() else 1):
                continue
            score = 0
            code = (m["code"] or "").lower()
            name = (m["name"] or "").lower()
            # Exakter Code-Treffer (z.B. "DBS", "WebG")
            if code and code in t:
                score += 5
            # Wörter aus dem Modulnamen
            name_words = [w for w in name.split() if len(w) > 3]
            for w in name_words:
                if w in t:
                    score += 1
            # Kurze Schlüsselwörter
            if score == 0:
                # Partielle Treffer (Substring-Match des Namens)
                name_parts = name.split(" – ")[0].split(" & ")[0].split(" und ")[0]
                if name_parts in t or any(p in t for p in name_parts.split()[:2] if len(p) > 3):
                    score += 1
            if score > best_score:
                best_score = score
                best_mod = dict(m)
        return best_mod if best_score > 0 else None

    def _module_links(self, mod: dict) -> tuple[list[str], list[str]]:
        """
        Gibt (yt_search_queries, web_resources_as_action_strings) für ein konkretes Modul zurück.
        Priorisiert MODULE_RESOURCES, fällt auf SUBJECTS/RESOURCES zurück.
        """
        code = (mod.get("code") or "").strip()
        name = mod.get("name") or "Modul"
        yt_queries: list[str] = []
        web_actions: list[str] = []

        if code in self.MODULE_RESOURCES:
            yt_q_list, web_res = self.MODULE_RESOURCES[code]
            for q in yt_q_list[:2]:
                yt_queries.append(self._yt(q, f"▶ {q[:35]}"))
            for label, url in web_res[:2]:
                web_actions.append(self._web(url, label[:40]))
        else:
            # Fallback: generische Suche basierend auf Modulname
            q = f"{name} FH Studium Tutorial Deutsch"
            yt_queries.append(self._yt(q, f"▶ {name[:28]} Tutorial"))
            google_url = (f"https://www.google.com/search?q="
                          f"{_urllib_parse.quote(name + ' FH Lernmaterial')}")
            web_actions.append(self._web(google_url, f"🔍 Google: {name[:28]}"))
        return yt_queries, web_actions

    @staticmethod
    def _parse_exam_date(text: str) -> Optional[str]:
        """Versucht, ein Datum aus deutschem Freitext zu parsen. Gibt ISO-String zurück oder None."""
        import re as _re2
        t = text.lower()
        # Format: 28.03.2026 / 28.03.26 / 28/03/2026
        m = _re2.search(r"(\d{1,2})[./](\d{1,2})[./](\d{2,4})", t)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if y < 100:
                y += 2000
            try:
                from datetime import date as _dt
                return _dt(y, mo, d).isoformat()
            except ValueError:
                pass
        # Format: "am 28. März" / "am 5. April 2026"
        month_map = {"januar":1,"february":2,"februar":2,"märz":3,"april":4,"mai":5,
                     "juni":6,"juli":7,"august":8,"september":9,"oktober":10,
                     "november":11,"dezember":12}
        m2 = _re2.search(r"(\d{1,2})\.\s*([a-zäöü]+)(?:\s+(\d{4}))?", t)
        if m2:
            d2, mon_str = int(m2.group(1)), m2.group(2)
            y2 = int(m2.group(3)) if m2.group(3) else date.today().year
            mo2 = month_map.get(mon_str)
            if mo2:
                try:
                    return date(y2, mo2, d2).isoformat()
                except ValueError:
                    pass
        return None

    def _build_rich_topic_html(self, topic: str, matched_mod: Optional[dict] = None) -> str:
        """Baut einen HTML-Block mit mehreren Links zu einem Thema (YouTube + Web + Wikipedia)."""
        q_de = _urllib_parse.quote(f"{topic} erklärt Deutsch")
        q_tut = _urllib_parse.quote(f"{topic} Tutorial Deutsch")
        q_fh  = _urllib_parse.quote(f"{topic} Grundlagen FH Studium")
        yt1   = f"https://www.youtube.com/results?search_query={q_de}"
        yt2   = f"https://www.youtube.com/results?search_query={q_tut}"
        yt3   = f"https://www.youtube.com/results?search_query={q_fh}"
        goog  = f"https://www.google.com/search?q={_urllib_parse.quote(topic + ' Lernmaterial Studium')}"
        wiki  = f"https://de.wikipedia.org/wiki/{_urllib_parse.quote(topic.replace(' ','_'))}"
        khan  = f"https://www.khanacademy.org/search?page_search_query={_urllib_parse.quote(topic)}"

        parts = [f"<b>🔍 Ressourcen zu &ldquo;{topic}&rdquo;:</b><br><br>"]

        # ── YouTube ──
        parts.append("<b>🎬 YouTube-Videos:</b><br>")
        parts.append(f'&nbsp;&nbsp;<a href="{yt1}">▶ {topic} erklärt (Deutsch)</a><br>')
        parts.append(f'&nbsp;&nbsp;<a href="{yt2}">▶ {topic} Tutorial (Deutsch)</a><br>')
        parts.append(f'&nbsp;&nbsp;<a href="{yt3}">▶ {topic} FH-Niveau (Deutsch)</a><br><br>')

        # ── Wikipedia (immer anzeigen) ──
        parts.append("<b>📖 Wikipedia:</b><br>")
        parts.append(f'&nbsp;&nbsp;<a href="{wiki}">📖 Wikipedia: {topic}</a><br><br>')

        # ── Modulspezifische Ressourcen ──
        if matched_mod:
            code = (matched_mod.get("code") or "").strip()
            if code in self.MODULE_RESOURCES:
                yt_qs, web_rs = self.MODULE_RESOURCES[code]
                if yt_qs:
                    extra_q = _urllib_parse.quote(yt_qs[0])
                    parts.append(f'&nbsp;&nbsp;<a href="https://www.youtube.com/results?search_query={extra_q}">'
                                  f'⭐ {yt_qs[0][:55]}</a><br><br>')
                if web_rs:
                    parts.append("<b>📚 Empfohlene Webseiten:</b><br>")
                    for label, url in web_rs[:4]:
                        parts.append(f'&nbsp;&nbsp;<a href="{url}">{label}</a><br>')
                    parts.append("<br>")
        else:
            # Generische Fach-Ressourcen
            subj = self._detect_subject(topic)
            if subj and subj in self.RESOURCES:
                parts.append("<b>📚 Empfohlene Webseiten:</b><br>")
                for label, url in self.RESOURCES[subj][:4]:
                    parts.append(f'&nbsp;&nbsp;<a href="{url}">{label}</a><br>')
                parts.append("<br>")
            else:
                parts.append("<b>🌐 Weitere Quellen:</b><br>")
                parts.append(f'&nbsp;&nbsp;<a href="{goog}">🔍 Google: {topic} Lernmaterial</a><br>')
                parts.append(f'&nbsp;&nbsp;<a href="{khan}">📐 Khan Academy: {topic}</a><br>')
                parts.append("<br>")

        parts.append(
            "<span style='font-size:11px;color:#6B7280;'>"
            "Klick auf einen Link &mdash; öffnet in deinem Browser.</span>"
        )
        return "".join(parts)

    @staticmethod
    def _nav(idx: int, label: str) -> str:
        return f"NAV|{idx}|{label}"

    @staticmethod
    def _yt(query: str, label: str) -> str:
        return f"YT|{_urllib_parse.quote(query)}|{label}"

    @staticmethod
    def _web(url: str, label: str) -> str:
        return f"WEB|{url}|{label}"

    def _situation(self) -> dict:
        """Snapshot der aktuellen Studentensituation."""
        today = date.today()
        today_str = today.isoformat()
        streak = self.repo.get_study_streak()
        week_secs = self.repo.seconds_studied_week(today - timedelta(days=today.weekday()))
        active_mods = self.repo.list_modules("active")
        all_tasks = self.repo.list_tasks(status="Open")
        overdue = [t for t in all_tasks if (t["due_date"] or "") < today_str and t["due_date"]]
        due_today = [t for t in all_tasks if (t["due_date"] or "") == today_str]
        upcoming = self.repo.upcoming_exams(within_days=14)
        most_urgent = upcoming[0] if upcoming else None
        urgent_days = days_until(most_urgent["exam_date"]) if most_urgent else None
        sr_due = 0
        for m in active_mods:
            for t in self.repo.list_topics(m["id"]):
                lr = t["last_reviewed"] if "last_reviewed" in t.keys() else ""
                lvl = int(t["knowledge_level"]) if t["knowledge_level"] else 0
                if lr and lvl < 3:
                    try:
                        if (today - datetime.fromisoformat(lr).date()).days >= 3:
                            sr_due += 1
                    except Exception:
                        pass
        return {
            "streak": streak, "week_h": week_secs / 3600,
            "active_mods": active_mods, "n_mods": len(active_mods),
            "open_tasks": len(all_tasks), "overdue": overdue, "due_today": due_today,
            "most_urgent": most_urgent, "urgent_days": urgent_days,
            "upcoming": upcoming, "sr_due": sr_due,
        }

    # ── Hauptmethode ─────────────────────────────────────────────────────────

    def respond(self, text: str, ctx: Optional[dict] = None) -> tuple[str, list[str]]:
        """
        Gibt (message_html, list_of_action_strings) zurück.
        Aktions-Format: "ACTION|data|Label" oder einfacher Text (→ als Nachricht schicken).
        ctx: Gesprächskontext {"last_subject", "last_intent", "turn"}
        """
        try:
            return self._respond_inner(text, ctx)
        except Exception as _e:
            import traceback; traceback.print_exc()
            return (
                "\u26a0\ufe0f Kurzer Fehler aufgetreten \u2014 versuch es nochmal oder nenn mir ein Fach.",
                ["Wo anfangen?", self._nav(self.PAGE_TIMER, "\u23f1 Timer"), "Lernressourcen"],
            )

    def _respond_inner(self, text: str, ctx: Optional[dict] = None) -> tuple[str, list[str]]:
        ctx = ctx or {}
        intent = self._intent(text)
        # 1) Erst: konkretes DB-Modul suchen (genaueste Erkennung)
        matched_mod = self._match_module(text)
        # 2) Dann: generische Fach-Erkennung (Fallback)
        subject = self._detect_subject(text)
        # 3) Dann: Kontext übernehmen wenn nichts erkannt
        if not subject and not matched_mod:
            subject = ctx.get("last_subject")
        last_intent = ctx.get("last_intent")
        last_mod_code = ctx.get("last_mod_code")
        turn = ctx.get("turn", 0)

        # Kontext mit Modul-Code aus Kontext befüllen falls kein neuer Treffer
        if not matched_mod and last_mod_code:
            all_m = self.repo.list_modules("all")
            for m in all_m:
                if (m["code"] if "code" in m.keys() else "") == last_mod_code:
                    matched_mod = dict(m)
                    break

        s = self._situation()
        mu = s["most_urgent"]
        name = mu["name"] if mu else "dein Modul"

        # ── Follow-up-Erkennung (kontextsensitiv) ───────────────────────────
        follow_up_kw = ["was sonst", "noch mehr", "andere", "weiteres", "mehr davon",
                        "was noch", "alternative", "sonst noch", "weitere links"]
        is_followup = any(kw in text.lower() for kw in follow_up_kw)

        if is_followup and last_intent in ("youtube", "resource"):
            if matched_mod:
                yt_actions, web_actions = self._module_links(matched_mod)
                mod_name = matched_mod.get("name", "Modul")
                msg = (f"🔎 Noch mehr zu <b>{mod_name}</b>:<br><br>"
                       f"Weitere Ressourcen und Übungslinks:")
                replies = web_actions[:2] + yt_actions[:1]
                google_url = (f"https://www.google.com/search?q="
                              f"{_urllib_parse.quote(mod_name + ' Übungsaufgaben Lösungen')}")
                replies.append(self._web(google_url, f"🔍 Übungsaufgaben: {mod_name[:20]}"))
                return msg, replies[:3]
            elif subject:
                resources = self.RESOURCES.get(subject, [])
                google_url = (f"https://www.google.com/search?q="
                              f"{_urllib_parse.quote(subject + ' Studium Übungen Aufgaben')}")
                msg = (f"🔎 Noch mehr zu <b>{subject}</b>:")
                replies = [self._web(url, label[:35]) for label, url in resources[1:3]]
                replies.append(self._web(google_url, f"🔍 Übungen: {subject}"))
                return msg, replies

        # ── Prüfungs-Eintragung (Multi-Turn) ────────────────────────────────
        pending = ctx.get("pending")

        # Fortsetzung: Modul-Auswahl nach Datum
        if pending and pending.get("action") == "exam_entry" and not pending.get("mod_id"):
            exam_date = pending.get("date")
            # Versuche Modul aus diesem Text zu erkennen
            chosen = self._match_module(text)
            if not chosen:
                # Nummern-Auswahl (1, 2, 3 …)?
                import re as _re3
                m_num = _re3.match(r"^\s*(\d+)\s*$", text.strip())
                if m_num:
                    idx_c = int(m_num.group(1)) - 1
                    pending_mods = pending.get("mod_list", [])
                    if 0 <= idx_c < len(pending_mods):
                        chosen = pending_mods[idx_c]
            if chosen:
                mod_id   = chosen.get("id")
                mod_name = chosen.get("name", "Modul")
                self.repo.update_module(mod_id, exam_date=exam_date)
                ctx["pending"] = None
                msg = (f"✅ <b>Prüfungstermin gespeichert!</b><br><br>"
                       f"📅 <b>{mod_name}</b> — "
                       f"Prüfung am <b>{exam_date}</b><br><br>"
                       f"Ich habe das Datum in deinem Modulplan eingetragen. "
                       f"Du siehst es im Kalender und im Prüfungsübersicht-Tab.")
                return msg, [
                    self._nav(self.PAGE_KALENDER, "📅 Kalender"),
                    self._nav(self.PAGE_PRÜFUNGEN, "📝 Prüfungen"),
                    f"Lernplan für {mod_name[:20]} erstellen",
                ]
            else:
                # Modul immer noch unklar
                active = self.repo.list_modules("active") or self.repo.list_modules("all")
                mod_list = [dict(m) for m in active[:6]]
                ctx["pending"]["mod_list"] = mod_list
                lines = "".join(
                    f"&nbsp;&nbsp;<b>{i+1}.</b> {m.get('name','?')} "
                    f"<span style='color:#6B7280;'>({m.get('code','')})</span><br>"
                    for i, m in enumerate(mod_list)
                )
                return (
                    f"❓ Für welches Modul ist die Prüfung am <b>{exam_date}</b>?<br><br>"
                    f"{lines}<br>Gib die Nummer oder den Namen ein:",
                    [m.get("name", "?")[:28] for m in mod_list[:3]],
                )

        # Neue Prüfungs-Eintragung
        if intent == "exam_entry":
            exam_date = self._parse_exam_date(text)
            # Modul aus Text erkennen?
            exam_mod = self._match_module(text) or (matched_mod if matched_mod else None)

            if exam_date and exam_mod:
                mod_id   = exam_mod.get("id")
                mod_name = exam_mod.get("name", "Modul")
                ctx["pending"] = None
                # Gewichtung aus Text? (z.B. "40%" / "gewichtung 40")
                import re as _re4
                w_match = _re4.search(r"(\d+)\s*%", text)
                weighting = float(w_match.group(1)) / 100.0 if w_match else None
                if weighting is not None:
                    self.repo.update_module(mod_id, exam_date=exam_date, weighting=weighting)
                    w_note = f", Gewichtung {int(weighting*100)}%"
                else:
                    self.repo.update_module(mod_id, exam_date=exam_date)
                    w_note = ""
                msg = (f"✅ <b>Eingetragen!</b><br><br>"
                       f"📅 <b>{mod_name}</b>{w_note}<br>"
                       f"Prüfung am <b>{exam_date}</b><br><br>"
                       f"Möchtest du gleich einen Lernplan dafür erstellen?")
                return msg, [
                    f"📋 Lernplan für {mod_name[:20]}",
                    self._nav(self.PAGE_KALENDER, "📅 Kalender"),
                    self._nav(self.PAGE_PRÜFUNGEN, "📝 Prüfungen"),
                ]

            if exam_date and not exam_mod:
                # Datum bekannt, Modul fehlt → nachfragen
                active = self.repo.list_modules("active") or self.repo.list_modules("all")
                mod_list = [dict(m) for m in active[:6]]
                ctx["pending"] = {"action": "exam_entry", "date": exam_date,
                                  "mod_id": None, "mod_list": mod_list}
                lines = "".join(
                    f"&nbsp;&nbsp;<b>{i+1}.</b> {m.get('name','?')} "
                    f"<span style='color:#6B7280;'>({m.get('code','')})</span><br>"
                    for i, m in enumerate(mod_list)
                )
                return (
                    f"📅 Datum erkannt: <b>{exam_date}</b><br><br>"
                    f"Für welches Modul ist diese Prüfung?<br><br>{lines}<br>"
                    f"Gib die Nummer oder den Namen ein.",
                    [m.get("name", "?")[:28] for m in mod_list[:3]],
                )

            if not exam_date:
                # Kein Datum erkannt → Datum erfragen
                ctx["pending"] = {"action": "exam_entry", "date": None, "mod_id": None}
                return (
                    "📅 <b>Prüfungstermin eintragen</b><br><br>"
                    "Wann findet die Prüfung statt? Gib das Datum ein, z.B.:<br>"
                    "<i>28.03.2026</i> oder <i>28. April 2026</i>",
                    ["28.03.2026", "15.04.2026", "01.06.2026"],
                )

        # ── Erklärung + Multi-Link Antwort ──────────────────────────────────
        if intent == "explain":
            # Extrahiere das eigentliche Thema aus dem Text
            import re as _re5
            t_low = text.lower()
            # Strip intent keywords to get the actual topic
            for kw in ["wie funktioniert", "wie funktionieren", "was ist", "was sind",
                       "erkläre mir", "erkläre", "erklär mir", "wie geht", "wie macht man",
                       "was bedeutet", "definition von", "einführung in", "grundlagen von",
                       "zeig mir wie", "ich verstehe nicht", "ich check nicht",
                       "bitte erkläre", "bitte erklär"]:
                t_low = t_low.replace(kw, "").strip()
            # Remove trailing punctuation and filler
            t_low = _re5.sub(r"[?!.,]+$", "", t_low).strip()
            topic = t_low if len(t_low) > 1 else (
                matched_mod.get("name") if matched_mod else subject or text.strip())
            # Capitalize properly
            topic = topic.strip().title() if topic == topic.lower() else topic.strip()

            html_links = self._build_rich_topic_html(topic, matched_mod)
            quick = []
            if matched_mod:
                quick.append(f"📋 Lernplan für {matched_mod.get('name','')[:20]}")
                quick.append(self._nav(self.PAGE_WISSEN, "🧠 Wissensmap"))
            else:
                quick.append(self._yt(f"{topic} erklärt Deutsch", f"▶ Mehr Videos: {topic[:22]}"))
                quick.append(self._nav(self.PAGE_TIMER, "⏱ Jetzt lernen"))
            quick.append("Noch mehr Ressourcen")
            return html_links, quick[:3]

        # ── YouTube-Suche ───────────────────────────────────────────────────
        if intent == "youtube":
            # Konkretes Modul gefunden → spezifische Queries
            if matched_mod:
                mod_name = matched_mod.get("name", "Modul")
                code = matched_mod.get("code", "")
                yt_actions, web_actions = self._module_links(matched_mod)
                has_exam_soon = mu and s.get("urgent_days") and s["urgent_days"] <= 14
                exam_note = (f"<br><br>⚠️ Prüfung in <b>{s['urgent_days']} Tagen</b> — "
                             f"Fokus auf Prüfungsrelevantes!" if has_exam_soon and
                             mu and (mu["name"] if "name" in mu.keys() else "") == mod_name else "")
                msg = (f"🎬 YouTube für <b>{mod_name}</b>:{exam_note}<br><br>"
                       f"Klick auf den Link — öffnet direkt in YouTube.")
                replies = yt_actions[:2] + web_actions[:1]
                return msg, replies[:3]

            if subject:
                q1 = f"{subject} Studium Erklärung Deutsch"
                q2 = f"{subject} Tutorial Deutsch"
                has_exam_soon = mu and s.get("urgent_days") and s["urgent_days"] <= 14
                msg = (f"🎬 YouTube für <b>{subject}</b>:<br><br>"
                       f"Klick auf den gewünschten Link — er öffnet YouTube direkt.")
                replies = [
                    self._yt(q1, f"▶ {subject} Erklärung"),
                    self._yt(q2, f"▶ {subject} Tutorial"),
                ]
                if has_exam_soon:
                    replies.append(self._yt(
                        f"{subject} Prüfungsvorbereitung kompakt", "▶ Prüfungsvorbereitung"))
                else:
                    replies.append(self._yt(f"{subject} Zusammenfassung", "▶ Zusammenfassung"))
                return msg, replies
            # Kein Fach → aus Kontext oder Module vorschlagen
            mod_names = [m["name"] for m in s["active_mods"][:3]]
            if mod_names:
                msg = (f"🎬 Zu welchem Fach suchst du Videos?<br><br>"
                       f"Deine aktiven Module:")
                replies = [self._yt(f"{n} Studium Erklärung Deutsch", f"▶ {n[:22]}") for n in mod_names[:2]]
                replies.append(self._yt("Lerntechniken Studium Motivation", "▶ Lerntipps"))
            else:
                msg = ("🎬 Zu welchem Fach suchst du Videos?<br><br>"
                       "Nenn mir das Thema, z.B. <i>&ldquo;Analysis Videos&rdquo;</i>.")
                replies = [
                    self._yt("Mathematik Studium Erklärung", "▶ Mathe"),
                    self._yt("Programmierung Python Tutorial Deutsch", "▶ Python"),
                    self._yt("Lerntechniken Studium", "▶ Lerntipps"),
                ]
            return msg, replies

        # ── Web-Ressourcen ──────────────────────────────────────────────────
        if intent == "resource":
            # Konkretes Modul → spezifische Ressourcen
            if matched_mod:
                mod_name = matched_mod.get("name", "Modul")
                yt_actions, web_actions = self._module_links(matched_mod)
                google_url = (f"https://www.google.com/search?q="
                              f"{_urllib_parse.quote(mod_name + ' FH Lernmaterial Skript')}")
                msg = (f"🌐 Ressourcen für <b>{mod_name}</b>:<br><br>"
                       f"Klick auf den Link — öffnet direkt im Browser.")
                replies = web_actions[:2] + [self._web(google_url, f"🔍 Skripte: {mod_name[:20]}")]
                return msg, replies[:3]
            if subject:
                resources = self.RESOURCES.get(subject, [])
                google_url = (f"https://www.google.com/search?q="
                              f"{_urllib_parse.quote(subject + ' Lernmaterial Studium')}")
                wiki_url = (f"https://de.wikipedia.org/wiki/"
                            f"{_urllib_parse.quote(subject.title())}")
                msg = (f"🌐 Ressourcen für <b>{subject}</b>:<br><br>"
                       f"Klick auf den Link — öffnet direkt im Browser.")
                replies = [self._web(url, label[:35]) for label, url in resources[:2]]
                if not replies:
                    replies.append(self._web(wiki_url, f"📖 Wikipedia: {subject[:20]}"))
                replies.append(self._web(google_url, f"🔍 Google: {subject} lernen"))
                return msg, replies
            # Kein Fach erkannt → Module aus DB anbieten
            all_mods = self.repo.list_modules("active")
            msg = ("🌐 Zu welchem Fach/Modul suchst du Ressourcen?<br><br>"
                   "Nenn den Modulnamen oder Code, z.B. <i>DBS</i>, <i>Algorithmen</i>.")
            replies = []
            for m in all_mods[:2]:
                yt_a, web_a = self._module_links(dict(m))
                if web_a:
                    replies.append(web_a[0])
            replies.append(self._web("https://de.khanacademy.org", "📚 Khan Academy"))
            return msg, replies[:3]

        # ── Tab-Navigation ──────────────────────────────────────────────────
        if intent == "navigate":
            t = text.lower()
            nav_map = [
                (["timer", "pomodoro"],                       self.PAGE_TIMER,        "⏱ Timer"),
                (["aufgaben", "tasks", "todo", "aufgabe"],    self.PAGE_AUFGABEN,     "✅ Aufgaben"),
                (["noten", "grade", "notenseite"],            self.PAGE_NOTEN,        "📈 Noten"),
                (["prüfungen", "exams", "exam", "klausur"],   self.PAGE_PRÜFUNGEN,    "🎯 Prüfungen"),
                (["wissen", "knowledge", "themen", "topics"], self.PAGE_WISSEN,       "🧠 Wissen"),
                (["kalender", "calendar"],                    self.PAGE_KALENDER,     "📅 Kalender"),
                (["module", "fächer", "fach"],                self.PAGE_MODULE,       "📚 Module"),
                (["studienplan", "plan"],                     self.PAGE_STUDIENPLAN,  "📊 Studienplan"),
                (["dashboard", "übersicht", "home"],          self.PAGE_DASHBOARD,    "🏠 Dashboard"),
            ]
            for keywords, idx, label in nav_map:
                if any(kw in t for kw in keywords):
                    msg = f"Navigiere zu <b>{label}</b>."
                    return msg, [self._nav(idx, f"→ {label} öffnen")]
            msg = "Wohin soll ich navigieren? Wähle eine Seite:"
            return msg, [
                self._nav(self.PAGE_DASHBOARD,   "🏠 Dashboard"),
                self._nav(self.PAGE_TIMER,       "⏱ Timer"),
                self._nav(self.PAGE_PRÜFUNGEN,   "🎯 Prüfungen"),
            ]

        # ── Timer starten ───────────────────────────────────────────────────
        if intent == "timer_req":
            mod_hint = f"Fokus: <b>{name}</b>." if mu else "Wähle dein Modul im Timer."
            msg = (f"⏱ <b>Lernsession starten!</b><br><br>"
                   f"25 Minuten Pomodoro — kein Handy, kein Social Media.<br>{mod_hint}")
            return msg, [
                self._nav(self.PAGE_TIMER, "⏱ Timer öffnen"),
                self._yt("Pomodoro Focus Music Study", "🎵 Fokus-Musik (YT)"),
            ]

        # ── Lernplan erstellen ──────────────────────────────────────────────
        if intent == "exam_plan":
            if not s["upcoming"]:
                msg = ("📋 Für einen konkreten Lernplan brauche ich deine Prüfungstermine.<br><br>"
                       "Trag dein Prüfungsdatum beim Modul ein — dann erstelle ich dir einen maßgeschneiderten Plan.")
                return msg, [
                    self._nav(self.PAGE_PRÜFUNGEN, "🎯 Prüfungstermin eintragen"),
                    self._nav(self.PAGE_MODULE,    "📚 Module anschauen"),
                ]
            if mu:
                d = s["urgent_days"] or 14
                available_h = max(d * 5, 2)
                topics = self.repo.list_topics(mu["id"])
                weak = [t for t in topics if (int(t["knowledge_level"]) if t["knowledge_level"] else 0) < 3]
                msg = (f"📋 <b>Lernplan für {name}</b> — {d} Tage verbleibend:<br><br>")
                if weak:
                    msg += f"<b>Priorisierte Themen</b> ({len(weak)} schwach):<br>"
                    for t in weak[:5]:
                        lvl = int(t["knowledge_level"]) if t["knowledge_level"] else 0
                        msg += f"&nbsp;&nbsp;{'🔴' if lvl <= 1 else '🟠'} {t['title']}<br>"
                    if len(weak) > 5:
                        msg += f"&nbsp;&nbsp;… und {len(weak) - 5} weitere<br>"
                    msg += f"<br>⏰ Verfügbar: ~{available_h:.0f}h → ~{available_h/max(len(weak),1):.1f}h/Thema"
                else:
                    msg += "✅ Alle Themen sind stark! Fokus auf Wiederholung und Übungsaufgaben."
                return msg, [
                    self._nav(self.PAGE_WISSEN,    "🧠 Themen ansehen"),
                    self._nav(self.PAGE_TIMER,     "⏱ Lernsession starten"),
                    self._nav(self.PAGE_PRÜFUNGEN, "🎯 Prüfungsübersicht"),
                ]
            return ("📋 Öffne deinen Studienplan:",
                    [self._nav(self.PAGE_STUDIENPLAN, "📊 Studienplan öffnen")])

        # ── Begrüßung ───────────────────────────────────────────────────────
        if intent == "greeting":
            if s["n_mods"] == 0:
                msg = (
                    "👋 <b>Hallo! Ich bin dein Studien-Coach.</b><br><br>"
                    "Ich helfe dir mit Lernplänen, YouTube-Videos, "
                    "Lernressourcen und App-Navigation — offline &amp; kostenlos.<br><br>"
                    "Lege zuerst deine Module an, damit ich dir gezielt helfen kann."
                )
                return msg, [
                    self._nav(self.PAGE_MODULE,       "📚 Module anlegen"),
                    self._nav(self.PAGE_STUDIENPLAN,  "📊 Studienplan ansehen"),
                    self._yt("Lerntechniken Studium Motivation",
                             "🎬 Lerntipps Videos"),
                ]
            if s["urgent_days"] is not None and s["urgent_days"] <= 5:
                msg = (
                    f"👋 <b>Hallo!</b> Ich sehe eine dringende Situation:<br><br>"
                    f"🚨 <b>{name}</b> steht in <b>{s['urgent_days']} Tagen</b> an.<br><br>"
                    f"Soll ich dir einen Crashplan erstellen?"
                )
                return msg, [
                    "🚨 Crashplan erstellen",
                    self._nav(self.PAGE_WISSEN, "🧠 Schwache Themen ansehen"),
                    self._nav(self.PAGE_TIMER,  "⏱ Lernsession starten"),
                    self._yt(f"{name} Prüfungsvorbereitung kompakt",
                             f"🎬 Videos: {name[:16]}"),
                ]
            if s["overdue"]:
                t = s["overdue"][0]
                n_over = len(s["overdue"])
                msg = (
                    f"👋 <b>Hallo!</b> Ein paar Dinge fallen mir auf:<br><br>"
                    f"⚠️ <b>{n_over} überfällige Aufgabe{'n' if n_over > 1 else ''}</b> — "
                    f"Dringlichste: <b>&ldquo;{t['title']}&rdquo;</b><br><br>"
                    f"Was willst du zuerst angehen?"
                )
                return msg, [
                    self._nav(self.PAGE_AUFGABEN, "✅ Aufgaben öffnen"),
                    "📋 Lernplan erstellen",
                    "📊 Fortschritt zeigen",
                ]
            streak_emoji = " 🔥" if s["streak"] > 2 else ""
            msg = (
                f"👋 <b>Hallo!</b> Hier ist dein aktueller Stand:<br><br>"
                f"📚 <b>{s['n_mods']} Module</b> aktiv · "
                f"✅ <b>{s['open_tasks']} Aufgaben</b> offen · "
                f"📅 Streak <b>{s['streak']} Tage</b>{streak_emoji}<br><br>"
                f"Was kann ich für dich tun?"
            )
            return msg, [
                "📊 Fortschritt zeigen",
                "🎬 Lernvideos finden",
                "📋 Lernplan erstellen",
                self._nav(self.PAGE_TIMER, "⏱ Timer starten"),
            ]

        # ── Panik / Prüfungsstress ──────────────────────────────────────────
        elif intent == "panic":
            if not s["upcoming"]:
                msg = ("🚨 Das klingt stressig — aber ich finde keine Prüfungen in deinem Kalender.<br><br>"
                       "Trag dein Prüfungsdatum ein, dann erstelle ich dir sofort einen Crashplan.")
                return msg, [
                    self._nav(self.PAGE_PRÜFUNGEN, "🎯 Prüfungsdatum eintragen"),
                    "Was soll ich ohne Datum tun?",
                ]
            if mu and s["urgent_days"] is not None:
                d = s["urgent_days"]
                available_h = max(d * 5, 2)
                topics = self.repo.list_topics(mu["id"])
                weak = [t for t in topics if (int(t["knowledge_level"]) if t["knowledge_level"] else 0) < 3]
                msg = (f"🚨 <b>Crashplan: {name}</b><br>"
                       f"⏳ <b>{d} Tag{'e' if d != 1 else ''}</b> · ~<b>{available_h:.0f}h</b> Lernzeit<br><br>")
                if weak:
                    msg += f"<b>{len(weak)} schwache Themen</b> (Priorität):<br>"
                    for t in weak[:5]:
                        lvl = int(t["knowledge_level"]) if t["knowledge_level"] else 0
                        msg += f"&nbsp;&nbsp;{'🔴' if lvl <= 1 else '🟠'} {t['title']}<br>"
                    if len(weak) > 5:
                        msg += f"&nbsp;&nbsp;… +{len(weak) - 5} weitere<br>"
                    msg += "<br>💡 <b>Rote zuerst → orange → Wiederholung</b>"
                else:
                    msg += "✅ Deine Themen sind stabil. Fokus auf Übungsaufgaben & Wiederholung."
                yt_q = f"{mu['name']} Prüfungsvorbereitung"
                return msg, [
                    self._nav(self.PAGE_TIMER,  "⏱ Session starten"),
                    self._nav(self.PAGE_WISSEN, "🧠 Themen öffnen"),
                    self._yt(yt_q, f"🎬 Videos: {mu['name'][:16]}"),
                ]
            exams_str = ", ".join(f"<b>{e['name']}</b> ({days_until(e['exam_date'])}d)"
                                  for e in s["upcoming"][:2])
            return (f"🚨 Bald: {exams_str}.", [
                "📋 Crashplan erstellen",
                self._nav(self.PAGE_TIMER, "⏱ Timer starten"),
            ])

        # ── Wo anfangen ─────────────────────────────────────────────────────
        elif intent == "start":
            if s["n_mods"] == 0:
                return ("🧭 Zuerst Module anlegen — das dauert 2 Minuten.",
                        [self._nav(self.PAGE_MODULE, "📚 Module anlegen")])
            if s["overdue"]:
                t = s["overdue"][0]
                msg = (f"🧭 <b>Priorität 1:</b> Aufgabe <b>&ldquo;{t['title']}&rdquo;</b> ist überfällig.<br>"
                       f"Danach: 25 Min für <b>{name}</b>.")
                return msg, [
                    self._nav(self.PAGE_AUFGABEN, "✅ Aufgaben öffnen"),
                    self._nav(self.PAGE_TIMER,    "⏱ Timer starten"),
                ]
            elif mu and s["urgent_days"] is not None and s["urgent_days"] <= 10:
                msg = (f"🧭 Dringlichstes: <b>{name}</b> in <b>{s['urgent_days']} Tagen</b>.<br><br>"
                       f"Starte jetzt eine 25-Min Session. Kein Handy, kein Social Media.")
                return msg, [
                    self._nav(self.PAGE_TIMER,  "⏱ 25-Min Session"),
                    "📋 Crashplan erstellen",
                    self._nav(self.PAGE_WISSEN, "🧠 Schwache Themen"),
                ]
            elif s["sr_due"] > 0:
                msg = (f"🧭 Bestes was du jetzt tun kannst: "
                       f"<b>{s['sr_due']} Thema{'s' if s['sr_due'] != 1 else ''}</b> wiederholen. "
                       f"20 Minuten — stärkt Langzeitgedächtnis.")
                return msg, [
                    self._nav(self.PAGE_WISSEN, "🧠 Zur Wissensseite"),
                    self._nav(self.PAGE_TIMER,  "⏱ 25-Min Timer"),
                ]
            else:
                return ("🧭 Starte eine 25-Min Lerneinheit. Der Anfang ist das Schwerste.", [
                    self._nav(self.PAGE_TIMER,       "⏱ Timer starten"),
                    self._nav(self.PAGE_STUDIENPLAN, "📊 Studienplan"),
                ])

        # ── Motivation ──────────────────────────────────────────────────────
        elif intent == "motivation":
            import random as _rnd
            streak_msg = (f"<br><br>💪 Du hast bereits <b>{s['streak']} Tage</b> in Folge gelernt "
                          f"— das ist bemerkenswert. Nicht aufhören!"
                          if s["streak"] > 2 else "")
            quotes = [
                ("Der Anfang ist die Hälfte des Ganzen.", "Aristoteles"),
                ("Bildung ist die mächtigste Waffe, die du einsetzen kannst, um die Welt zu verändern.", "Nelson Mandela"),
                ("Es ist nicht genug, zu wissen — man muss auch anwenden.", "Goethe"),
                ("Investiere in dich selbst — das ist die beste Investition.", "Warren Buffett"),
                ("Du musst nicht groß sein, um anzufangen — aber du musst anfangen, um groß zu sein.", "Zig Ziglar"),
            ]
            quote, author = _rnd.choice(quotes)
            mod_hint = (f"Starte mit <b>{name}</b> — auch nur 25 Minuten."
                        if mu else "Starte mit dem ersten Thema auf deiner Liste.")
            msg = (f"😊 <b>Keine Lust? Völlig normal.</b>{streak_msg}<br><br>"
                   f"🧠 <b>Trick #1:</b> Nur 5 Minuten anfangen. Dann meistens nicht mehr aufhören.<br>"
                   f"🧠 <b>Trick #2:</b> Ablenkungen weg — Handy in Flugmodus, 1 Tab offen.<br>"
                   f"🧠 <b>Trick #3:</b> {mod_hint}<br><br>"
                   f"💬 <i>&ldquo;{quote}&rdquo; — {author}</i>")
            return msg, [
                self._nav(self.PAGE_TIMER, "⏱ 5-Min Pomodoro starten"),
                self._yt("Studium Motivation Produktivität Tipps", "🎬 Motivations-Videos"),
                self._web("https://de.wikipedia.org/wiki/Pomodoro-Technik",
                          "📖 Wikipedia: Pomodoro-Technik"),
            ]

        # ── Fortschritt ─────────────────────────────────────────────────────
        elif intent == "progress":
            week_h = s["week_h"]
            if mu:
                target_h = self.repo.ects_target_hours(mu["id"])
                studied_h = self.repo.seconds_studied_for_module(mu["id"]) / 3600
                pct = min(100, int(studied_h / target_h * 100)) if target_h > 0 else 0
                msg = (f"📊 <b>Dein Fortschritt:</b><br><br>"
                       f"• Diese Woche: <b>{week_h:.1f}h</b><br>"
                       f"• Lernserie: <b>{s['streak']} Tage</b><br>"
                       f"• {name}: <b>{pct}%</b> ({studied_h:.1f}h / {target_h:.0f}h)<br>"
                       f"• Offene Aufgaben: <b>{s['open_tasks']}</b><br><br>")
                if pct < 30 and s["urgent_days"] is not None and s["urgent_days"] <= 14:
                    msg += f"⚠️ {name} braucht dringend mehr Aufmerksamkeit!"
                elif pct >= 80:
                    msg += "🎉 Super — du bist auf einem sehr guten Weg!"
                else:
                    msg += "👍 Solider Fortschritt. Bleib dran!"
            else:
                msg = (f"📊 Diese Woche: <b>{week_h:.1f}h</b> · "
                       f"Streak: <b>{s['streak']} Tage</b> · "
                       f"Aufgaben: <b>{s['open_tasks']}</b>")
            return msg, [
                self._nav(self.PAGE_NOTEN,    "📈 Noten ansehen"),
                self._nav(self.PAGE_PRÜFUNGEN,"🎯 Prüfungsübersicht"),
                "Was als nächstes?",
            ]

        # ── Wenig Zeit ──────────────────────────────────────────────────────
        elif intent == "time":
            msg = (f"⚡ Selbst <b>15 Minuten</b> bringen was!<br><br>"
                   f"In 15 Min: 1 Thema wiederholen"
                   f"{', 1 überfällige Aufgabe' if s['overdue'] else ''}"
                   f" oder Stichpunkte für {name} durchgehen.")
            return msg, [
                self._nav(self.PAGE_TIMER,    "⏱ 15-Min Timer"),
                self._nav(self.PAGE_AUFGABEN, "✅ Aufgaben"),
            ]

        # ── Noten & Ziele ────────────────────────────────────────────────────
        elif intent == "grade":
            if not mu:
                return ("📈 Für eine Notenprognose Module mit Prüfungsterminen eintragen.",
                        [self._nav(self.PAGE_MODULE, "📚 Module anlegen")])
            avg = self.repo.module_weighted_grade(mu["id"])
            mod_full = self.repo.get_module(mu["id"])
            tg_raw = (mod_full or {}).get("target_grade")
            tg = float(tg_raw) if tg_raw else None
            if avg is not None and tg is not None:
                diff = avg - tg
                if diff >= 0:
                    msg = (f"📈 <b>{name}</b>: <b>{avg:.1f}%</b> — "
                           f"<b>{diff:+.1f}%</b> über Ziel {tg:.1f}%. Sehr gut!")
                else:
                    msg = (f"📈 <b>{name}</b>: <b>{avg:.1f}%</b>, "
                           f"Ziel {tg:.1f}% — <b>{abs(diff):.1f}%</b> darunter.")
            elif avg is not None:
                msg = f"📈 Schnitt für <b>{name}</b>: <b>{avg:.1f}%</b>. Kein Ziel gesetzt."
            else:
                msg = f"📈 Noch keine Noten für <b>{name}</b> eingetragen."
            return msg, [
                self._nav(self.PAGE_NOTEN, "📈 Notenseite öffnen"),
                "Was soll ich tun?",
            ]

        # ── Generic / Modul oder Fach erkannt ───────────────────────────────
        else:
            if matched_mod:
                # Konkretes DB-Modul erkannt → maßgeschneiderte Antwort
                mod_name = matched_mod.get("name", "Modul")
                code = matched_mod.get("code", "")
                yt_actions, web_actions = self._module_links(matched_mod)
                extra = ""
                if mu and s.get("urgent_days") and s["urgent_days"] <= 14:
                    if (mu["name"] if "name" in mu.keys() else "") == mod_name:
                        extra = (f"<br><br>⚠️ Prüfung in <b>{s['urgent_days']} Tagen</b> — "
                                 f"Fokus auf Prüfungsthemen!")
                msg = (f"🔍 <b>{mod_name}</b>{extra}<br><br>"
                       f"Ich habe spezifische Ressourcen für dieses Modul:")
                replies = yt_actions[:1] + web_actions[:2]
                return msg, replies[:3]

            if subject:
                # Fach erkannt (generisch) → Ressourcen
                resources = self.RESOURCES.get(subject, [])
                google_url = (f"https://www.google.com/search?q="
                              f"{_urllib_parse.quote(subject + ' Studium Lernmaterial')}")
                extra = ""
                if mu and s.get("urgent_days") and s["urgent_days"] <= 14:
                    extra = (f"<br><br>⚠️ Prüfung in <b>{s['urgent_days']} Tagen</b> — "
                             f"Prüfungsthemen priorisieren!")
                msg = (f"🔍 <b>{subject}</b>{extra}")
                replies = [self._yt(f"{subject} Studium Erklärung Deutsch", f"🎬 YouTube: {subject[:20]}")]
                if resources:
                    label, url = resources[0]
                    replies.append(self._web(url, label[:35]))
                replies.append(self._web(google_url, f"🔍 Google: {subject[:20]}"))
                return msg, replies

            # Kein Intent, kein Fach erkannt → auf aktuelle Situation eingehen
            # Smarte Situation-basierte Antwort statt random-Tipp
            if s["overdue"]:
                t_item = s["overdue"][0]
                msg = (f"👀 Ich schaue auf deine Situation:<br><br>"
                       f"Du hast <b>{len(s['overdue'])} überfällige Aufgabe(n)</b> — "
                       f"die Dringlichste: <b>&ldquo;{t_item['title']}&rdquo;</b>.<br><br>"
                       f"Was meintest du genau? Nenn mir ein Fach, Thema oder dein Problem.")
                return msg, [
                    self._nav(self.PAGE_AUFGABEN, "✅ Aufgaben öffnen"),
                    "📋 Lernplan erstellen",
                    "🎬 Lernvideo suchen",
                ]
            if mu and s.get("urgent_days") and s["urgent_days"] <= 10:
                msg = (f"👀 Ich sehe: <b>{name}</b> steht in <b>{s['urgent_days']} Tagen</b> an.<br><br>"
                       f"Was beschäftigt dich? Nenn mir ein Thema, dann helfe ich gezielt.")
                return msg, [
                    f"🎬 Videos zu {name[:20]}",
                    "📋 Crashplan erstellen",
                    self._nav(self.PAGE_TIMER, "⏱ Session starten"),
                ]
            # Wirklich generisch → Hilfe-Menü mit aktiven Vorschlägen
            week_note = (f"Diese Woche: <b>{s['week_h']:.1f}h</b> gelernt"
                         f"{' · 🔥 ' + str(s['streak']) + ' Tage Serie' if s['streak'] > 2 else ''}.")
            msg = (
                f"💬 <b>Kein Problem — ich helfe gerne!</b><br>"
                f"<span style='color:#6B7280;font-size:12px;'>{week_note}</span><br><br>"
                "Schreib mir z.B.:<br>"
                "&rarr; Ein <b>Fach</b>: <i>&bdquo;Analysis&ldquo;</i>, <i>&bdquo;SQL&ldquo;</i><br>"
                "&rarr; Eine <b>Aktion</b>: <i>&bdquo;Videos&ldquo;</i>, <i>&bdquo;Lernplan&ldquo;</i><br>"
                "&rarr; Ein <b>Problem</b>: <i>&bdquo;Ich bin gestresst&ldquo;</i><br>"
                "&rarr; Einen <b>Termin</b>: <i>&bdquo;Prüfung DBS am 15.04&ldquo;</i>"
            )
            mod_names = [m["name"] for m in s["active_mods"][:2]]
            replies = [self._yt(f"{n} Tutorial Deutsch", f"🎬 Videos: {n[:18]}")
                       for n in mod_names]
            replies.append(self._nav(self.PAGE_TIMER, "⏱ Timer starten"))
            if not replies:
                replies = [
                    "📋 Lernplan erstellen",
                    self._nav(self.PAGE_TIMER, "⏱ Timer starten"),
                    self._web("https://de.wikipedia.org/wiki/Lerntechnik",
                              "📖 Wikipedia: Lerntechniken"),
                ]
            return msg, replies[:4]


class StudienChatPanel(QDialog):
    """
    Konversations-Coach mit Tab-Navigation, YouTube-Suche und Web-Ressourcen.
    Quick-Reply-Format: "ACTION|data|Label" oder reiner Text.
    """

    def __init__(self, repo: SqliteRepo, switch_page_cb=None, parent=None):
        super().__init__(parent)
        self._repo = repo
        self._switch_page = switch_page_cb   # callable(int) → navigiert zur Seite
        self._engine = _CoachEngine(repo)
        self._messages: list[dict] = []
        # Gesprächskontext — wird laufend aktualisiert
        self._ctx: dict = {
            "last_subject":  None,  # zuletzt erwähntes Fach (z.B. "Analysis")
            "last_mod_code": None,  # zuletzt erkannter Modul-Code (z.B. "DBS")
            "last_intent":   None,  # letzter erkannter Intent
            "turn":          0,     # Gesprächsrunden-Zähler
            "pending":       None,  # laufender Multi-Turn-Flow (z.B. exam_entry)
        }
        self.setWindowTitle("💬  Studien-Coach")
        self.setMinimumSize(520, 640)
        self.resize(580, 700)
        self._build()
        self._welcome()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── Coach Header ─────────────────────────────────────────────────────
        hdr = QFrame()
        hdr.setAttribute(Qt.WA_StyledBackground, True)
        hdr.setStyleSheet(
            "QFrame{"
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #6D28D9,stop:1 #7C3AED);"
            "border-bottom:1px solid rgba(255,255,255,0.15);"
            "}"
        )
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(16, 12, 16, 12)
        hdr_lay.setSpacing(12)

        # Avatar
        avatar = QLabel("🤖")
        avatar.setFixedSize(42, 42)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(
            "background:rgba(255,255,255,0.18);border-radius:21px;"
            "font-size:21px;"
        )
        hdr_lay.addWidget(avatar)

        # Title + status
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_lbl = QLabel("Studien-Coach")
        title_lbl.setStyleSheet(
            "color:#FFFFFF;font-size:15px;font-weight:bold;background:transparent;"
        )
        title_col.addWidget(title_lbl)

        status_row = QHBoxLayout()
        status_row.setSpacing(5)
        status_row.setContentsMargins(0, 0, 0, 0)
        dot_lbl = QLabel("●")
        dot_lbl.setStyleSheet("color:#4ADE80;font-size:9px;background:transparent;")
        sub_lbl = QLabel("KI-Assistent · offline &amp; kostenlos")
        sub_lbl.setTextFormat(Qt.RichText)
        sub_lbl.setStyleSheet(
            "color:rgba(255,255,255,0.72);font-size:11px;background:transparent;"
        )
        status_row.addWidget(dot_lbl)
        status_row.addWidget(sub_lbl)
        status_row.addStretch()
        title_col.addLayout(status_row)
        hdr_lay.addLayout(title_col, 1)

        # Action buttons
        clr_btn = QPushButton("🗑")
        clr_btn.setFixedSize(32, 32)
        clr_btn.setToolTip("Chat leeren")
        clr_btn.setStyleSheet(
            "QPushButton{background:rgba(255,255,255,0.15);color:white;"
            "border:none;border-radius:16px;font-size:14px;}"
            "QPushButton:hover{background:rgba(255,255,255,0.28);}"
        )
        clr_btn.clicked.connect(self._clear_chat)
        hdr_lay.addWidget(clr_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(32, 32)
        close_btn.setToolTip("Schließen")
        close_btn.setStyleSheet(
            "QPushButton{background:rgba(255,255,255,0.15);color:white;"
            "border:none;border-radius:16px;font-size:13px;}"
            "QPushButton:hover{background:rgba(220,38,38,0.6);}"
        )
        close_btn.clicked.connect(self.reject)
        hdr_lay.addWidget(close_btn)
        lay.addWidget(hdr)

        # Chat area
        self._chat_sa = QScrollArea()
        self._chat_sa.setWidgetResizable(True)
        self._chat_sa.setFrameShape(QFrame.NoFrame)
        self._chat_container = QWidget()
        self._chat_container.setAttribute(Qt.WA_StyledBackground, True)
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setSpacing(10)
        self._chat_layout.setContentsMargins(12, 12, 12, 4)
        self._chat_layout.addStretch()
        self._chat_sa.setWidget(self._chat_container)
        lay.addWidget(self._chat_sa, 1)

        # ── Quick-Reply-Leiste ───────────────────────────────────────────────
        self._replies_scroll = QScrollArea()
        self._replies_scroll.setFrameShape(QFrame.NoFrame)
        self._replies_scroll.setFixedHeight(48)
        self._replies_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._replies_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._replies_scroll.setWidgetResizable(True)
        self._replies_w = QWidget()
        self._replies_w.setStyleSheet("background:transparent;")
        self._replies_lay = QHBoxLayout(self._replies_w)
        self._replies_lay.setContentsMargins(12, 6, 12, 6)
        self._replies_lay.setSpacing(8)
        self._replies_lay.addStretch()
        self._replies_scroll.setWidget(self._replies_w)
        lay.addWidget(self._replies_scroll)

        # Eingabefeld
        inp_frame = QFrame()
        inp_frame.setObjectName("Card")
        inp_lay = QHBoxLayout(inp_frame)
        inp_lay.setContentsMargins(12, 8, 12, 8)
        inp_lay.setSpacing(8)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Fach, Thema oder Frage eingeben … (Enter zum Senden)")
        self._input.returnPressed.connect(self._send)
        inp_lay.addWidget(self._input, 1)
        send_btn = QPushButton("→")
        send_btn.setObjectName("PrimaryBtn")
        send_btn.setFixedSize(36, 36)
        send_btn.clicked.connect(self._send)
        inp_lay.addWidget(send_btn)
        lay.addWidget(inp_frame)

    def _welcome(self):
        """Zeigt eine kontextabhängige Begrüßung mit hilfreichen Starter-Chips."""
        try:
            s = self._engine._situation()
        except Exception:
            s = {"n_mods": 0, "open_tasks": 0, "streak": 0,
                 "most_urgent": None, "urgent_days": None,
                 "active_mods": [], "overdue": []}

        n_mods = s.get("n_mods", 0)
        mu = s.get("most_urgent")
        urgent_days = s.get("urgent_days")
        streak = s.get("streak", 0)

        # ── Nachricht ────────────────────────────────────────────────────────
        if n_mods == 0:
            html = (
                "<b>👋 Willkommen beim Studien-Coach!</b><br><br>"
                "Ich bin dein persönlicher Lernassistent — "
                "offline, kostenlos, immer verfügbar.<br><br>"
                "<b>Was ich für dich tun kann:</b><br>"
                "🎬 &nbsp;YouTube-Videos zu jedem Fach finden<br>"
                "📋 &nbsp;Lernpläne &amp; Crashpläne erstellen<br>"
                "🌐 &nbsp;Lernwebsites &amp; Wikipedia-Links öffnen<br>"
                "📅 &nbsp;Prüfungstermine eintragen &amp; tracken<br>"
                "⏱️ &nbsp;Timer starten &amp; App navigieren<br><br>"
                "<i>Leg zuerst deine Module an – dann helfe ich gezielt.</i>"
            )
            chips = [
                self._engine._nav(self._engine.PAGE_MODULE,    "📚 Module anlegen"),
                self._engine._nav(self._engine.PAGE_STUDIENPLAN, "📊 Studienplan ansehen"),
                self._engine._yt("Lerntechniken Studium Tipps Deutsch", "🎬 Lerntipps Videos"),
                self._engine._web("https://de.wikipedia.org/wiki/Lernstrategie",
                                  "📖 Wikipedia: Lernstrategien"),
            ]

        elif mu and urgent_days is not None and urgent_days <= 5:
            mod_name = mu.get("name", "Prüfung")
            html = (
                f"<b>👋 Hallo! Ich bin dein Studien-Coach.</b><br><br>"
                f"🚨 <b>Achtung:</b> <b>{mod_name}</b> steht in "
                f"<b>{urgent_days} Tag{'en' if urgent_days != 1 else ''}</b> an!<br><br>"
                f"Soll ich dir sofort einen Crashplan erstellen?"
            )
            chips = [
                "🚨 Crashplan erstellen",
                self._engine._nav(self._engine.PAGE_WISSEN,  "🧠 Schwache Themen"),
                self._engine._nav(self._engine.PAGE_TIMER,   "⏱ Lernsession starten"),
                self._engine._yt(f"{mod_name} Prüfungsvorbereitung kompakt",
                                 f"🎬 Videos: {mod_name[:20]}"),
            ]

        else:
            streak_note = (f" · 🔥 {streak} Tage Serie" if streak > 2 else "")
            task_note   = (f" · {s['open_tasks']} Aufgaben" if s.get("open_tasks") else "")
            html = (
                f"<b>👋 Hallo! Ich bin dein Studien-Coach.</b><br><br>"
                f"<b>{n_mods} Module aktiv</b>{task_note}{streak_note}<br><br>"
                "Schreib mir, was dich beschäftigt &mdash; oder klick einen Vorschlag unten.<br><br>"
                "<span style='color:#6B7280;font-size:12px;'>"
                "Tipps: <i>&bdquo;Analysis&ldquo;</i> &middot; <i>&bdquo;Prüfung am 15.04&ldquo;</i>"
                " &middot; <i>&bdquo;Wo anfangen?&ldquo;</i> &middot; <i>&bdquo;Videos zu SQL&ldquo;</i>"
                "</span>"
            )
            chips = []
            # Dringlichstes Modul als erster Chip
            if mu and urgent_days is not None and urgent_days <= 21:
                mod_name = mu.get("name", "Modul")
                chips.append(f"📋 Lernplan: {mod_name[:22]}")
            # Aktive Module als Video-Chips
            for m in s.get("active_mods", [])[:2]:
                chips.append(
                    self._engine._yt(
                        f"{m['name']} Studium Tutorial Deutsch",
                        f"🎬 {m['name'][:22]}"
                    )
                )
            chips.append("📊 Wie stehe ich?")
            chips.append(self._engine._nav(self._engine.PAGE_TIMER, "⏱ Timer starten"))

        self._add_bot_message(html, chips[:5])

    def _send(self):
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self._add_user_message(text)
        self._ctx["turn"] += 1
        # _ctx wird als Referenz übergeben; engine schreibt pending/etc. direkt rein
        msg, replies = self._engine.respond(text, ctx=self._ctx)
        # Kontext für nächste Runde aktualisieren (nur wenn kein pending-Flow läuft)
        if not self._ctx.get("pending"):
            subj = self._engine._detect_subject(text)
            if subj:
                self._ctx["last_subject"] = subj
            mod = self._engine._match_module(text)
            if mod and mod.get("code"):
                self._ctx["last_mod_code"] = mod["code"]
                self._ctx["last_subject"] = mod.get("name")
            self._ctx["last_intent"] = self._engine._intent(text)
        QTimer.singleShot(300, lambda: self._add_bot_message(msg, replies))

    def _add_user_message(self, text: str):
        bubble = QFrame()
        bubble.setStyleSheet(
            "background:#7C3AED;border-radius:14px 14px 4px 14px;padding:8px 14px;")
        bubble.setAttribute(Qt.WA_StyledBackground, True)
        bl = QHBoxLayout(bubble)
        bl.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color:#FFFFFF;font-size:13px;background:transparent;")
        bl.addWidget(lbl)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(bubble)
        container = QWidget()
        container.setLayout(row)
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, container)
        self._scroll_to_bottom()

    def _add_bot_message(self, html: str, quick_replies: list[str] = None):
        bubble = QFrame()
        bubble.setObjectName("Card")
        bl = QVBoxLayout(bubble)
        bl.setContentsMargins(12, 10, 12, 10)
        bl.setSpacing(8)
        lbl = QLabel(html)
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.RichText)
        lbl.setTextInteractionFlags(Qt.TextBrowserInteraction)
        lbl.linkActivated.connect(_open_url_safe)
        lbl.setStyleSheet("font-size:13px;line-height:1.6;")
        bl.addWidget(lbl)
        bubble.setMaximumWidth(480)

        row = QHBoxLayout()
        row.addWidget(bubble)
        row.addStretch()
        container = QWidget()
        container.setLayout(row)
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, container)

        # Quick-Reply-Buttons aktualisieren
        while self._replies_lay.count() > 1:
            item = self._replies_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if quick_replies:
            for action_str in quick_replies[:5]:
                label = self._parse_label(action_str)
                btn = QPushButton(label)
                btn.setFixedHeight(32)
                btn.setStyleSheet(
                    "QPushButton{"
                    "background:#F3F0FF;color:#6D28D9;"
                    "border:1.5px solid #C4B5FD;"
                    "border-radius:16px;"
                    "font-size:12px;font-weight:600;"
                    "padding:4px 12px;"
                    "}"
                    "QPushButton:hover{"
                    "background:#EDE9FE;border-color:#7C3AED;"
                    "}"
                    "QPushButton:pressed{background:#DDD6FE;}"
                )
                btn.clicked.connect(
                    lambda checked, a=action_str: self._execute_action(a))
                self._replies_lay.insertWidget(self._replies_lay.count() - 1, btn)

        self._scroll_to_bottom()

    @staticmethod
    def _parse_label(action_str: str) -> str:
        """Extrahiert den Anzeigetext aus einem Aktions-String."""
        parts = action_str.split("|")
        if len(parts) == 3 and parts[0] in ("NAV", "YT", "WEB"):
            return parts[2]
        return action_str  # Klartext

    def _execute_action(self, action_str: str):
        """Führt eine Quick-Reply-Aktion aus."""
        parts = action_str.split("|")
        kind = parts[0] if len(parts) >= 1 else ""

        if kind == "NAV" and len(parts) == 3:
            # Zur Seite navigieren und Chat schließen
            try:
                idx = int(parts[1])
            except ValueError:
                return
            label = parts[2]
            self._add_user_message(label)
            if self._switch_page:
                QTimer.singleShot(300, lambda: (self._switch_page(idx), self.accept()))
            return

        if kind == "YT" and len(parts) == 3:
            query = _urllib_parse.unquote(parts[1])
            label = parts[2]
            self._add_user_message(label)
            url = f"https://www.youtube.com/results?search_query={_urllib_parse.quote(query)}"
            # Link im Chat anzeigen — User entscheidet selbst ob er klickt
            confirm_msg = (
                f"🎬 <b>YouTube-Suche:</b> {query}<br><br>"
                f'<a href="{url}">▶ Auf YouTube öffnen</a><br><br>'
                f"<span style='font-size:11px;color:#6B7280;'>"
                f"Klick auf den Link — öffnet in deinem Browser.</span>"
            )
            # Kontext aktualisieren
            subj = self._engine._detect_subject(query)
            if subj:
                self._ctx["last_subject"] = subj
            self._ctx["last_intent"] = "youtube"
            self._ctx["turn"] += 1
            # Smarte Follow-ups basierend auf Kontext
            subject = self._ctx.get("last_subject")
            followups: list[str] = []
            if subject:
                resources = self._engine.RESOURCES.get(subject, [])
                if resources:
                    _lbl, _url = resources[0]
                    followups.append(self._engine._web(_url, _lbl[:35]))
            followups.append(self._engine._yt(query + " Zusammenfassung", "▶ Kompaktere Erklärung"))
            followups.append("🌐 Weitere Ressourcen")
            QTimer.singleShot(300, lambda: self._add_bot_message(confirm_msg, followups[:3]))
            return

        if kind == "WEB" and len(parts) >= 3:
            # URL kann Pipe-Zeichen enthalten → alles zwischen erstem und letztem "|" ist URL
            url = "|".join(parts[1:-1])
            label = parts[-1]
            self._add_user_message(label)
            # Anzeigenamen bereinigen
            display = label
            for pfx in ("🌐 ", "📐 ", "🔍 ", "🤖 ", "💻 ", "🗄 ", "📊 ", "🔢 ", "⚙ "):
                display = display.replace(pfx, "")
            display = display.strip()
            # Link im Chat anzeigen
            confirm_msg = (
                f"🌐 <b>{display}</b><br><br>"
                f'<a href="{url}">{url[:65]}{"…" if len(url) > 65 else ""}</a><br><br>'
                f"<span style='font-size:11px;color:#6B7280;'>"
                f"Klick auf den Link — öffnet in deinem Browser.</span>"
            )
            # Kontext & Follow-ups
            self._ctx["last_intent"] = "resource"
            self._ctx["turn"] += 1
            subject = self._ctx.get("last_subject")
            followups: list[str] = []
            if subject:
                followups.append(self._engine._yt(
                    f"{subject} Studium Erklärung", f"🎬 YouTube: {subject[:20]}"))
                resources = self._engine.RESOURCES.get(subject, [])
                if len(resources) > 1:
                    _lbl2, _url2 = resources[1]
                    followups.append(self._engine._web(_url2, _lbl2[:35]))
            followups.append("📋 Lernplan dazu erstellen")
            QTimer.singleShot(300, lambda: self._add_bot_message(confirm_msg, followups[:3]))
            return

        # Kein spezielles Format → als normaler Text senden
        self._add_user_message(action_str)
        self._ctx["turn"] += 1
        msg, replies = self._engine.respond(action_str, ctx=self._ctx)
        subj = self._engine._detect_subject(action_str)
        if subj:
            self._ctx["last_subject"] = subj
        mod = self._engine._match_module(action_str)
        if mod and mod.get("code"):
            self._ctx["last_mod_code"] = mod["code"]
            self._ctx["last_subject"] = mod.get("name")
        self._ctx["last_intent"] = self._engine._intent(action_str)
        QTimer.singleShot(300, lambda: self._add_bot_message(msg, replies))

    def _scroll_to_bottom(self):
        QTimer.singleShot(50, lambda: self._chat_sa.verticalScrollBar().setValue(
            self._chat_sa.verticalScrollBar().maximum()
        ))

    def _clear_chat(self):
        while self._chat_layout.count() > 1:
            item = self._chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._welcome()


