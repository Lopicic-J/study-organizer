"""GUI Constants — colors, labels, and quotes."""

MODULE_COLORS = [
    "#4A86E8", "#E84A5F", "#2CB67D", "#FF8C42", "#9B59B6",
    "#00B4D8", "#F72585", "#3A86FF", "#F4A261", "#2EC4B6",
]

KNOWLEDGE_COLORS = {0: "#9E9E9E", 1: "#F44336", 2: "#FF9800", 3: "#8BC34A", 4: "#4CAF50"}

KNOWLEDGE_LABELS = {0: "Nicht begonnen", 1: "Grundlagen", 2: "Vertraut", 3: "Gut", 4: "Experte"}

PRIORITY_COLORS = {"Critical": "#F44336", "High": "#FF9800", "Medium": "#7C3AED", "Low": "#9E9E9E"}

STATUS_LABELS = {"planned": "Geplant", "active": "Aktiv", "completed": "Abgeschlossen", "paused": "Pausiert"}

# Motivational Quotes
# Shown daily on the Dashboard — one per day, deterministic (date-based index).
STUDENT_QUOTES: list[tuple[str, str]] = [
    ("Du musst nicht perfekt sein. Du musst nur anfangen.", ""),
    ("Jeder Experte war einmal ein Anfänger.", "Helen Hayes"),
    ("Investiere in dein Wissen — es trägt Zinsen dein Leben lang.", "Benjamin Franklin"),
    ("Der Anfang ist die Hälfte des Ganzen.", "Aristoteles"),
    ("Bildung ist das mächtigste Werkzeug, das du nutzen kannst, um die Welt zu verändern.", "Nelson Mandela"),
    ("Du schaffst das. Schritt für Schritt, Tag für Tag.", ""),
    ("Misserfolg ist nur eine Umleitung, kein Ende.", ""),
    ("Konzentrier dich auf den Fortschritt, nicht auf Perfektion.", ""),
    ("Die meisten Menschen scheitern nicht, weil sie versagen — sondern weil sie aufhören.", ""),
    ("Wer aufhört zu lernen, hört auf zu wachsen.", ""),
    ("Kleine Fortschritte jeden Tag summieren sich zu großen Ergebnissen.", ""),
    ("Dein zukünftiges Ich dankt dir für das, was du heute tust.", ""),
    ("Es wird schwer — und das ist genau der Punkt. Das Schwere ist es, was es wertvoll macht.", ""),
    ("Nicht die Zeit fehlt, sondern die Entscheidung, sie zu nutzen.", ""),
    ("Lerne nicht für die Note. Lerne für das Verständnis.", ""),
    ("Jeder Schritt vorwärts — egal wie klein — ist ein Sieg.", ""),
    ("Du bist fähiger, als du glaubst.", "A. A. Milne"),
    ("Die Hürden, die du überwindest, formen dich mehr als die Wege ohne Hindernisse.", ""),
    ("Motiviere dich nicht durch Angst vor Misserfolg, sondern durch Freude am Wachsen.", ""),
    ("Fang an. Das ist alles, was du jetzt tun musst.", ""),
    ("Wissen ist der einzige Besitz, den dir niemand nehmen kann.", ""),
    ("Heute ist der beste Tag, um etwas Neues zu lernen.", ""),
    ("Eine Stunde konzentriertes Lernen schlägt drei Stunden passives Lesen.", ""),
    ("Glaub nicht an die Grenzen, die andere für dich gesetzt haben.", ""),
    ("Dein Gehirn ist flexibler als du denkst — nutze es.", ""),
    ("Du musst nicht schnell lernen. Du musst nur nicht aufhören.", ""),
    ("Studieren ist keine Last — es ist ein Privileg.", ""),
    ("Die Energie, die du in dein Wissen investierst, kehrt tausendfach zurück.", ""),
    ("Zwischen heute und deinem Ziel liegt nur Ausdauer.", ""),
    ("Rückschläge sind keine Niederlagen. Sie sind Hinweise.", ""),
]
