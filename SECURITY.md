# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| main branch | ✅ |

## Reporting a Vulnerability

**Do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to: security@privatesearch.example.com

You will receive a response within 48 hours. If the issue is confirmed, we will work on a fix and coordinate disclosure.

## Security Architecture

### Privacy by Design

- No external search APIs required
- No query logging by default
- No user tracking or profiling
- No third-party analytics
- No advertising networks

### Crawler Security

The crawler makes outbound network requests and is treated as a security-sensitive component:

- **SSRF Protection**: Validates all URLs before fetching (scheme, hostname, IP resolution)
- **Private IP Blocking**: Rejects localhost, private ranges (10/8, 172.16/12, 192.168/16), link-local, cloud metadata endpoints
- **Scheme Validation**: Only allows HTTP/HTTPS
- **Redirect Safety**: Validates redirect targets, limits redirect chains
- **Domain Restrictions**: Configurable allowlist/blocklist
- **Rate Limiting**: Per-domain and global request limits
- **Request Size Limits**: Configurable maximum response size
- **Timeout Handling**: Connection and read timeouts
- **robots.txt Compliance**: Mandatory parsing and respect

### API Security

- Input validation on all endpoints
- Request size limits
- Rate limiting (configurable)
- Secure HTTP headers (CSP, HSTS, X-Frame-Options, etc.)
- CORS configuration (restrictive by default)
- No sensitive data in logs or error responses

### Data Protection

- Secrets via environment variables only
- No hardcoded credentials
- Database connections encrypted (TLS)
- Content hashes for deduplication (not reversible)

### Dependencies

- Regular dependency auditing (`pip-audit`, `npm audit`)
- Minimal dependency footprint
- Pinned versions in lockfiles

## Security Checklist for Contributors

Before submitting changes:

- [ ] No secrets in code or config
- [ ] Input validation on new endpoints
- [ ] SSRF protections for any new outbound requests
- [ ] Rate limiting considered
- [ ] Secure headers maintained
- [ ] Dependencies audited
- [ ] Tests include security-relevant cases

## Threat Model

### In Scope

- Search query privacy
- Crawler SSRF and network safety
- API injection attacks
- Data integrity in index/storage
- Denial of service via crawl targets

### Out of Scope (V1)

- Multi-user authentication/authorization
- Encrypted index at rest
- Advanced threat detection
- Compliance certifications

## Secure Deployment

For production deployments:

- Use HTTPS/TLS termination
- Restrict network access to database
- Configure firewall rules
- Enable audit logging
- Regular security updates
- Monitor for anomalous crawl behavior

## Disclosure Timeline

1. Report received → Acknowledge within 48 hours
2. Investigation → Initial assessment within 7 days
3. Fix development → Target 30 days for critical issues
4. Coordinated disclosure → After fix is deployed
5. Public advisory → After users have time to upgrade

## Security Contacts

- Primary: security@privatesearch.example.com
- Maintainers: Listed in GitHub repository

## Acknowledgments

We thank all security researchers who responsibly disclose vulnerabilities.