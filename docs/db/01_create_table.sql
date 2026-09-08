#이전 차수 테이블 정리
drop trigger if exists on_auth_user_created on auth.users;

create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();

drop table if exists messages;
drop table if exists conversations;
drop table if exists users;

select table_name
from information_schema.tables
where table_schema = 'public'
  and table_name in ('users', 'conversations', 'messages');

del app\routers\users.py

select tablename, policyname, cmd
from pg_policies
where schemaname = 'public'
order by tablename, policyname;

# 새테이블 생성
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.profiles (id, username)
    values (new.id, split_part(new.email, '@', 1));
    return new;
end;
$$;

# 회원가입시 프로필 자동생성 트리거
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.profiles (id, username)
    values (new.id, split_part(new.email, '@', 1));
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;

create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();

#RLS 활성화와 정책 작성 
alter table profiles enable row level security;
alter table conversations enable row level security;
alter table messages enable row level security;

drop policy if exists "select own profile" on profiles;
drop policy if exists "update own profile" on profiles;
drop policy if exists "select own conversations" on conversations;
drop policy if exists "insert own conversations" on conversations;
drop policy if exists "update own conversations" on conversations;
drop policy if exists "delete own conversations" on conversations;
drop policy if exists "select own messages" on messages;
drop policy if exists "insert own messages" on messages;

create policy "select own profile" on profiles
    for select using (auth.uid() = id);

create policy "update own profile" on profiles
    for update using (auth.uid() = id);

create policy "select own conversations" on conversations
    for select using (auth.uid() = user_id);

create policy "insert own conversations" on conversations
    for insert with check (auth.uid() = user_id);

create policy "update own conversations" on conversations
    for update using (auth.uid() = user_id);

create policy "delete own conversations" on conversations
    for delete using (auth.uid() = user_id);

create policy "select own messages" on messages
    for select using (
        exists (
            select 1 from conversations c
            where c.id = messages.conversation_id
              and c.user_id = auth.uid()
        )
    );

create policy "insert own messages" on messages
    for insert with check (
        exists (
            select 1 from conversations c
            where c.id = messages.conversation_id
              and c.user_id = auth.uid()
        )
    );




