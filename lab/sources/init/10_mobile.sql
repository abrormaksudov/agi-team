-- mobile: in-house mobile banking backend; one schema per microservice. Runs only in database "mobile".
SELECT current_database() <> 'mobile' AS skip \gset
\if :skip
\quit
\endif

CREATE SCHEMA users;
CREATE SCHEMA devices;
CREATE SCHEMA kyc;

CREATE TABLE users.app_user (
    user_id uuid PRIMARY KEY,
    phone_number text NOT NULL,
    email text,
    first_name text NOT NULL,
    last_name text NOT NULL,
    middle_name text,
    date_of_birth date NOT NULL,
    gender char(1) NOT NULL,
    pinfl char(14) NOT NULL,
    lang text NOT NULL,
    account_status text NOT NULL,
    verification_level text NOT NULL,
    core_customer_id bigint,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);
COMMENT ON TABLE users.app_user IS 'Mobile app account. One person may own more than one (same PINFL, different phone).';
COMMENT ON COLUMN users.app_user.phone_number IS 'Login phone number, +998 format';
COMMENT ON COLUMN users.app_user.pinfl IS 'Personal identification number of an individual (14 digits)';
COMMENT ON COLUMN users.app_user.verification_level IS 'none until onboarding KYC succeeds, then full';
COMMENT ON COLUMN users.app_user.core_customer_id IS 'iABS customer id, set when onboarding KYC succeeds';

CREATE TABLE users.login_event (
    event_id bigint PRIMARY KEY,
    user_id uuid NOT NULL,
    device_id uuid,
    session_id uuid NOT NULL,
    event_type text NOT NULL,
    auth_result text NOT NULL,
    ip_address inet,
    app_version text NOT NULL,
    occurred_at timestamptz NOT NULL
);
COMMENT ON TABLE users.login_event IS 'Authentication events: register, login, logout';

CREATE TABLE devices.device (
    device_id uuid PRIMARY KEY,
    device_fingerprint text NOT NULL,
    platform text NOT NULL,
    device_model text NOT NULL,
    os_version text NOT NULL,
    app_version text NOT NULL,
    first_seen_at timestamptz NOT NULL
);
COMMENT ON TABLE devices.device IS 'Device registry: one row per physical device seen by the app';

CREATE TABLE devices.user_device (
    user_device_id bigint PRIMARY KEY,
    user_id uuid NOT NULL,
    device_id uuid NOT NULL,
    is_trusted boolean NOT NULL,
    is_blocked boolean NOT NULL,
    is_rooted boolean NOT NULL,
    malware_detected boolean NOT NULL,
    malware_scan_at timestamptz,
    first_linked_at timestamptz NOT NULL
);
COMMENT ON TABLE devices.user_device IS 'User × device link with device security signals';

CREATE TABLE kyc.kyc_attempt (
    attempt_id uuid PRIMARY KEY,
    user_id uuid NOT NULL,
    purpose text NOT NULL,
    mode text NOT NULL,
    status text NOT NULL,
    last_step text NOT NULL,
    fail_reason text,
    face_match_score numeric(4, 3),
    face_photo_ref text,
    aml_result text,
    started_at timestamptz NOT NULL,
    completed_at timestamptz,
    updated_at timestamptz NOT NULL
);
COMMENT ON TABLE kyc.kyc_attempt IS 'Identity verification attempt: onboarding, new device login, password reset';
COMMENT ON COLUMN kyc.kyc_attempt.status IS 'HOLD (manual review), FAIL (retry), REFUSE (rejected), SUCCESS';
COMMENT ON COLUMN kyc.kyc_attempt.face_photo_ref IS 'Storage reference of the biometric selfie';
