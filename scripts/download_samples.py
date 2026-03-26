"""Download sample public financial PDFs for demo/testing."""

import urllib.request
import ssl
from pathlib import Path

SAMPLES = {
    "bank_statement_commerce.pdf": "https://www.commercebank.com/-/media/cb/pdf/personal/bank/statement_sample1.pdf",
    "utility_bill_sample.pdf": "https://www.crwwd.com/wp-content/uploads/bsk-pdf-manager/2019/09/Sample_Utility_Bill.pdf",
}

OUTPUT_DIR = Path("tests/fixtures")


def download_samples():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Allow unverified SSL for sample downloads
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for filename, url in SAMPLES.items():
        output_path = OUTPUT_DIR / filename
        if output_path.exists():
            print(f"  Already exists: {filename}")
            continue

        print(f"  Downloading: {filename}...")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "DocExtract/1.0"})
            with urllib.request.urlopen(req, context=ctx, timeout=30) as response:
                content = response.read()
                if content[:4] == b"%PDF":
                    output_path.write_bytes(content)
                    print(f"  Saved: {filename} ({len(content)} bytes)")
                else:
                    print(f"  Skipped: {filename} (not a valid PDF)")
        except Exception as e:
            print(f"  Failed: {filename} - {e}")

    print(f"\nSample PDFs saved to: {OUTPUT_DIR}")
    print("You can also manually add any PDF files to this directory for testing.")


if __name__ == "__main__":
    download_samples()
