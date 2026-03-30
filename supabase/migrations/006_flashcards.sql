-- ─── Karteikarten (Flashcards) ───────────────────────────────────────────────
-- Studenten können pro Modul, Prüfung oder Lernziel Karteikarten erstellen.
-- Zwei Quellen: manuell (user) und KI-generiert (ai).
-- AI-generierte Karten werden separat gespeichert, damit sie leicht gelöscht werden können.

CREATE TABLE IF NOT EXISTS flashcards (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id       UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

  -- Zuordnung (mindestens eins sollte gesetzt sein)
  module_id     UUID REFERENCES modules(id) ON DELETE SET NULL,
  exam_id       UUID REFERENCES exams(id) ON DELETE SET NULL,
  knowledge_id  UUID REFERENCES knowledge_items(id) ON DELETE SET NULL,

  -- Deck-Gruppierung (z.B. "Mathematik 1 - Kapitel 3" oder automatisch vom Dokument)
  deck_name     TEXT NOT NULL DEFAULT 'Standard',

  -- Karteikarten-Inhalt
  front         TEXT NOT NULL,          -- Frage / Vorderseite
  back          TEXT NOT NULL,          -- Antwort / Rückseite

  -- Quelle: 'user' = manuell erstellt, 'ai' = KI-generiert aus Dokument
  source        TEXT NOT NULL DEFAULT 'user' CHECK (source IN ('user', 'ai')),

  -- Für AI-generierte: Referenz auf das Quelldokument
  source_document TEXT,                 -- Dateiname des hochgeladenen Dokuments

  -- Spaced Repetition Felder
  ease_factor   REAL NOT NULL DEFAULT 2.5,   -- SM-2 Algorithmus
  interval_days INTEGER NOT NULL DEFAULT 0,  -- Tage bis nächste Wiederholung
  repetitions   INTEGER NOT NULL DEFAULT 0,  -- Anzahl erfolgreicher Wiederholungen
  next_review   TIMESTAMPTZ,                 -- Nächster Wiederholungszeitpunkt
  last_reviewed TIMESTAMPTZ,                 -- Letzter Wiederholungszeitpunkt

  -- Meta
  created_at    TIMESTAMPTZ DEFAULT now() NOT NULL,
  updated_at    TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- RLS
ALTER TABLE flashcards ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can CRUD own flashcards"
  ON flashcards FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- Indizes
CREATE INDEX idx_flashcards_user    ON flashcards(user_id);
CREATE INDEX idx_flashcards_module  ON flashcards(module_id);
CREATE INDEX idx_flashcards_deck    ON flashcards(user_id, deck_name);
CREATE INDEX idx_flashcards_review  ON flashcards(user_id, next_review);
CREATE INDEX idx_flashcards_source  ON flashcards(user_id, source);

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_flashcards_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER flashcards_updated_at
  BEFORE UPDATE ON flashcards
  FOR EACH ROW EXECUTE FUNCTION update_flashcards_updated_at();
