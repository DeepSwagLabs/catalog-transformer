# Creative Merchandise System Notes

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Creative Merchandise                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐     ┌──────────────────┐                  │
│  │ Admin Panel      │     │ Customer Stores   │                  │
│  │ admin.creative   │     │ demo.creative     │                  │
│  │ merch.com        │     │ merch.com         │                  │
│  └────────┬─────────┘     └────────┬─────────┘                  │
│           │                        │                             │
│           └────────────┬───────────┘                             │
│                        │                                         │
│              ┌─────────▼─────────┐                               │
│              │   trunk1.creative │  ◄── SSH (port 22)            │
│              │   merch.com       │      user: pat                │
│              │   (Dev Server)    │      auth: key "Global 1"     │
│              └─────────┬─────────┘                               │
│                        │                                         │
│              ┌─────────▼─────────┐                               │
│              │     MySQL         │                               │
│              │ cm_v3_production  │                               │
│              └───────────────────┘                               │
│                                                                  │
│  CDN: dpbxvxue3c4z7.cloudfront.net (static assets)              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Known Endpoints

| URL | Purpose |
|-----|---------|
| https://admin.creativemerch.com | Admin login panel |
| https://admin.creativemerch.com/ae_scripts/login.php | Login POST endpoint |
| http://www.trunk1.creativemerch.com | Dev/trunk server (public) |
| http://demo.creativemerch.com | Demo store |
| http://demo.creativemerch.com/admin | Demo admin (open access) |

## Technology Stack

- **Language**: PHP (ancient - jQuery 1.3.1 era)
- **Database**: MySQL (`cm_v3_production`)
- **Web Server**: Apache
- **CDN**: CloudFront
- **OS**: Unknown (likely Ubuntu/CentOS)

## SSH Access

- **Host**: trunk1.creativeMerch.com (note capital M)
- **Port**: 22
- **Username**: pat
- **Auth**: SSH key ("Global 1" in Bitvise)
- **Password**: Does not work, key required

The SSH key is stored in a Bitvise profile "CreativeMerchant.bscp" - need to get this from employee.

## Database

- **Name**: cm_v3_production
- **Table structure**: Unknown - need SSH access to discover
- **Likely tables**: products, suppliers, categories, users

## Suppliers in System

From the public supplier list:
- 1919 Candy Company
- Aakron Line
- Ariel Premium Supply
- HIT Promotional Products
- Illini
- And ~60+ more

## Current Manual Process

1. Download Sage export from supplier
2. Transform in Excel (column mapping, zero cleanup, merges)
3. Upload to admin panel via web UI
4. Manually fill quantity/price fields
5. Lane clicks buttons to add products

## Automation Status

| Component | Status |
|-----------|--------|
| Sage → DB format transform | ✅ Done (catalog_transformer.py) |
| HTTP API for transform | ✅ Done (Flask endpoints) |
| Railway deployment | 🔄 Ready to test |
| Direct DB import | 📝 Script ready, needs schema |
| Browser automation | 📝 Script ready, needs UI discovery |
| SSH access | ⏳ Waiting for key |

## AWS Cost Issues

- $3k/month bill
- ~30TB growing file/blob consuming most of cost
- Likely: unrotated logs, old backups, or asset storage
- Need to audit after SSH access

## Next Steps

1. [ ] Get SSH key from employee
2. [ ] Run server_audit.sh to understand system
3. [ ] Discover database schema
4. [ ] Update db_import.py with actual table/column names
5. [ ] Test direct database import
6. [ ] If DB import fails, fall back to browser automation
7. [ ] Audit AWS for the 30TB blob
