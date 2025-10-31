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

This will download the receipts to the `receipts` directory, starting from the most recent invoice. Just cancel the script if you have all the receipts you need.
