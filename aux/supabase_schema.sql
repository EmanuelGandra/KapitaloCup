create extension if not exists pgcrypto;

create table if not exists profiles (
    id uuid primary key default gen_random_uuid(),
    username text unique not null,
    password_hash text not null,
    created_at timestamptz default now()
);

create table if not exists matches (
    match_id text primary key,
    stage text not null,
    group_name text,
    match_no int,
    kickoff_at timestamptz,
    venue text,
    home_team text not null,
    away_team text not null,
    is_open boolean default true,
    created_at timestamptz default now()
);

create table if not exists predictions (
    user_id uuid references profiles(id) on delete cascade,
    match_id text references matches(match_id) on delete cascade,
    home_goals int not null check (home_goals >= 0),
    away_goals int not null check (away_goals >= 0),
    advancing_team text,
    updated_at timestamptz default now(),
    primary key (user_id, match_id)
);

create table if not exists actual_results (
    match_id text primary key references matches(match_id) on delete cascade,
    home_goals int not null check (home_goals >= 0),
    away_goals int not null check (away_goals >= 0),
    advancing_team text,
    updated_at timestamptz default now()
);

create table if not exists phase_predictions (
    user_id uuid references profiles(id) on delete cascade,
    phase text not null,
    team text not null,
    primary key (user_id, phase, team)
);

create table if not exists phase_actuals (
    phase text not null,
    team text not null,
    primary key (phase, team)
);

create table if not exists bonus_predictions (
    user_id uuid primary key references profiles(id) on delete cascade,
    champion text,
    top_scorer text,
    updated_at timestamptz default now()
);

create table if not exists bonus_actuals (
    id int primary key default 1 check (id = 1),
    champion text,
    top_scorer text,
    updated_at timestamptz default now()
);

-- Para app interno simples, você pode deixar RLS desabilitado.
-- Para app público, implemente Supabase Auth + RLS antes de publicar.
