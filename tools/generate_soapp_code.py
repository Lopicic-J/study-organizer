#!/usr/bin/env python3
"""
Generate SOAPP license codes for Semetra Desktop Pro.
Usage:
    python tools/generate_soapp_code.py                    # generate 1 code
    python tools/generate_soapp_code.py --count 5          # generate 5 codes
    python tools/generate_soapp_code.py --insert            # generate + insert into Supabase
"""
import hashlib
import hmac
import os
import secrets
import argparse

HMAC_SECRET = os.getenv("SOAPP_HMAC_SECRET", "Semetra_Pro_2025_xK9mP3vQrZ")

def generate_soapp_code() -> str:
    """Generate a SOAPP-XXXXXX-YY code with HMAC checksum."""
    body = secrets.token_hex(3).upper()  # 6 hex chars
    mac = hmac.new(HMAC_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()[:2].upper()
    return f"SOAPP-{body}-{mac}"

def main():
    parser = argparse.ArgumentParser(description="Generate SOAPP license codes")
    parser.add_argument("--count", type=int, default=1, help="Number of codes to generate")
    parser.add_argument("--insert", action="store_true", help="Insert into Supabase license_codes table")
    parser.add_argument("--email", type=str, default="", help="Customer email (for --insert)")
    args = parser.parse_args()

    codes = [generate_soapp_code() for _ in range(args.count)]

    for code in codes:
        print(code)

    if args.insert:
        try:
            from supabase import create_client
            url = os.getenv("SOAPP_SB_URL", "https://glnbdloeffeylfmzviis.supabase.co")
            key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
            if not key:
                print("\n⚠️  SUPABASE_SERVICE_ROLE_KEY not set — cannot insert.")
                print("   Set it as environment variable or insert manually:")
                for code in codes:
                    print(f"   INSERT INTO license_codes (code, used, customer_email) VALUES ('{code}', false, '{args.email}');")
                return

            client = create_client(url, key)
            for code in codes:
                client.table("license_codes").insert({
                    "code": code,
                    "used": False,
                    "customer_email": args.email or None,
                    "plan": "lifetime",
                }).execute()
            print(f"\n✅ {len(codes)} Code(s) in Supabase eingefügt.")
        except ImportError:
            print("\n⚠️  supabase-py not installed. Insert manually:")
            for code in codes:
                print(f"   INSERT INTO license_codes (code, used, customer_email) VALUES ('{code}', false, '{args.email}');")

if __name__ == "__main__":
    main()
