create table users(chat_id bigint primary key, name text, interests text[] default '{}', active boolean default true, created timestamptz default now());
create table items(id text primary key, name text, inst text, type text, deadline date, eligibility text, details text, fee text, prize text, past_winners text, link text, brochure text, tags text[] default '{}', trust int default 50, trust_note text, created timestamptz default now());
create table user_items(chat_id bigint references users on delete cascade, item_id text references items on delete cascade, status text default 'new', rem int[] default '{}', primary key(chat_id,item_id));
create table meta(key text primary key, value text);
create table inbox(id bigint generated always as identity primary key, chat_id bigint, payload jsonb, done boolean default false, created timestamptz default now());
-- RLS on, no policies: the public/anon key can read nothing. Only the service key (kept in secrets) can access.
alter table users enable row level security; alter table items enable row level security;
alter table user_items enable row level security; alter table meta enable row level security; alter table inbox enable row level security;
create table institutes(id bigint generated always as identity primary key, name text, website text, pages text[] default '{}', contact text, info text, submitted_by bigint, status text default 'pending', created timestamptz default now());
alter table institutes enable row level security;
