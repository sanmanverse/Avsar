-- Only if you already ran the v3 schema:
create table if not exists institutes(id bigint generated always as identity primary key, name text, website text, pages text[] default '{}', contact text, info text, submitted_by bigint, status text default 'pending', created timestamptz default now());
alter table institutes enable row level security;
