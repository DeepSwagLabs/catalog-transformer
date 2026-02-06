# Catalog Transformer - Session Handoff Document

**Last Updated**: 2026-02-05
**Repo**: https://github.com/DeepSwagLabs/catalog-transformer

---

## TL;DR

We're automating the manual product catalog update process for Creative Merchandise, a 20-year-old PHP/MySQL system.

**What Works:**
- SSH to trunk1.creativemerch.com ✅
- Sage transformer ✅
- Replink transformer ✅
- AWS S3 access (limited) ✅

**What's Blocked:**
- Database access (trunk1 is dev server, can't reach production DB)
- Need AWS Console access (have root creds, need 2FA)

---

## The $3k Replink Job

Client wants daily feed import with enable/disable based on inventory. **We built it.**

```bash
python3 replink_transformer.py "/mnt/c/Users/jason/Downloads/replink_catalog_2026-01-14.txt" output.xlsx
# Result: 4,729 products (3,318 enabled, 1,411 disabled)
```

Just need database access to push the changes.

---

## Access Summary

### We Have Access To

| Resource | How | Notes |
|----------|-----|-------|
| trunk1.creativemerch.com | SSH as ec2-user | `ssh -i ~/.ssh/CMAdminKey.pem ec2-user@trunk1.creativemerch.com` |
| AWS S3 | cmS3ProductsUploader creds | Limited permissions, can list buckets |
| Admin Panel | HTTPS | https://admin.creativemerch.com (have login creds) |
| PHP Source Code | Via trunk1 | /home/subversion/wc/pl/trunk/web/cm_v3/ |

### We Need Access To

| Resource | Blocker | Solution |
|----------|---------|----------|
| MySQL Database | trunk1 can't reach it (dev server) | Get AWS Console → find RDS endpoint |
| AWS Console | 2FA required | Root: wayde@creativemerch.com / q3Gm^XM$7B#dys%zd |
| v3Instance.ppk | Password protected | Ask Pat/Irvin for password |

---

## SSH Keys (in ~/.ssh/)

| Key | Status | Works For |
|-----|--------|-----------|
| CMAdminKey.pem | ✅ Working | trunk1 (ec2-user) |
| creativemerchPK.pem | ❌ Untested | Unknown |
| ServerSL.pem | ❌ Untested | Unknown |
| v3Instance.ppk | 🔒 Locked | Needs password |

Source files in: `/mnt/c/Users/jason/Downloads/CM/`

---

## AWS Account: 030249209621

### S3 Buckets
- cm-backups (no access - likely has 30TB)
- cm-products (CloudFront source)
- cm-static
- cm-system-logs
- 4x efs-backup-* buckets

### Credentials
```
User: cmS3ProductsUploader
Access Key: [REDACTED - see /mnt/c/Users/jason/Downloads/CM/Lane_credentials.csv]
Secret: [REDACTED]
```

---

## Database Schema (Reverse-Engineered)

See `DATABASE_SCHEMA.md` for full details.

### Key Tables
- **P_product**: product_id, item_number, product, active, supplier_id, user_id
- **P_supplier**: supplier_id, supplier
- **P_price_rel**: product_id, quantity, price

### Enable/Disable Products
```sql
UPDATE P_product SET active = 1 WHERE product_id = X;  -- enable
UPDATE P_product SET active = 0 WHERE product_id = X;  -- disable
```

### Config Credentials (stale - RDS decommissioned)
```
Database: cm_v3_production
Username: cm
Password: DooPu3oJ0chi
```

---

## Infrastructure Map

See `INFRASTRUCTURE_MAP.md` for complete details.

### Key Servers
- **trunk1.creativemerch.com** - Dev server (SSH works, no DB access)
- **admin.creativemerch.com** - Admin panel (HTTPS, behind LB)
- **v3.creativemerch.com** - Main site
- **52.21.216.34:3306** - Likely DB location (firewalled)

### Internal Hostnames (from /etc/hosts on trunk1)
- db.cloud / db1.cloud (10.248.21.220)
- admin1.cloud (10.210.170.115)
- www1-6.cloud (various IPs)
- cache.cloud, mailer1.cloud, etc.

**Note**: trunk1 cannot reach these internal hosts (different VPC/security group)

---

## Files Created

| File | Purpose |
|------|---------|
| catalog_transformer.py | Sage format → CM format |
| replink_transformer.py | Replink daily feed processor |
| db_import.py | MySQL import (needs working endpoint) |
| browser_import.py | Playwright automation (fallback) |
| INFRASTRUCTURE_MAP.md | Server/network documentation |
| DATABASE_SCHEMA.md | Tables, columns, API reference |

---

## Next Steps (When 2FA Available)

1. **Login to AWS Console** as root (wayde@creativemerch.com)
2. **Go to RDS → Databases** - find the actual working endpoint
3. **Go to S3** - check bucket sizes to find the 30TB
4. **Update db_import.py** with working RDS endpoint
5. **Test the Replink import** end-to-end

---

## Quick Commands

### SSH to trunk1
```bash
ssh -i ~/.ssh/CMAdminKey.pem ec2-user@trunk1.creativemerch.com
```

### AWS S3 (limited)
```bash
# Load creds from Lane_credentials.csv in /mnt/c/Users/jason/Downloads/CM/
AWS_ACCESS_KEY_ID=<from_csv> \
AWS_SECRET_ACCESS_KEY=<from_csv> \
aws s3 ls
```

### Test Replink Transformer
```bash
cd /home/jason/workspaces/catalog-transformer
python3 replink_transformer.py "/mnt/c/Users/jason/Downloads/replink_catalog_2026-01-14.txt" /tmp/out.xlsx
```

---

## Cost Issue

- ~$3k/month AWS bill
- ~30TB storage (likely cm-backups or EFS backup buckets)
- Need admin AWS access to audit

---

## Contacts

- **wayde@creativemerch.com** - AWS root (email forwards to irvin@)
- **Pat** - 80-year-old programmer, knows passwords
- **Lane** - Manual product entry person
- **Irvin** - Current contact
