# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.8.x   | :white_check_mark: |
| < 0.8   | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to: **christopher.abanilla@gmx.de**
(dedicated `security@` alias TBD — replace once one exists).

We will acknowledge receipt of your vulnerability report within 48 hours and send you regular updates about our progress.

**What to include:**
- Description of the vulnerability
- Steps to reproduce the issue
- Possible impact
- Suggested fix (if any)

**What to expect:**
1. Initial response within 48 hours
2. Assessment within 5 business days
3. Fix timeline and disclosure coordination
4. Credit in security advisory (if desired)

---

# Security Architecture

> This section describes what the code in this repository actually does,
> verified against the source — not aspirational best practice. Items that
> are recommended but **not yet implemented** are explicitly marked as such
> rather than presented as fact.

## Authentication & Authorization

### JWT Token Security

openDox uses JWT tokens (`backend/components/security/hashing.py`):

- **Access Tokens**: 30-minute expiration (`ACCESS_TOKEN_EXPIRE_MINUTES`)
- **Refresh Tokens**: 7-day expiration (`REFRESH_TOKEN_EXPIRE_DAYS`)
- **Algorithm**: HS256 (HMAC with SHA-256)
- **Storage**: Tokens are stored in `localStorage` (browser)
- **Signing key**: `SECRET_KEY` has no insecure hardcoded fallback — if
  unset, a random key is generated per process start and a critical
  warning is logged (this invalidates all existing sessions on every
  restart until a stable `SECRET_KEY` is configured)

There is **no separate CSRF token mechanism** for the API, and none is
needed: all state-changing endpoints require a Bearer `Authorization`
header, which (unlike cookies) browsers never attach automatically to
cross-site requests — the classic CSRF attack vector doesn't apply here.
The one cookie in the system is a short-lived, `itsdangerous`-signed OIDC
`state` value, used only to prevent CSRF on the OIDC login redirect itself
(`oidc_routes.py`).

**Reverse-proxy header trust**: `CORS_ALLOWED_ORIGINS` (comma-separated)
replaces a previously hardcoded `allow_origins=["*"]`; unset falls back to
`*` with a logged warning. `TRUSTED_PROXY_IPS` controls which peers may set
`X-Forwarded-Proto`/`X-Forwarded-Host` (used to build the OIDC redirect
URI) — unset auto-detects loopback + the container's Docker gateway IP.
See `backend/run.py` (`mark_trusted_proxy` middleware) and
`backend/views/auth_api/oidc_routes.py` (`_build_redirect_uri`).

### LDAP Integration

When using LDAP/Active Directory (`backend/components/services/ldap.py`):

- Passwords are **never stored** in the database for LDAP users — only
  username and metadata are synced locally
- The LDAP search filter escapes the submitted username
  (`ldap3.utils.conv.escape_filter_chars`) before building the query, and
  empty passwords are rejected before any bind attempt (an empty-password
  SIMPLE bind is an RFC 4513 "unauthenticated bind", which some LDAP
  servers treat as a successful anonymous bind rather than a credential
  check)
- Group-based access control: `allowed_groups` (comma-separated group
  names) gates who may log in at all; `admin_groups`/`moderator_groups`
  map LDAP group membership (via the user's `memberOf` attribute) to
  roles, re-synced on every login — same admin-takes-precedence logic as
  the OIDC group mapping
- The optional LDAPS CA certificate is uploaded through the admin UI and
  stored in the database (`LdapSettingsModel.cert_data`), never written to
  disk
- `LdapSettingsModel.bind_user_password` and `OidcSettingsModel.client_secret`
  are Fernet-encrypted at rest (`EncryptedString` column type, same
  mechanism as patient data — see the encryption table below)
- SSL/TLS is recommended for LDAP connections (`ldaps://`) — not enforced
  by the application
- Bind credentials should use a service account with minimal privileges

**No self-registration**: there is no public sign-up endpoint. Accounts are
created by an admin (`POST /api/v1/auth/users`) or auto-provisioned on the
first successful LDAP/OIDC login.

**Not implemented**: no MFA/2FA of any kind (local, LDAP, or OIDC-side) is
implemented or enforced by this application. If your LDAP/OIDC provider
enforces MFA itself, that protects the directory login, but openDox has no
knowledge of it and adds nothing on top.

## Data Encryption

### Field-Level Encryption

Sensitive patient data is encrypted at the field level using **Fernet
symmetric encryption** (`backend/components/security/field_encryption.py`,
`ENCRYPTION_KEY` env var):

| Field / Location | Encrypted | Mechanism |
|-------|-----------|-----------|
| `Record.content` | ✅ Yes | Fernet, `EncryptedString` column type |
| `Record.summarize` | ✅ Yes | Fernet, `EncryptedString` column type |
| `Record.pii_mapping` | ✅ Yes | Fernet, `EncryptedString` column type |
| Persisted audio (S3-compatible object storage, optional feature) | ✅ Yes | Fernet, encrypted client-side with `encrypt_bytes()` before upload — the storage provider never sees plaintext |
| `Record.title` | ✅ Yes | Fernet, `EncryptedString` column type |
| `User.personal_glossary` | ✅ Yes | Fernet, `EncryptedString` column type |
| `User.name` | ❌ No | Plaintext (username, not patient data) |
| `User.hashed_password` | N/A | bcrypt (one-way hash, not Fernet) |
| `LdapSettingsModel.bind_user_password` | ✅ Yes | Fernet, `EncryptedString` column type |
| `OidcSettingsModel.client_secret` | ✅ Yes | Fernet, `EncryptedString` column type |
| `LlmSettingsModel.llm_api_key`, `sanitizer_api_key`; `WhisperSettingsModel.live_api_key`, `final_api_key`; `Categories.llm_api_key` | ❌ No | Plaintext in the database. `GET /api/v1/settings/llm-settings/`, `ldap-settings/` and `oidc-settings/` are admin-only, and `whisper-settings/` returns its keys to admins only (since the Unreleased security fix, see `CHANGELOG.md`) |

If `ENCRYPTION_KEY` is unset, Fernet encryption is silently disabled for
all rows marked ✅ above (a warning is logged at startup) — the
guarantees in this table only hold with a configured key.

**Why field-level encryption?**
- Searchable metadata remains accessible (title, timestamps)
- Patient content is protected even if the database is compromised
- Supports the technical-measures side of Art. 32 GDPR — see
  [`docs/data-mapping.md`](docs/data-mapping.md) for the full data-flow picture
  and known gaps (including the plaintext API keys above)

### Password Hashing

User passwords are hashed using **bcrypt** with:
- **Salt**: Automatically generated per password
- **Work Factor**: passlib's bcrypt default (12 rounds; not configurable in this app)
- **Algorithm**: Blowfish-based adaptive hashing

```
# Example bcrypt HASH (not a Fernet key — see Key Management below for that)
$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyNiAYMyzJ/IiO
#    └┘ └┘  └──────────────────────────────────────────────────────────┘
#    │  │                      Hash + Salt
#    │  └── Cost factor (2^12 = 4096 rounds)
#    └── bcrypt version
```

## Key Management

### Encryption Key Generation

```bash
# Generate a Fernet KEY (not a token — see the warning below)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# A real Fernet key is urlsafe-base64 of exactly 32 random bytes: 44
# characters, always ending in "=". It does NOT start with "gAAAAA" — that
# prefix belongs to a Fernet TOKEN (a piece of ciphertext produced BY a
# key), not the key itself. Example of what a real key looks like:
#   r50b-iOmhw_OKEOMfWf4g7GzqqC8moG49r84BKFRmUg=
```

### Secure Key Storage

#### Option 1: Environment Variables (Development)

```bash
# .env file (NEVER commit this file!)
ENCRYPTION_KEY=<output of the command above>
SECRET_KEY=<a long random string, e.g. `openssl rand -hex 32`>
```

#### Option 2: Docker Swarm Secrets (Production — what this repo actually ships)

`docker-swarm.yml` (paired with `docker-compose.yml`'s local/dev setup)
sources `SECRET_KEY`, `ENCRYPTION_KEY`, `SQL_PASS`, and the S3/Garage
credentials from Swarm-native secrets, via the app's existing `{VAR}_FILE`
convention (`backend/components/modules/env.py:env_or_file()`):

```bash
docker swarm init                        # once per manager node
./create_docker_secrets.sh                # once — generates + creates every secret
export OPENDOX_VERSION=$(python3 scripts/bump_version.py --current)
docker stack deploy -c docker-swarm.yml opendox
```

`create_docker_secrets.sh` prints freshly generated values exactly once
(Docker secrets can never be read back afterward — `docker secret inspect`
never reveals the value) and skips any secret that already exists, so it's
safe to re-run.

If you're not using Swarm, plain `docker compose` also supports
file-backed secrets (`secrets: { name: { file: ./secrets/... } }`) using
the same `{VAR}_FILE` mechanism — `docker-swarm.yml`'s comments are a
useful reference even outside Swarm.

### Key Rotation

**When to rotate keys:**
- Suspected compromise
- Employee departure
- Annual security review
- After security incident

**Rotation process (automatic re-encryption, manual secret handling):**

1. Generate a new key:
```bash
NEW_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
```

2. **Plain env var deployments:** set both vars for the next restart (the
   old key is needed once, to decrypt existing data before re-encrypting
   it under the new key):
```bash
ENCRYPTION_KEY_PREVIOUS=<the old key>
ENCRYPTION_KEY=$NEW_KEY
```
   **Docker Swarm:** Swarm secrets are immutable — you can't edit
   `opendox_encryption_key` in place. Create the previous-key secret, point
   `docker-swarm.yml`'s `opendox_encryption_key` source at a freshly
   created secret holding `$NEW_KEY`, and deploy with the rotation overlay:
```bash
printf '%s' '<the old key>' | docker secret create opendox_encryption_key_previous -
docker stack deploy -c docker-swarm.yml -c docker-swarm.rotation.yml opendox
```
   See the header comment in `docker-swarm.rotation.yml` for the full
   step-by-step, including cleanup after the rotation completes.

3. Restart/redeploy the container. On startup the app detects the key
   change (via a fingerprint stored in the `EncryptionKeyState` table),
   re-encrypts every encrypted column in place (`Record.title`/`content`/
   `summarize`/`pii_mapping`, `User.personal_glossary`, the LDAP bind password
   and the OIDC client secret), and logs `Encryption key rotation complete (N rows
   re-encrypted)`. The process is idempotent and safe to interrupt — an
   incomplete run resumes on the next restart with the same key values.
   **Note:** the persisted-audio-in-S3 feature (`audio_storage.py`) is
   encrypted with the same `ENCRYPTION_KEY` but is **not** covered by this
   automatic re-encryption pass — it's encrypted/decrypted on
   upload/download, not re-encrypted at rest on rotation.

4. Verify: check `GET /api/v1/settings/services-health/` — the
   `"Verschlüsselung"` entry should read `"online"`. `ENCRYPTION_KEY_PREVIOUS`
   (or the `opendox_encryption_key_previous` Swarm secret) can now be
   removed.

See `backend/components/security/key_rotation.py` for the implementation.

---

# Deployment Security

## Docker Security

### Image Security

All four first-party images (`Dockerfile`, `parakeet_server/Dockerfile`,
`whisper_server/Dockerfile`, `garage/init/Dockerfile`) run as an
unprivileged `appuser` (UID/GID 1000), not root:

```dockerfile
RUN useradd -m -u 1000 appuser \
    && chown -R 1000:1000 /app
USER appuser
```

Applies to newly created deployments/volumes. Upgrading an existing
deployment whose named volumes (e.g. `app-chunks`, the Whisper model-cache
volume) were populated by an older root-based image requires a one-time
`chown -R 1000:1000` on those volumes first — Docker only applies the
image's ownership to a named volume the first time it's created empty, not
on every container start. No `read_only`/capability restrictions beyond
that are applied yet — see Container Security below.

### Container Security

Recommended, not currently set in `docker-compose.yml`/`docker-swarm.yml`:

```yaml
services:
  app:
    read_only: true
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - CHOWN
      - SETGID
      - SETUID
    tmpfs:
      - /tmp:noexec,nosuid,size=100m
```

`read_only: true` would need testing against this app specifically — it
writes to `chunks/` (PCM scratch space) at runtime, which would need an
explicit writable `tmpfs`/volume mount carved out if this is adopted.

## Network Security

### Reverse Proxy (Apache — matches the actual documented deployment)

The reference production setup (see `AGENTS.md`) terminates TLS at
**Apache**, not Nginx. The WebSocket route for live recording
(`/api/v1/records/ws/record`) needs `mod_proxy_wstunnel`, declared
**before** the catch-all proxy rule — a generic reverse-proxy example that
omits this will silently break live transcription (binary WS frames get
through `mod_proxy_http` for text, but not audio):

```apache
<VirtualHost *:443>
    ServerName opendox.example.com

    SSLEngine on
    SSLCertificateFile /etc/apache2/ssl/opendox.crt
    SSLCertificateKeyFile /etc/apache2/ssl/opendox.key

    # Overwrite, don't just append — a client-supplied value here would
    # otherwise be forwarded straight through to the app.
    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Port  "443"
    RequestHeader set X-Forwarded-Host  "opendox.example.com"
    RequestHeader set X-Forwarded-For   %{REMOTE_ADDR}s

    # WebSocket route MUST come before the catch-all ProxyPass below.
    ProxyPass        "/api/v1/records/ws/record" "ws://127.0.0.1:20000/api/v1/records/ws/record"
    ProxyPassReverse "/api/v1/records/ws/record" "ws://127.0.0.1:20000/api/v1/records/ws/record"

    ProxyPass        "/" "http://127.0.0.1:20000/"
    ProxyPassReverse "/" "http://127.0.0.1:20000/"

    Header always set Strict-Transport-Security "max-age=31536000; includeSubDomains"
    Header always set X-Frame-Options "SAMEORIGIN"
    Header always set X-Content-Type-Options "nosniff"
    Header always set Referrer-Policy "strict-origin-when-cross-origin"
</VirtualHost>
```

Required Apache modules: `a2enmod proxy proxy_http proxy_wstunnel ssl
headers`. Set `TRUSTED_PROXY_IPS`/`CORS_ALLOWED_ORIGINS` on the app to
match (see JWT Token Security above) — without `X-Forwarded-Host` set
correctly here, the OIDC redirect URI will be built from the internal
`127.0.0.1:20000` address instead of the public one.

None of the above security headers are currently set by openDox itself
(only `Permissions-Policy: microphone=(self), camera=(self)`, added in
`backend/run.py`) — they need to come from the reverse proxy.

Standalone, ready-to-adapt copies of the vhost above (Apache) and an
equivalent Nginx server block live in `docs/examples/apache-vhost.conf.example`
and `docs/examples/nginx-vhost.conf.example`. Neither includes a
Content-Security-Policy — see the comment in those files for why (inline
`window.__ROOT_PATH__` injection, WebSocket, blob: AudioWorklet).

### Database Security

`docker-swarm.yml`/`docker-compose.yml` already do this: `postgres`/`redis`
have no `ports:` mapping to the host — only reachable from other
containers on the same Docker network, never directly from the internet.
`docker-swarm.yml` additionally sources `POSTGRES_PASSWORD_FILE` from a
Swarm secret rather than a plaintext env var.

**Not implemented**: Redis has no authentication (`requirepass`) configured
in either compose file — acceptable only because it's not exposed to the
host, but still a gap if the Docker network itself isn't trusted (e.g.
other untrusted workloads on the same host).

---

# Security Checklist

## Pre-Deployment

- [ ] All secrets are stored in environment variables or Docker secrets (see Key Management above)
- [ ] `.env` file is in `.gitignore`
- [ ] `CORS_ALLOWED_ORIGINS` is set to the real public origin(s), not left at the `*` default
- [ ] `TRUSTED_PROXY_IPS` is verified correct if the reverse proxy is NOT on the same host as the app container (the default auto-detection assumes same-host)
- [ ] HTTPS is configured (not just HTTP) at the reverse proxy
- [ ] Database and Redis are not exposed to the internet (default in both compose files — verify no `ports:` was added)
- [ ] Redis requires authentication if the Docker network isn't fully trusted (not implemented by default — see Database Security above)
- [ ] LDAP connection uses `ldaps://`
- [ ] Rate limiting is configured for everything except `/login` (the login endpoint has an in-process limiter, 5 requests per 60 s per client IP, `rate_limiter.py`; all other endpoints need a reverse-proxy or gateway solution, and the limiter is per process)

## Post-Deployment

- [ ] Security headers are present in HTTP responses (must be set at the reverse proxy — see Network Security above)
- [ ] SSL certificate is valid and not expiring soon
- [ ] Database backups are encrypted
- [ ] Health checks are working (`/api/endpoint`, `/api/ready`, `/api/version`, `GET /api/v1/settings/services-health/`)
- [ ] No hardcoded credentials in logs
- [x] Container runs as non-root user (all 4 first-party images — see Docker Security above; existing pre-upgrade volumes need a one-time `chown`)

## Regular Maintenance

- [ ] Review access logs monthly
- [ ] Rotate encryption keys annually
- [ ] Update dependencies (check for CVEs)
- [ ] Review user permissions and LDAP/OIDC group-to-role mappings
- [ ] Test backup restoration
- [ ] Security scan of Docker images

---

# GDPR Compliance

> This section describes what is and isn't implemented today — verified
> against the code, not aspirational. For the full data-flow picture
> (what goes where, encryption status, external recipients) see
> [`docs/data-mapping.md`](docs/data-mapping.md). None of this is legal advice.

## Technical Measures (Article 32)

| Measure | Implementation | Status |
|---------|---------------|--------|
| Encryption at rest | Fernet field-level encryption (see table above) | ✅ if `ENCRYPTION_KEY` is set |
| Encryption in transit | Depends entirely on how endpoints (LLM, Whisper, LDAP, reverse proxy) are configured — not enforced by the app | ⚠️ (configure `https://`/`ldaps://`) |
| Access Control | JWT + optional LDAP/OIDC + role-based (`admin`/`moderator`/`demo_viewer`/`user`) | ✅ |
| Data minimization | Raw PCM/WAV audio is deleted immediately after a *successful* transcription; on failure it's kept unencrypted in `chunks/failed/` so an admin can retry, and moved encrypted to the object store after `FAILED_AUDIO_RETENTION_DAYS` (default 3) if one is configured — see "Retry for failed transcriptions" in `AGENTS.md`'s Audio File Cleanup section | ⚠️ |
| Availability | PostgreSQL backups | ⚠️ (operator's responsibility, not automated by this repo) |

## Organizational Measures

Outside this repository's scope — operator responsibility:

- [ ] **Privacy Policy**: Published and accessible
- [ ] **Data Processing Agreement (DPA)**: With hosting provider and any
      externally-configured LLM/sanitizer endpoint
- [ ] **Records of Processing Activities (ROPA)**: Documented — see
      [`docs/data-mapping.md`](docs/data-mapping.md) as a starting point
- [ ] **Data Retention Policy**: Define deletion schedules (the app itself
      has no automatic retention/expiry — records persist until manually
      deleted)
- [ ] **Breach Notification Procedure**: 72h to authorities

## Data Subject Rights — actually implemented vs. not

| Right | Status | Detail |
|---|---|---|
| Rectification | ✅ Implemented | `PUT /record/{id}`, `PUT /users/{id}` allow editing records and user data |
| Erasure | ⚠️ Partially | `DELETE /record/{id}` performs an immediate **hard** delete — there is no soft-delete/undo, and no bulk "erase everything for this patient" tooling if a patient's data is scattered across multiple records |
| Access | ❌ Not implemented | No self-service data export endpoint exists. Exporting a user's/patient's data today means a manual database query |
| Portability | ❌ Not implemented | Same gap as Access — no JSON/structured export tooling |
| Objection (opt out of LLM processing) | ❌ Not implemented | There is no per-record or per-patient consent flag; if a category has an LLM step configured, it always runs |

If any of these rights need to be demonstrably supported for a given
deployment, that tooling does not exist yet and would need to be built —
treat the rows above as a gap list, not a feature list.

---

# Security Best Practices

## For Administrators

1. **Use strong passwords** for all accounts (min 16 chars, mixed case, symbols)
2. **Multi-factor authentication is not implemented anywhere in this app**
   (local, LDAP, or OIDC-side) — if your identity provider enforces MFA
   itself, that protects the directory login only, openDox adds nothing on
   top
3. **Regular audits** of user accounts, roles, and LDAP/OIDC group mappings
4. **Monitor logs** for suspicious activity (failed logins, unusual access patterns)
5. **Keep backups** encrypted and test restoration quarterly
6. **Update promptly** when security patches are released

## For Developers

1. **Never commit secrets** - use environment variables or Docker secrets
2. **Validate all inputs** - use Pydantic models for API validation
3. **Use parameterized queries** - SQLModel/SQLAlchemy prevents SQL injection; if you ever need a raw LDAP filter or similar, escape it (see `ldap.py`'s `escape_filter_chars` usage as the pattern to follow)
4. **Sanitize output** - React escapes by default; never use `dangerouslySetInnerHTML` with user-controlled content
5. **Handle errors securely** - don't leak stack traces in production
6. **Use dependency scanning** - `safety check` for Python packages

```bash
# Dependency vulnerability scanning
pip install safety
safety check

# Docker image scanning (docker scan is discontinued; use e.g. Trivy or Docker Scout)
trivy image opendox:latest
```

## For End Users

1. **Lock your workstation** when away
2. **Don't share credentials** - each user should have own account
3. **Log out** when finished
4. **Report suspicious activity** immediately
5. **Verify recipients** before copying patient data to clipboard

---

# Incident Response

## Severity Levels

| Level | Description | Examples | Response Time |
|-------|-------------|----------|---------------|
| **Critical** | Active exploitation, data breach | Ransomware, unauthorized admin access | Immediate |
| **High** | Potential breach, severe vulnerability | SQL injection, auth bypass | 24 hours |
| **Medium** | Security weakness, no active exploitation | Weak cipher, information disclosure | 7 days |
| **Low** | Best practice deviation | Missing header, outdated TLS | Next release |

## Response Playbook

### Critical Incident

1. **Contain** (0-1 hour)
   - Isolate affected systems
   - Revoke compromised credentials (rotate `SECRET_KEY` to invalidate all sessions, see Key Management)
   - Enable maintenance mode

2. **Assess** (1-4 hours)
   - Determine scope of breach
   - Identify affected data/users
   - Preserve evidence (logs, images)

3. **Notify** (4-72 hours)
   - Internal stakeholders
   - Data protection authority (if required)
   - Affected users (if required)

4. **Remediate** (ongoing)
   - Patch vulnerabilities
   - Rotate all keys/passwords (see Key Rotation above)
   - Restore from clean backups

5. **Review** (post-incident)
   - Root cause analysis
   - Process improvements
   - Security enhancements

---

# Contact

**Security Contact:**
- Email: christopher.abanilla@gmx.de (dedicated `security@` alias TBD)

**Responsible Disclosure:**
We follow a 90-day disclosure policy. After fix confirmation, we will:
1. Issue security advisory
2. Credit reporter (if desired)
3. Update this document

---

# References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [GDPR Guidelines](https://gdpr.eu/)
- [Docker Security](https://docs.docker.com/engine/security/)
- [PostgreSQL Security](https://www.postgresql.org/docs/current/security.html)
- [`docs/data-mapping.md`](docs/data-mapping.md) — full data-flow mapping
- [`docs/pii.md`](docs/pii.md) — PII sanitizer pipeline detail
- `AGENTS.md` (repo root, also linked as `CLAUDE.md`) — technical architecture reference

---

*Last updated: 2026-10-08*
*Version: 2.1 — reconciled against the implementation as of v0.8.3*
