-- ─── KI-Usage Tracking (Server-seitig) ────────────────────────────────────
-- Trackt monatliche KI-Requests pro User.
--
-- Modell v3:
-- Pro Basic (4.90/Mo):       10 KI/Monat Pool
-- Pro Full (9.90/Mo):       100 KI/Monat Pool
-- Lifetime Basic (89.90):     0 KI/Monat (nur Add-on)
-- Lifetime Full (129.90):    20 KI/Monat Pool
-- Add-on (+200 für 6.90):   nur aktueller Monat, verfällt!

-- plan_tier auf Profil: "basic" oder "full"
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'profiles' AND column_name = 'plan_tier'
  ) THEN
    ALTER TABLE profiles ADD COLUMN plan_tier TEXT DEFAULT NULL;
  END IF;
END $$;

-- AI credits auf Profil (legacy / fallback)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'profiles' AND column_name = 'ai_credits'
  ) THEN
    ALTER TABLE profiles ADD COLUMN ai_credits INTEGER NOT NULL DEFAULT 0;
  END IF;
END $$;

-- Monats-Zähler: KI-Requests pro User pro Monat + Add-on Credits
CREATE TABLE IF NOT EXISTS ai_usage (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  month           TEXT NOT NULL,       -- Format: "2026-04"
  used            INTEGER NOT NULL DEFAULT 0,
  addon_credits   INTEGER NOT NULL DEFAULT 0,  -- Add-on credits (verfällt am Monatsende)
  created_at      TIMESTAMPTZ DEFAULT now() NOT NULL,
  updated_at      TIMESTAMPTZ DEFAULT now() NOT NULL,
  UNIQUE(user_id, month)
);

-- Add addon_credits column if table already exists
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'ai_usage' AND column_name = 'addon_credits'
  ) THEN
    ALTER TABLE ai_usage ADD COLUMN addon_credits INTEGER NOT NULL DEFAULT 0;
  END IF;
END $$;

-- RLS
ALTER TABLE ai_usage ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Users can read own AI usage') THEN
    CREATE POLICY "Users can read own AI usage"
      ON ai_usage FOR SELECT
      USING (auth.uid() = user_id);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Users can update own AI usage') THEN
    CREATE POLICY "Users can update own AI usage"
      ON ai_usage FOR ALL
      USING (auth.uid() = user_id)
      WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

-- Index
CREATE INDEX IF NOT EXISTS idx_ai_usage_user_month ON ai_usage(user_id, month);

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_ai_usage_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS ai_usage_updated_at ON ai_usage;
CREATE TRIGGER ai_usage_updated_at
  BEFORE UPDATE ON ai_usage
  FOR EACH ROW
  EXECUTE FUNCTION update_ai_usage_updated_at();

-- ─── Server-side function to check & increment AI usage atomically ───
-- Supports: monthly pool + addon_credits + weighted requests (p_weight)
CREATE OR REPLACE FUNCTION check_and_increment_ai(
  p_user_id UUID,
  p_month TEXT,
  p_monthly_pool INTEGER,   -- determined by plan tier in application code
  p_weight INTEGER DEFAULT 1 -- credit cost of this request (1=short, 2=explain, 3=summary, 5=pdf)
) RETURNS JSON AS $$
DECLARE
  v_usage RECORD;
  v_allowed BOOLEAN := FALSE;
  v_used INTEGER := 0;
  v_addon INTEGER := 0;
  v_total_available INTEGER := 0;
  v_remaining INTEGER := 0;
  v_source TEXT := 'none';
  v_cost INTEGER := GREATEST(1, p_weight);
BEGIN
  -- Get or create monthly usage record
  INSERT INTO ai_usage (user_id, month, used, addon_credits)
  VALUES (p_user_id, p_month, 0, 0)
  ON CONFLICT (user_id, month) DO NOTHING;

  SELECT used, addon_credits INTO v_usage
  FROM ai_usage WHERE user_id = p_user_id AND month = p_month;

  v_used := COALESCE(v_usage.used, 0);
  v_addon := COALESCE(v_usage.addon_credits, 0);
  v_total_available := p_monthly_pool + v_addon;

  -- Check if enough credits for this weighted request
  IF (v_used + v_cost) <= v_total_available THEN
    v_allowed := TRUE;
    IF v_used < p_monthly_pool THEN
      v_source := 'pool';
    ELSE
      v_source := 'addon';
    END IF;
    v_remaining := v_total_available - v_used - v_cost;
  ELSE
    v_allowed := FALSE;
    v_remaining := GREATEST(0, v_total_available - v_used);
  END IF;

  -- Increment usage by weight if allowed
  IF v_allowed THEN
    UPDATE ai_usage SET used = used + v_cost WHERE user_id = p_user_id AND month = p_month;
  END IF;

  RETURN json_build_object(
    'allowed', v_allowed,
    'used', v_used + (CASE WHEN v_allowed THEN v_cost ELSE 0 END),
    'remaining', GREATEST(0, v_remaining),
    'source', v_source,
    'monthly_pool', p_monthly_pool,
    'addon_credits', v_addon,
    'cost', v_cost
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ─── Add addon credits to a user for a specific month ───
-- Called by webhook after add-on purchase
CREATE OR REPLACE FUNCTION add_addon_credits(
  p_user_id UUID,
  p_month TEXT,
  p_credits INTEGER
) RETURNS VOID AS $$
BEGIN
  INSERT INTO ai_usage (user_id, month, used, addon_credits)
  VALUES (p_user_id, p_month, 0, p_credits)
  ON CONFLICT (user_id, month)
  DO UPDATE SET addon_credits = ai_usage.addon_credits + p_credits;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Legacy function (kept for backward compat, now uses monthly addon)
CREATE OR REPLACE FUNCTION increment_ai_credits(
  p_user_id UUID,
  p_credits INTEGER
) RETURNS VOID AS $$
BEGIN
  UPDATE profiles SET ai_credits = ai_credits + p_credits WHERE id = p_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
