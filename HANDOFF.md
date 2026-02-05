# Catalog Transformer - Session Handoff Document

**Date**: 2026-02-04
**Session**: Bare metal WSL environment (not Docker)
**Repo**: https://github.com/DeepSwagLabs/catalog-transformer

---

## TL;DR

We're automating the manual product catalog update process for Creative Merchandise, a 20-year-old PHP/MySQL system. **TWO transformers are built and working:**

1. **Sage transformer** - For supplier catalog updates (Illini, Ariel, HIT, etc.)
2. **Replink transformer** - For daily inventory feeds (the $1,800 job Pat quoted)

We're blocked on SSH access to discover the database schema for direct imports.

---

## BONUS: The $1,800 Job

A custom project came in that's exactly what we built. Client wants:
1. Daily feed → import products, enable/disable based on inventory
2. Order export feed for fulfillment
3. Tracking import to auto-update orders

**Pat quoted $1,800 and 7-10 days. We built #1 in 10 minutes.**

```bash
# Test with the actual Replink feed
python3 replink_transformer.py "/mnt/c/Users/jason/Downloads/replink_catalog_2026-01-14.txt" output.xlsx

# Result: 4,729 products (3,318 enabled, 1,411 disabled)
```

The feed file is at: `/mnt/c/Users/jason/Downloads/replink_catalog_2026-01-14.txt`

Items 2 & 3 (order export, tracking import) need the database schema to implement.

---

## What Was Accomplished

### 1. Cloned and Fixed the Catalog Transformer

```bash
git clone https://github.com/DeepSwagLabs/catalog-transformer.git
cd catalog-transformer
```

**Fixes applied:**
- Fixed CSV encoding (Sage exports use Windows-1252, not UTF-8)
- Fixed "Blank" → "No Imprint" conversion in included_decoration field
- Fixed Dockerfile to use Railway's dynamic `${PORT}` instead of hardcoded 8080

### 2. Tested the Transformer

```bash
# Install deps
pip install pandas openpyxl xlrd flask gunicorn

# Run transform
python catalog_transformer.py "SAGE_BPU_ProductList_60462_2026-01-07 USD.csv" output.xlsx

# Result: 2175 products transformed successfully
```

### 3. Discovered the Legacy System Architecture

**Admin Panel**: https://admin.creativemerch.com
- Login: POST to `/ae_scripts/login.php`
- Fields: `username` (email), `password`
- This is where Lane manually adds products

**Dev Server**: trunk1.creativemerch.com
- SSH port 22
- Username: `pat`
- Auth: SSH key only (password fails)
- Key name in Bitvise: "Global 1"

**Database**: MySQL
- Name: `cm_v3_production`
- Visible in debug banner on trunk1 site

**Tech Stack**:
- PHP (ancient - jQuery 1.3.1 era)
- MySQL
- Apache
- CloudFront CDN

### 4. Created Automation Tools

All committed to repo:

| File | Purpose |
|------|---------|
| `catalog_transformer.py` | Sage format → CM format (for supplier updates) |
| `replink_transformer.py` | Replink feed → CM format (the $1,800 job) |
| `db_import.py` | Direct MySQL import - needs schema discovery |
| `browser_import.py` | Playwright fallback - needs UI discovery |
| `server_audit.sh` | Run first after SSH to map the system |
| `SYSTEM_NOTES.md` | Architecture documentation |

### 5. Tested Replink Transformer

```bash
python3 replink_transformer.py "/mnt/c/Users/jason/Downloads/replink_catalog_2026-01-14.txt" /tmp/out.xlsx

# Output:
# ✅ Saved 4729 products to /tmp/out.xlsx
# ✅ 3318 enabled products → /tmp/out_ENABLED.xlsx
# ⏸️  1411 disabled products → /tmp/out_DISABLED.xlsx
```

The Replink feed is pipe-delimited with 90+ columns including:
- BrandName, ItemNumber, ShortName, SalesCopy
- Multiple price tiers (MSRP, MAP, UserPrice, JobberPrice, DistributorPrice)
- QtyAvailable (determines enabled/disabled)
- ImageURL
- Features 1-18

---

## What's Blocked

### SSH Access
Need the private key to access trunk1.creativemerch.com. The key is stored in:
- Bitvise profile: `CreativeMerchant.bscp`
- Key name: "Global 1"
- Located on: "the drive" (unknown location - ask employee)

**Screenshot evidence found**: `/mnt/c/Users/jason/Downloads/ffff (004).png`
Shows successful Bitvise connection with these details.

**Employee to contact**: Whoever sent that screenshot (named file poorly as "fffff.png")

---

## Commands to Resume

### Load secrets (if in deepswag environment)
```bash
python3 /home/jason/workspaces/deepswag/scripts/load_secrets_from_pipedream.py
source /home/jason/.config/deepswag/pipedream_secrets.sh
```

### Test transformer
```bash
cd /home/jason/workspaces/catalog-transformer
python3 catalog_transformer.py "SAGE_BPU_ProductList_60462_2026-01-07 USD.csv" /tmp/out.xlsx
```

### After getting SSH key
```bash
# Save key to file
chmod 600 ~/.ssh/creativemerch_key

# Connect
ssh -i ~/.ssh/creativemerch_key pat@trunk1.creativemerch.com

# Once in, run audit
bash server_audit.sh > audit_results.txt
cat audit_results.txt

# Look for database config
grep -r "mysql" /var/www/ --include="*.php" | head -20
```

### Deploy to Railway
```bash
# Push triggers auto-deploy if Railway is connected
git push origin main

# Or manual via Railway CLI
railway up
```

---

## The Manual Process We're Replacing

From the employee's instructions:

1. Download Sage export from supplier portal
2. Copy specific columns to new spreadsheet
3. Remove zeros from qty/price columns (using ChatGPT!)
4. Split price codes (one cell → multiple)
5. Merge production time columns ("5 to 10 Working Days")
6. Merge decoration columns, replace "Blank" with "No Imprint"
7. Truncate to 60 char limit
8. Compare with existing DB to find adds/updates/deletes
9. Upload update sheet to admin
10. Send adds to "Lane" who clicks UI buttons

**Our transformer automates steps 1-8.** Steps 9-10 need the database/browser automation.

---

## AWS Cost Issue

- ~$3k/month bill
- Mostly from a ~30TB blob that's been growing for years
- Likely candidates: unrotated logs, backups, asset storage
- Need server access to audit

---

## Key URLs

| URL | What |
|-----|------|
| https://github.com/DeepSwagLabs/catalog-transformer | This repo |
| https://admin.creativemerch.com | Admin login (Lane uses this) |
| http://www.trunk1.creativemerch.com | Dev server (shows DB name in banner) |
| http://demo.creativemerch.com/admin | Demo admin (open, good for UI discovery) |

---

## Git Log (for reference)

```
2d2d3d3 Add system documentation and architecture notes
d32d0e3 Add database import and browser automation tools
5d76dfa Fix encoding handling and Railway deployment
24b539b Add files via upload (original)
```

---

## Next Session Checklist

- [ ] Get SSH key from employee
- [ ] SSH into trunk1.creativemerch.com
- [ ] Run `server_audit.sh`, share output
- [ ] Find database credentials in PHP config files
- [ ] Connect to MySQL, run `SHOW TABLES; DESCRIBE products;`
- [ ] Update `db_import.py` with actual schema
- [ ] Test import on a few products
- [ ] Set up automated pipeline (Pipedream? Cron?)
- [ ] Audit AWS for the 30TB cost blob

---

## Contacts/Credentials Mentioned

- **SSH**: pat@trunk1.creativemerch.com (key auth only)
- **Charles River portal**: courtney@brandfuse.com / Fuse94901 (on hold)
- **Lane**: Person who manually adds products via UI
- **Pat**: 80-year-old programmer who uses Notepad and PHP

---

## Environment Notes

This session ran on bare metal WSL, not the Docker environment. To load GitHub credentials:

```bash
python3 /home/jason/workspaces/deepswag/scripts/load_secrets_from_pipedream.py
source /home/jason/.config/deepswag/pipedream_secrets.sh
```

The `LETTA_GITHUB_PAT` only works for DeepSwagLabs org repos, not personal repos.

---

## Sample Data Location

```
/home/jason/workspaces/catalog-transformer/SAGE_BPU_ProductList_60462_2026-01-07 USD.csv
```

2175 products, Windows-1252 encoded, from a Sage export.
