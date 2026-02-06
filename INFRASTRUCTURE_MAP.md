# Creative Merchandise Infrastructure Map

## Overview
Legacy promotional products platform running on AWS EC2 instances with internal `.cloud` DNS via /etc/hosts.

## Discovered Servers

### Database Servers
| Hostname | IP | Notes |
|----------|-----|-------|
| db.cloud / db1.cloud | 10.248.21.220 | Primary database (internal) |
| db2.cloud | 10.251.147.112 | Secondary database (internal) |
| db3.cloud | 184.72.247.230 | Database server (public IP) |
| db-sandbox.cloud | 10.46.159.155 | Sandbox/dev database |
| db.cm / db1.cm | 75.101.130.57 | Legacy database reference |

### Web/Application Servers
| Hostname | IP | Notes |
|----------|-----|-------|
| trunk1.creativemerch.com | (public) | Main dev/staging server |
| admin1.cloud | 10.210.170.115 | Admin panel server |
| admin.cm / admin1.cm | 75.101.147.12 | Legacy admin reference |
| stage1.cloud | 10.193.14.223 | Staging environment |
| stage1.cm | 75.101.147.63 | Legacy staging reference |
| www1.cloud | 10.86.11.208 | Web server 1 |
| www2.cloud | 10.74.42.148 | Web server 2 |
| www3.cloud | 10.209.77.31 | Web server 3 |
| www4.cloud | 10.245.149.134 | Web server 4 |
| www5.cloud | 10.214.183.148 | Web server 5 |
| www6.cloud | 10.71.54.240 | Web server 6 |
| www1-4 (legacy) | 75.101.149.x | Legacy web servers |

### Infrastructure
| Hostname | IP | Notes |
|----------|-----|-------|
| lb1.cloud | 10.192.149.157 | Load balancer |
| lb.cm / lb1.cm | 75.101.142.22 | Legacy load balancer |
| fs.cloud / fs1.cloud / fs2.cloud | 10.69.164.137 | File storage |
| fs.cm / fs1.cm | 75.101.147.80 | Legacy file storage |
| cache.cloud | 10.110.21.134 | Cache server (Memcached/Redis?) |
| mailer1.cloud | 10.249.193.236 | Email server |
| utility1.cloud / logs.cloud | 10.169.33.225 | Utility/logging server |

## Database Configuration

### Credentials (from cm_v3.config.php)
```
Database: cm_v3_production
Username: cm
Password: DooPu3oJ0chi
```

### Config File References (outdated RDS hostnames)
- DB_REPLICA: db-replica1.chfdb3cuiva8.us-east-1.rds.amazonaws.com (NXDOMAIN)
- DB_MASTER: db-master1.chfdb3cuiva8.us-east-1.rds.amazonaws.com (NXDOMAIN)

**Note**: The RDS hostnames don't resolve anywhere (NXDOMAIN even from trunk1).

### Actual Database Location
Based on network traffic analysis:
- Observed connection attempt to **52.21.216.34:3306** (SYN_SENT state)
- Port 3306 is filtered from external IPs
- Database likely lives behind AWS security group, accessible only from production instances

### Database Access Strategy
1. **trunk1 is a DEV server** - does NOT have database connectivity
2. **Production servers** (admin1.cloud, www1-6.cloud) likely CAN connect
3. For imports, we must either:
   - Use the web admin UI (Playwright automation via browser_import.py)
   - Get SSH access to a production server (admin1 or www1)
   - Request firewall rule to allow trunk1 → database

## Access Methods

### SSH Keys Available
| Key Name | Format | Purpose |
|----------|--------|---------|
| CMAdminKey.pem | PEM | ✅ Works for trunk1 (ec2-user) |
| v3instance.ppk | PPK | Unknown - may be for v3 app server |
| stripebackup.ppk | PPK | Stripe backup server? |
| serverSL.ppk | PPK | Unknown - SL server? |
| creativemerchPK.ppk | PPK | General CM access? |

**Note**: PPK files need to be converted to PEM for OpenSSH:
```bash
puttygen keyfile.ppk -O private-openssh -o keyfile.pem
```

### SSH Access (Confirmed)
```bash
ssh -i ~/.ssh/CMAdminKey.pem ec2-user@trunk1.creativemerch.com
```

### Web Admin
- URL: https://admin.creativemerch.com
- Login endpoint: POST /ae_scripts/login.php

## CloudFront CDN Distributions
| Distribution | Purpose | S3 Bucket |
|--------------|---------|-----------|
| dqrxzyzyhbzmu.cloudfront.net | Dynamic content | Unknown |
| d2t0gcpna5v47p.cloudfront.net | Product images | cm_products |
| dpbxvxue3c4z7.cloudfront.net | Static custom content | cm_static/custom |

**Note**: These CloudFront distributions may be connected to the 30TB storage issue.

## Tech Stack
- OS: Amazon Linux 2018.03
- Web Server: Apache
- PHP: 5.6.40
- MySQL: 5.5.62 (or compatible)
- Frontend: jQuery 1.3.1
- CDN: CloudFront

## AWS Account
- **Account ID**: 030249209621
- **IAM User**: cmS3ProductsUploader (S3-only access)

### S3 Buckets Discovered
| Bucket | Notes |
|--------|-------|
| cm-backups | Likely large - no list access |
| cm-products | Product images (CloudFront source) |
| cm-static | Static assets |
| cm-system-logs | Logs |
| cm-promostandards | PromoStandards integration |
| efs-backup-* | EFS backup buckets (4 of them) |
| montycloud-* | MontyCloud reports |
| 030249209621-dms-report | DMS migration reports |

### EFS Backup Buckets (Possible 30TB Culprits)
- efs-backup-efslogbucket-6y6mi46t4reh
- efsbinariesbackup-efslogbucket-1bmu2idyhhxsl
- efscachebackup-efslogbucket-1r2x8dng4jvbs
- efsdynbackup-efslogbucket-aepdxgaprn47

**Note**: Need higher-privilege AWS creds to audit bucket sizes.

## Cost Issues
- ~$3k/month AWS bill
- ~30TB blob storage - likely EFS backups or cm-backups
- Need admin AWS access to audit

## Related Documentation
- [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) - Full database schema and API reference
- [HANDOFF.md](./HANDOFF.md) - Session handoff notes

## TODO
- [x] Discover database schema - See DATABASE_SCHEMA.md
- [x] Map product-related tables - See DATABASE_SCHEMA.md
- [x] Document API endpoints - See DATABASE_SCHEMA.md
- [ ] Test other SSH keys (v3instance, stripebackup, serverSL, creativemerchPK)
- [ ] Identify the 30TB storage blob (check S3 buckets)
- [ ] Get database access from production server
- [ ] Set up Playwright automation for browser_import.py
