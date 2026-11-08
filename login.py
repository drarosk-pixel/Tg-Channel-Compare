"""
One-time login with phone number + OTP (and 2FA password if enabled).

Run on your own computer:  python login.py
Telegram sends the OTP to your Telegram app (or SMS). The session is saved to
SESSION_NAME.session, and a SESSION_STRING is printed for hosting.
"""

import asyncio
import getpass

from telethon.sessions import StringSession

from config import PHONE, SESSION_NAME, make_client


async def main():
    client = make_client(use_string=False)
    await client.start(
        phone=lambda: PHONE or input("Phone number (with country code, e.g. +91...): ").strip(),
        code_callback=lambda: input("OTP code received on Telegram: ").strip(),
        password=lambda: getpass.getpass("2FA password (hidden): "),
    )
    me = await client.get_me()
    name = " ".join(filter(None, [me.first_name, me.last_name]))
    print(f"\nLogged in as {name} (@{me.username or '-'}, id {me.id})")
    print(f"Session saved: {SESSION_NAME}.session  (keep this file private)")

    if input("\nPrint SESSION_STRING for hosting? [y/N]: ").strip().lower() == "y":
        print("\nSESSION_STRING (secret! paste only into your hosting env variables):\n")
        print(StringSession.save(client.session))
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
