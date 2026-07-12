# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to: **security@opendox.local**

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

## Authentication & Authorization

### JWT Token Security

openDox uses JWT tokens with the following security measures:

- **Access Tokens**: 30-minute expiration
- **Refresh Tokens**: 7-day expiration
- **Algorithm**: HS256 (HMAC with SHA-256)
- **Storage**: Tokens are stored in `localStorage` (browser)
- **CSRF Protection**: CSRF tokens in cookies for state-changing operations

### LDAP Integration

When using LDAP/Active Directory:

- Passwords are **never stored** in the database for LDAP users
- Only the username and metadata are synced locally
- SSL/TLS is recommended for LDAP connections
- Bind credentials should use a service account with minimal privileges

## Data Encryption

### Field-Level Encryption

Sensitive patient data is encrypted at the field level using **Fernet symmetric encryption**:

| Field | Encrypted | Algorithm |
|-------|-----------|-----------|
| `Record.content` | ✅ Yes | Fernet (AES-128-CBC) |
| `Record.summarize` | ✅ Yes | Fernet (AES-128-CBC) |
| `Record.title` | ❌ No | Plaintext |
| `User.name` | ❌ No | Plaintext |
| `User.hashed_password` | ✅ N/A | bcrypt |

**Why field-level encryption?**
- Searchable metadata remains accessible (title, timestamps)
- Patient content is protected even if database is compromised
- GDPR-compliant data protection

### Password Hashing

User passwords are hashed using **bcrypt** with:
- **Salt**: Automatically generated per password
- **Work Factor**: 12 rounds (configurable)
- **Algorithm**: Blowfish-based adaptive hashing

```python
# Example bcrypt hash
$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyNiAYMyzJ/IiO
#    └┘ └┘  └──────────────────────────────────────────────────────────┘
#    │  │                      Hash + Salt
#    │  └── Cost factor (2^12 = 4096 rounds)
#    └── bcrypt version
```

## Key Management

### Encryption Key Generation

```bash
# Generate a Fernet key for field encryption
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Output: a URL-safe base64-encoded 32-byte key
# Example: gAAAAABgJ8xC3B8vB8mP6mP9mP8mP7mP6mP9mP8mP9mP8mP9mP8=
```

### Secure Key Storage

#### Option 1: Environment Variables (Development)

```bash
# .env file (NEVER commit this file!)
ENCRYPTION_KEY=gAAAAABgJ8xC3B8vB8mP6mP9mP8mP7mP6mP9mP8mP9mP8mP9mP8=
SECRET_KEY=your-secret-key-for-jwt
```

#### Option 2: Docker Secrets (Production - Recommended)

```yaml
# docker-compose.yml
version: '3.8'

secrets:
  encryption_key:
    file: ./secrets/encryption_key
  jwt_secret:
    file: ./secrets/jwt_secret

services:
  app:
    image: opendox:latest
    secrets:
      - encryption_key
      - jwt_secret
    environment:
      ENCRYPTION_KEY_FILE: /run/secrets/encryption_key
      SECRET_KEY_FILE: /run/secrets/jwt_secret
```

```bash
# Create secrets directory
mkdir -p secrets

# Generate keys
echo "gAAAAABgJ8xC..." > secrets/encryption_key
echo "your-jwt-secret" > secrets/jwt_secret

# Set restrictive permissions
chmod 600 secrets/*

# Add to .gitignore
echo "secrets/" >> .gitignore
```

### Key Rotation

**When to rotate keys:**
- Suspected compromise
- Employee departure
- Annual security review
- After security incident

**Rotation process (automatic):**

1. Generate a new key:
```bash
NEW_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
```

2. Set both env vars for the next restart (the old key is needed once, to
   decrypt existing data before re-encrypting it under the new key):
```bash
ENCRYPTION_KEY_PREVIOUS=<the old key>
ENCRYPTION_KEY=$NEW_KEY
```

3. Restart the container. On startup the app detects the key change (via a
   fingerprint stored in the `EncryptionKeyState` table), re-encrypts every
   `Record.content`/`summarize`/`pii_mapping` value in place, and logs
   `Encryption key rotation complete (N records re-encrypted)`. The process
   is idempotent and safe to interrupt — an incomplete run resumes on the
   next restart with the same env vars.

4. Verify: check `GET /api/v1/settings/services-health/` — the
   `"Verschlüsselung"` entry should read `"online"`. `ENCRYPTION_KEY_PREVIOUS`
   can now be removed from the environment.

See `backend/components/security/key_rotation.py` for the implementation and
`docs/superpowers/specs/2026-07-12-encryption-key-rotation-design.md` for the
full design rationale.

---

# Deployment Security

## Docker Security

### Image Security

```dockerfile
# Use official base images
FROM python:3.12-slim-bookworm

# Run as non-root user
RUN useradd -m -u 1000 appuser
USER appuser

# Install security updates
RUN apt-get update && apt-get upgrade -y

# Remove unnecessary packages
RUN apt-get remove -y gcc build-essential
```

### Container Security

```yaml
# docker-compose.yml security options
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

## Network Security

### Reverse Proxy (Nginx/Traefik)

```nginx
# nginx.conf
server {
    listen 443 ssl http2;
    server_name opendox.example.com;

    # SSL Configuration
    ssl_certificate /etc/nginx/ssl/opendox.crt;
    ssl_certificate_key /etc/nginx/ssl/opendox.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256';
    ssl_prefer_server_ciphers on;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "microphone=(self), camera=()" always;

    location / {
        proxy_pass http://app:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Database Security

```yaml
# docker-compose.yml
services:
  postgres:
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets:
      - db_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    # Network isolation
    networks:
      - backend
    # No external exposure
    expose:
      - "5432"
    # NOT "5432:5432" (no host port mapping)

secrets:
  db_password:
    file: ./secrets/db_password
```

---

# Security Checklist

## Pre-Deployment

- [ ] All secrets are stored in environment variables or Docker secrets
- [ ] `.env` file is in `.gitignore`
- [ ] `secrets/` directory is in `.gitignore`
- [ ] HTTPS is configured (not just HTTP)
- [ ] Database is not exposed to internet
- [ ] Redis (if used) requires authentication
- [ ] LDAP connection uses SSL/TLS
- [ ] File uploads are limited in size
- [ ] Rate limiting is configured

## Post-Deployment

- [ ] Security headers are present in HTTP responses
- [ ] SSL certificate is valid and not expiring soon
- [ ] Database backups are encrypted
- [ ] Audit logging is enabled
- [ ] Health checks are working
- [ ] No hardcoded credentials in logs
- [ ] Container runs as non-root user

## Regular Maintenance

- [ ] Review access logs monthly
- [ ] Rotate encryption keys annually
- [ ] Update dependencies (check for CVEs)
- [ ] Review user permissions
- [ ] Test backup restoration
- [ ] Security scan of Docker images

---

# GDPR Compliance

## Data Protection Measures

### Technical Measures (Article 32)

| Measure | Implementation | Status |
|---------|---------------|--------|
| Pseudonymization | Fernet encryption keys | ✅ |
| Encryption | Field-level AES-128 | ✅ |
| Access Control | JWT + LDAP + RBAC | ✅ |
| Integrity | HMAC in Fernet tokens | ✅ |
| Availability | PostgreSQL backups | ⚠️ (configure) |

### Organizational Measures

- [ ] **Privacy Policy**: Published and accessible
- [ ] **Data Processing Agreement (DPA)**: With hosting provider
- [ ] **Records of Processing Activities (ROPA)**: Documented
- [ ] **Data Retention Policy**: Define deletion schedules
- [ ] **Breach Notification Procedure**: 72h to authorities

### Data Subject Rights

openDox supports GDPR rights through:

- **Right to Access**: API endpoint for exporting user data
- **Right to Erasure**: Soft delete with hard delete option
- **Right to Rectification**: Edit endpoints for records
- **Right to Portability**: JSON export of patient data
- **Right to Object**: Opt-out of LLM processing (settings)

```python
# Example: Data export for GDPR request
@auth_bp.get("/export-data")
async def export_user_data(current_user: User = Depends(get_current_user)):
    """Export all user data for GDPR portability request."""
    records = await get_user_records(current_user.id)
    return {
        "user": current_user.to_dict(),
        "records": [r.to_dict() for r in records],
        "export_date": datetime.utcnow().isoformat()
    }
```

---

# Security Best Practices

## For Administrators

1. **Use strong passwords** for all accounts (min 16 chars, mixed case, symbols)
2. **Enable 2FA** where possible (LDAP integration supports MFA)
3. **Regular audits** of user accounts and permissions
4. **Monitor logs** for suspicious activity (failed logins, unusual access patterns)
5. **Keep backups** encrypted and test restoration quarterly
6. **Update promptly** when security patches are released

## For Developers

1. **Never commit secrets** - use environment variables
2. **Validate all inputs** - use Pydantic models for API validation
3. **Use parameterized queries** - SQLModel prevents SQL injection
4. **Sanitize output** - XSS protection in React by default
5. **Handle errors securely** - don't leak stack traces in production
6. **Use dependency scanning** - `safety check` for Python packages

```bash
# Dependency vulnerability scanning
pip install safety
safety check

# Docker image scanning
docker scan opendox:latest
```

## For End Users

1. **Lock your workstation** when away
2. **Don't share credentials** - each user should have own account
3. **Log out** when finished (auto-logout after 30 minutes)
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
   - Revoke compromised credentials
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
   - Rotate all keys/passwords
   - Restore from clean backups

5. **Review** (post-incident)
   - Root cause analysis
   - Process improvements
   - Security enhancements

---

# Contact

**Security Team:**
- Email: security@opendox.local
- GPG Key: [Download public key](https://opendox.local/security.gpg)

**Emergency:**
- Phone: +49-XXX-XXXXXXX (24/7 hotline)

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

---

*Last updated: June 2025*  
*Version: 1.0*
