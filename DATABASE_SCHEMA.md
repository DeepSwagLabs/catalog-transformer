# Creative Merchandise Database Schema

## Core Tables

### P_product (Products)
Main product table.

| Column | Type | Notes |
|--------|------|-------|
| product_id | INT | Primary key |
| item_number | VARCHAR | SKU/item number |
| product | VARCHAR | Product name |
| product_desc | TEXT | Description |
| supplier_id | INT | FK to P_supplier |
| user_id | INT | FK to U_user (owner) |
| is_custom | CHAR(1) | 'Y' or 'N' |
| active | INT | 1=enabled, 0=disabled |
| decoration_id | INT | FK to P_decoration |
| production_time_id | INT | FK to P_production_time |
| price_code_id | INT | FK to P_price_code |
| price_setup | DECIMAL | Setup charge |
| price_setup_code | VARCHAR | Setup price code |
| logo_id | INT | FK to P_logo |
| has_upcharge | CHAR(1) | 'Y' or 'N' |
| date_created | DATETIME | |
| date_modified | DATETIME | |
| date_checked | DATETIME | |

### P_supplier (Suppliers)
| Column | Type | Notes |
|--------|------|-------|
| supplier_id | INT | Primary key |
| supplier | VARCHAR | Supplier name |

### P_price_rel (Pricing)
Quantity-based pricing.

| Column | Type | Notes |
|--------|------|-------|
| product_id | INT | FK to P_product |
| quantity | INT | Minimum quantity |
| price | DECIMAL | Unit price at quantity |

### P_price_code (Price Codes)
| Column | Type | Notes |
|--------|------|-------|
| price_code_id | INT | Primary key |
| price_code | VARCHAR | e.g., 'R', 'P', 'C' |

### P_decoration (Decoration Info)
| Column | Type | Notes |
|--------|------|-------|
| decoration_id | INT | Primary key |
| decoration | VARCHAR | Description |

### P_production_time (Production Times)
| Column | Type | Notes |
|--------|------|-------|
| production_time_id | INT | Primary key |
| production_time | VARCHAR | e.g., "5-7 working days" |

### P_logo (Product Logos/Images)
| Column | Type | Notes |
|--------|------|-------|
| logo_id | INT | Primary key |
| logo_scale | FLOAT | Image scale |
| logo_rotate | INT | Rotation degrees |
| coord_x | INT | X position |
| coord_y | INT | Y position |
| logo_style | VARCHAR | Style info |
| is_penlogo | CHAR(1) | 'Y' or 'N' |

### S_snapshot (Store Snapshots)
Links products to stores.

| Column | Type | Notes |
|--------|------|-------|
| snapshot_id | INT | Store ID |
| product_id | INT | FK to P_product |

### S_hotitem (Hot Items)
Featured products.

| Column | Type | Notes |
|--------|------|-------|
| hotitem_id | INT | |
| product_id | INT | FK to P_product |

### U_user (Users)
| Column | Type | Notes |
|--------|------|-------|
| user_id | INT | Primary key |
| name_first | VARCHAR | |
| name_last | VARCHAR | |

## Key Queries

### Check if product exists
```sql
SELECT product_id, item_number
FROM P_product
WHERE item_number = 'SKU123'
  AND supplier_id = 1
  AND user_id = 123
```

### Get product with full details
```sql
SELECT p.*, d.decoration, pt.production_time, pc.price_code, s.supplier
FROM P_product p
JOIN P_supplier s ON p.supplier_id = s.supplier_id
LEFT JOIN P_decoration d ON d.decoration_id = p.decoration_id
LEFT JOIN P_production_time pt ON pt.production_time_id = p.production_time_id
LEFT JOIN P_price_code pc ON pc.price_code_id = p.price_code_id
WHERE product_id = 123
```

### Enable/disable product
```sql
UPDATE P_product SET active = 1 WHERE product_id = 123  -- enable
UPDATE P_product SET active = 0 WHERE product_id = 123  -- disable
```

### Update modified date
```sql
UPDATE P_product SET date_modified = NOW() WHERE product_id = 123
```

## Import File Format (Excel)

Required columns for bulk import via `/products/import`:

| Column | Required | Notes |
|--------|----------|-------|
| item_number | Yes | SKU |
| product | Yes | Name |
| product_desc | Yes | Description |
| production_time | Yes | e.g., "5 - 7 working days" |
| included_decoration | Yes | Included decoration description |
| supplier_id | Yes | Must exist in P_supplier |
| user_id | Yes | Owner user ID |
| image_name | Yes | URL to download image (must be .jpg/.jpeg) |
| categories | Yes | Comma-separated, use "::" for hierarchy |
| price_1 through price_6 | Optional | Unit prices |
| price_quantity_1 through price_quantity_6 | Optional | Quantities for prices |
| price_code_1 through price_code_6 | Optional | Price codes |
| setup_charge | Optional | Setup fee |
| setup_price_code | Optional | |
| colors | Optional | Comma-separated |
| sizes | Optional | Comma-separated |
| sizeupcharges | Optional | Format: "Size:Price,Size:Price" |
| addcost | Optional | Additional costs |
| addcostprice | Optional | |
| addcostpricecode | Optional | |
| decoration | Optional | Decoration methods |
| imprint_location | Optional | |

## API Endpoints (Admin Panel)

### Login
```
POST /ae_scripts/login.php
Content-Type: application/x-www-form-urlencoded

username=xxx&password=xxx
```

### Import Products (Bulk)
```
POST /products/import
Content-Type: multipart/form-data

Upload Excel file with columns above
```

### Save Single Product
```
POST /ae_scripts/products/save_product.php
```

### Update Product Status (Enable/Disable)
```
POST /ae_scripts/products/status_product.php

product_id=123&cat_1_2=Y  # Enable in category
product_id=123&cat_1_2=N  # Disable in category
```

### Delete Product
```
POST /ae_scripts/products/delete_product.php

product_id=123
```
