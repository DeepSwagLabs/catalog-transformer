# catalog-transformer

Converts Sage-format supplier exports to Creative Merchandise legacy DB schema.

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/your-template)

## Quick Start

### Deploy to Railway

1. Fork this repo
2. Connect to Railway
3. Deploy
4. Use the API endpoints below

### Run Locally

```bash
pip install -r requirements.txt
python catalog_transformer.py input.xlsx output.xlsx --supplier illini
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Health check |
| `POST` | `/transform` | Transform supplier export → DB schema |
| `POST` | `/reconcile` | Transform + compare against existing DB |

### Transform a file

```bash
curl -X POST https://YOUR-APP.railway.app/transform \
  -F "file=@supplier_export.xlsx" \
  -F "supplier=illini" \
  -o transformed.xlsx
```

### Transform + Reconcile

```bash
curl -X POST https://YOUR-APP.railway.app/reconcile \
  -F "file=@new_supplier_export.xlsx" \
  -F "old_file=@current_db_export.xlsx" \
  -F "supplier=illini" \
  -o catalog_sync.zip
```

Returns ZIP containing:
- `{supplier}_transformed.xlsx` - Full catalog
- `{supplier}_ADDS.xlsx` - New products
- `{supplier}_UPDATES.xlsx` - Changed products  
- `{supplier}_DELETES.xlsx` - Removed products

## CLI Usage

```bash
# Basic transform
python catalog_transformer.py supplier.xlsx output.xlsx

# With supplier name
python catalog_transformer.py supplier.xlsx output.xlsx --supplier hit

# With reconciliation
python catalog_transformer.py new.xlsx output.xlsx --old current_db.xlsx
```

## What It Does

Transforms 116-column Sage exports → 42-column legacy DB schema:

- `ProdTimeLo` + `ProdTimeHi` → `"3 to 5 Working Days"`
- `PrCode "CCCCC"` → `price_code_1` through `price_code_6`
- `PriceIncludeClr` + `PriceIncludeLoc` + `DecorationMethod` → `included_decoration`
- Zeros in qty/price columns → blank/NaN
- Item number normalization (`3020-10 X 8` → `3020-10 x 8`)

## Files

```
├── catalog_transformer.py   # Main app (CLI + HTTP)
├── requirements.txt         # Python dependencies
├── Dockerfile              # Container build
├── railway.json            # Railway config
└── README.md
```
