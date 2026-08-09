-- 011_user_privilege.sql

ALTER TABLE users
    ADD COLUMN is_privileged BOOLEAN NOT NULL DEFAULT FALSE;