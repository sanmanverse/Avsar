-- Only if you already ran the v2 schema:
alter table items add column if not exists trust int default 50;
alter table items add column if not exists trust_note text;
create table if not exists inbox(id bigint generated always as identity primary key, chat_id bigint, payload jsonb, done boolean default false, created timestamptz default now());
alter table inbox enable row level security;
