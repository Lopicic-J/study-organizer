-- ── Task Attachments: links & file uploads per task ─────────────────
CREATE TABLE IF NOT EXISTS task_attachments (
  id          uuid primary key default uuid_generate_v4(),
  user_id     uuid references auth.users(id) on delete cascade not null,
  task_id     uuid references tasks(id) on delete cascade not null,
  kind        text not null default 'link',        -- 'link' | 'file'
  label       text not null default '',
  url         text not null default '',             -- URL or storage path
  file_type   text default '',                     -- pdf, docx, xlsx, etc.
  file_size   bigint default 0,                    -- bytes
  storage_path text default null,                  -- Supabase storage path (for files)
  created_at  timestamptz default now()
);

-- RLS policies
ALTER TABLE task_attachments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own task attachments"
  ON task_attachments FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own task attachments"
  ON task_attachments FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own task attachments"
  ON task_attachments FOR DELETE
  USING (auth.uid() = user_id);

-- Index for fast lookup by task
CREATE INDEX idx_task_attachments_task ON task_attachments(task_id);

-- ── Storage bucket for task file uploads ────────────────────────────
INSERT INTO storage.buckets (id, name, public)
VALUES ('task-files', 'task-files', false)
ON CONFLICT (id) DO NOTHING;

-- Storage policies: only owner can upload/read/delete their files
CREATE POLICY "Users can upload task files"
  ON storage.objects FOR INSERT
  WITH CHECK (
    bucket_id = 'task-files'
    AND auth.uid()::text = (storage.foldername(name))[1]
  );

CREATE POLICY "Users can view own task files"
  ON storage.objects FOR SELECT
  USING (
    bucket_id = 'task-files'
    AND auth.uid()::text = (storage.foldername(name))[1]
  );

CREATE POLICY "Users can delete own task files"
  ON storage.objects FOR DELETE
  USING (
    bucket_id = 'task-files'
    AND auth.uid()::text = (storage.foldername(name))[1]
  );
