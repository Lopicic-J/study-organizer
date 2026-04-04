-- ─── Flashcard: Aufgabe-Verknüpfung + Multiple-Correct MC ──────────────────
-- task_id: optional link to a task (Aufgabe)
-- correct_answers: array of correct choices for MC cards (supports multiple correct)
-- card_type: type of card (basic, cloze, mc)
-- choices: array of answer options for MC cards
-- tags: user-defined tags
-- streak, total_reviews, correct_count, last_quality: review tracking

-- Add task_id column if not exists
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'flashcards' AND column_name = 'task_id'
  ) THEN
    ALTER TABLE flashcards ADD COLUMN task_id UUID REFERENCES tasks(id) ON DELETE SET NULL;
    CREATE INDEX idx_flashcards_task ON flashcards(task_id);
  END IF;
END $$;

-- Add correct_answers column (array of correct choices for MC)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'flashcards' AND column_name = 'correct_answers'
  ) THEN
    ALTER TABLE flashcards ADD COLUMN correct_answers TEXT[];
  END IF;
END $$;

-- Ensure card_type exists
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'flashcards' AND column_name = 'card_type'
  ) THEN
    ALTER TABLE flashcards ADD COLUMN card_type TEXT NOT NULL DEFAULT 'basic'
      CHECK (card_type IN ('basic', 'cloze', 'mc'));
  END IF;
END $$;

-- Ensure choices exists
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'flashcards' AND column_name = 'choices'
  ) THEN
    ALTER TABLE flashcards ADD COLUMN choices TEXT[];
  END IF;
END $$;

-- Ensure tags exists
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'flashcards' AND column_name = 'tags'
  ) THEN
    ALTER TABLE flashcards ADD COLUMN tags TEXT[] DEFAULT '{}';
  END IF;
END $$;

-- Ensure streak, total_reviews, correct_count, last_quality exist
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'flashcards' AND column_name = 'streak'
  ) THEN
    ALTER TABLE flashcards ADD COLUMN streak INTEGER NOT NULL DEFAULT 0;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'flashcards' AND column_name = 'total_reviews'
  ) THEN
    ALTER TABLE flashcards ADD COLUMN total_reviews INTEGER NOT NULL DEFAULT 0;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'flashcards' AND column_name = 'correct_count'
  ) THEN
    ALTER TABLE flashcards ADD COLUMN correct_count INTEGER NOT NULL DEFAULT 0;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'flashcards' AND column_name = 'last_quality'
  ) THEN
    ALTER TABLE flashcards ADD COLUMN last_quality INTEGER;
  END IF;
END $$;
