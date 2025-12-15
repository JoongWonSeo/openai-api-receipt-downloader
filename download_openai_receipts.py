import argparse
import re
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

# Heuristic: these texts show up on Stripe invoice pages
DOWNLOAD_TEXTS = [
    "Download receipt",
    "Download invoice",
    "Download PDF",
    "Download",
]


def extract_invoice_links(html: str):
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.select("a[href]"):
        href = a["href"]
        if href.startswith("https://invoice.stripe.com/i/"):
            links.append(href)
    # de-dup while preserving order
    seen = set()
    unique = []
    for u in links:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


def extract_invoice_info(page_html: str):
    """Extract invoice number and payment date from the invoice page HTML."""
    soup = BeautifulSoup(page_html, "html.parser")

    invoice_number = None
    payment_date = None

    # Find the InvoiceDetails-table
    table = soup.find("table", class_="InvoiceDetails-table")
    if table:
        rows = table.find_all("tr", class_="LabeledTableRow")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)

                if label == "Invoice number":
                    invoice_number = value
                elif label == "Payment date":
                    payment_date = value

    # Format the date to YYYY-MM-DD format
    formatted_date = None
    if payment_date:
        try:
            # Parse date like "October 30, 2025"
            date_obj = datetime.strptime(payment_date, "%B %d, %Y")
            formatted_date = date_obj.strftime("%Y-%m-%d")
        except ValueError:
            # If parsing fails, use original date with spaces replaced
            formatted_date = payment_date.replace(" ", "-")

    return invoice_number, formatted_date


def main(html_file: Path, out_dir: Path, headless: bool, early_stop: bool):
    html = html_file.read_text(encoding="utf-8")
    urls = extract_invoice_links(html)
    if not urls:
        print("No Stripe invoice links found in the provided HTML.")
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Found {len(urls)} invoice links. Saving to: {out_dir.resolve()}")
    if early_stop:
        print("Early stop enabled: will exit on first duplicate.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        for i, url in enumerate(urls, start=1):
            print(f"[{i}/{len(urls)}] {url}")
            page.goto(url, wait_until="domcontentloaded")

            # Wait for JavaScript to render the invoice content
            page.wait_for_timeout(5000)

            # Extract invoice number and payment date from the page
            page_html = page.content()
            invoice_number, payment_date = extract_invoice_info(page_html)

            # Check if file already exists (if we have invoice info)
            if invoice_number and payment_date:
                filename = f"{payment_date}-{invoice_number}.pdf"
                dest_path = out_dir / filename
                if dest_path.exists():
                    if early_stop:
                        print(f"  → already exists: {filename} (stopping)")
                        break
                    else:
                        print(f"  → already exists: {filename} (skipping)")
                        continue

            # Try multiple possible button texts
            clicked = False
            for label in DOWNLOAD_TEXTS:
                try:
                    with page.expect_download(timeout=15000) as dl_info:
                        # Try button, link, or any element with the text
                        # 1) by role (button)
                        page.get_by_role(
                            "button", name=re.compile(label, re.IGNORECASE)
                        ).click(timeout=2000)
                        clicked = True
                    download = dl_info.value
                except PWTimeout:
                    # Try a generic text locator next
                    try:
                        with page.expect_download(timeout=15000) as dl_info:
                            page.get_by_text(re.compile(label, re.IGNORECASE)).click(
                                timeout=2000
                            )
                            clicked = True
                        download = dl_info.value
                    except PWTimeout:
                        continue

                if clicked:
                    # Use extracted invoice number and date for filename
                    if invoice_number and payment_date:
                        filename = f"{payment_date}-{invoice_number}.pdf"
                    else:
                        # Fallback to suggested filename or default
                        filename = download.suggested_filename or f"invoice_{i}.pdf"

                    dest_path = out_dir / filename
                    download.save_as(str(dest_path))
                    print(f"  → saved: {dest_path.name}")
                    break

            if not clicked:
                print("  ! Could not find a download button on this page (skipped).")

            # Be polite and avoid hammering Stripe
            page.wait_for_timeout(400)

        context.close()
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download Stripe invoice receipts from an OpenAI billing HTML page."
    )
    parser.add_argument(
        "--html", required=True, help="Path to the saved billing history HTML file."
    )
    parser.add_argument(
        "--out", default="receipts", help="Output directory for downloaded PDFs."
    )
    parser.add_argument(
        "--headed", action="store_true", help="Run with a visible browser window."
    )
    parser.add_argument(
        "--no-early-stop",
        action="store_true",
        help="Don't stop on first duplicate; skip and continue (useful for filling holes).",
    )
    args = parser.parse_args()

    main(
        Path(args.html),
        Path(args.out),
        headless=not args.headed,
        early_stop=not args.no_early_stop,
    )
