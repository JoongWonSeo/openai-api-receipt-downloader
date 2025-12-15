# OpenAI Billing Downloader

Usage:

Go to [OpenAI Billing History](https://platform.openai.com/settings/organization/billing/history) and save the page as `billing.html`.

Then install the dependencies and run the script:

```bash
uv sync
uv run playwright install
```

```bash
uv run download_openai_receipts.py --html billing.html --out receipts
```

This will download the receipts to the `receipts` directory, starting from the most recent invoice.

The script automatically skips already downloaded invoices. By default, it stops as soon as it encounters a duplicate (early stop). To continue processing and fill any "holes" in your downloads, use `--no-early-stop`:

```bash
uv run download_openai_receipts.py --html billing.html --out receipts --no-early-stop
```
