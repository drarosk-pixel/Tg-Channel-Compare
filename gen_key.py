"""Print a fresh ENCRYPTION_KEY for the bot. Run: python gen_key.py"""

from cryptography.fernet import Fernet

if __name__ == "__main__":
    print("ENCRYPTION_KEY=" + Fernet.generate_key().decode())
    print("\nPut this line in your .env (or hosting env vars). Keep it secret and do NOT change")
    print("it later, or all stored logins become unreadable and users must /login again.")
