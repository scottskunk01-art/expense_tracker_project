import json
import os
import base64
import secrets
import string
import getpass
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

VAULT_FILE = "vault.enc"
VERIFY_STR = b"vault-ok"


# ─────────────────────────────────────────────
# Step 4: Derive a Fernet key from master password + salt
# ─────────────────────────────────────────────
def derive_key(master_password: str, salt: bytes) -> Fernet:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480_000,       # high iteration count = slow to brute-force
    )
    key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
    return Fernet(key)


# ─────────────────────────────────────────────
# Step 5: Create a brand-new vault file
# ─────────────────────────────────────────────
def create_vault(master_password: str):
    salt = os.urandom(16)                          # fresh random salt
    fernet = derive_key(master_password, salt)

    verify_token = fernet.encrypt(VERIFY_STR)      # encrypted "vault-ok"
    empty_entries = fernet.encrypt(json.dumps({}).encode())

    vault_data = {
        "salt":    base64.b64encode(salt).decode(),
        "verify":  verify_token.decode(),
        "entries": empty_entries.decode(),
    }

    with open(VAULT_FILE, "w") as f:
        json.dump(vault_data, f)

    print("  Vault created successfully.")


# ─────────────────────────────────────────────
# Step 6: Unlock an existing vault
# ─────────────────────────────────────────────
def unlock_vault(master_password: str):
    with open(VAULT_FILE, "r") as f:
        vault_data = json.load(f)

    salt   = base64.b64decode(vault_data["salt"])
    fernet = derive_key(master_password, salt)

    # Verify the master password is correct
    try:
        decrypted = fernet.decrypt(vault_data["verify"].encode())
        if decrypted != VERIFY_STR:
            raise ValueError("Vault verification string mismatch.")
    except InvalidToken:
        raise ValueError("Incorrect master password.")

    # Decrypt the entries blob
    entries_json = fernet.decrypt(vault_data["entries"].encode())
    entries      = json.loads(entries_json)

    return fernet, entries, vault_data


# ─────────────────────────────────────────────
# Step 7: Save updated entries back to the vault
# ─────────────────────────────────────────────
def save_vault(fernet: Fernet, entries: dict, vault_data: dict):
    vault_data["entries"] = fernet.encrypt(
        json.dumps(entries).encode()
    ).decode()

    with open(VAULT_FILE, "w") as f:
        json.dump(vault_data, f)


# ─────────────────────────────────────────────
# Step 8: Password generator
# ─────────────────────────────────────────────
def generate_password(
    length:    int  = 16,
    uppercase: bool = True,
    lowercase: bool = True,
    digits:    bool = True,
    symbols:   bool = True,
) -> str:
    if length < 4:
        raise ValueError("Password length must be at least 4.")

    pool = ""
    guaranteed = []

    if uppercase:
        pool += string.ascii_uppercase
        guaranteed.append(secrets.choice(string.ascii_uppercase))
    if lowercase:
        pool += string.ascii_lowercase
        guaranteed.append(secrets.choice(string.ascii_lowercase))
    if digits:
        pool += string.digits
        guaranteed.append(secrets.choice(string.digits))
    if symbols:
        pool += string.punctuation
        guaranteed.append(secrets.choice(string.punctuation))

    if not pool:
        raise ValueError("At least one character type must be selected.")

    # Fill the rest of the password randomly from the full pool
    remaining = [secrets.choice(pool) for _ in range(length - len(guaranteed))]
    password_list = guaranteed + remaining

    # Shuffle so guaranteed characters aren't always at the start
    secrets.SystemRandom().shuffle(password_list)

    return "".join(password_list)


# ─────────────────────────────────────────────
# Step 9: CRUD operations on the entries dict
# ─────────────────────────────────────────────
def add_entry(fernet, entries, vault_data):
    service  = input("  Service name (e.g. gmail, github): ").strip().lower()
    username = input("  Username / email: ").strip()

    choice = input("  Generate a password? (y/n): ").strip().lower()
    if choice == "y":
        try:
            length = int(input("  Password length (default 16): ").strip() or "16")
        except ValueError:
            length = 16
        password = generate_password(length=length)
        print(f"  Generated password: {password}")
    else:
        password = getpass.getpass("  Enter password: ")

    entries[service] = {"username": username, "password": password}
    save_vault(fernet, entries, vault_data)
    print(f"  Entry for '{service}' saved.")


def get_entry(entries):
    service = input("  Service name to look up: ").strip().lower()
    if service not in entries:
        print(f"  No entry found for '{service}'.")
        return
    e = entries[service]
    print(f"\n  Service  : {service}")
    print(f"  Username : {e['username']}")
    print(f"  Password : {e['password']}\n")


def list_entries(entries):
    if not entries:
        print("  No entries stored yet.")
        return
    print(f"\n  {'#':<4} {'Service':<20} {'Username'}")
    print("  " + "-" * 45)
    for i, (service, data) in enumerate(sorted(entries.items()), start=1):
        print(f"  {i:<4} {service:<20} {data['username']}")
    print()


def delete_entry(fernet, entries, vault_data):
    service = input("  Service name to delete: ").strip().lower()
    if service not in entries:
        print(f"  No entry found for '{service}'.")
        return
    confirm = input(f"  Delete '{service}'? This cannot be undone. (y/n): ").strip().lower()
    if confirm == "y":
        del entries[service]
        save_vault(fernet, entries, vault_data)
        print(f"  Entry for '{service}' deleted.")


def standalone_generator():
    """Generate a password without opening the vault."""
    try:
        length = int(input("  Length (default 16): ").strip() or "16")
    except ValueError:
        length = 16

    use_symbols = input("  Include symbols? (y/n, default y): ").strip().lower()
    symbols = use_symbols != "n"

    password = generate_password(length=length, symbols=symbols)
    print(f"\n  Generated: {password}\n")


# ─────────────────────────────────────────────
# Step 10: Main menu loop
# ─────────────────────────────────────────────
def main():
    print("  === Password Manager ===\n")

    # First run: no vault file exists yet
    if not os.path.exists(VAULT_FILE):
        print("  No vault found. Let's create one.")
        print("  Choose a strong master password — if you forget it, your data cannot be recovered.\n")
        while True:
            mp  = getpass.getpass("  Set master password: ")
            mp2 = getpass.getpass("  Confirm master password: ")
            if mp == mp2 and len(mp) >= 8:
                create_vault(mp)
                break
            elif mp != mp2:
                print("  Passwords do not match. Try again.")
            else:
                print("  Master password must be at least 8 characters.")

    # Unlock the vault
    attempts = 0
    fernet, entries, vault_data = None, None, None

    while attempts < 3:
        mp = getpass.getpass("\n  Enter master password: ")
        try:
            fernet, entries, vault_data = unlock_vault(mp)
            print("  Vault unlocked.\n")
            break
        except ValueError as e:
            attempts += 1
            remaining = 3 - attempts
            print(f"  {e} ({remaining} attempt(s) left)")

    if fernet is None:
        print("  Too many failed attempts. Exiting.")
        return

    # Main menu
    while True:
        print("  ─────────────────────────────")
        print("  1. Generate a password")
        print("  2. Add / update an entry")
        print("  3. Get a password")
        print("  4. List all services")
        print("  5. Delete an entry")
        print("  6. Lock & quit")
        print("  ─────────────────────────────")

        choice = input("  Choose (1-6): ").strip()

        if choice == "1":
            standalone_generator()
        elif choice == "2":
            add_entry(fernet, entries, vault_data)
        elif choice == "3":
            get_entry(entries)
        elif choice == "4":
            list_entries(entries)
        elif choice == "5":
            delete_entry(fernet, entries, vault_data)
        elif choice == "6":
            print("  Vault locked. Goodbye.")
            break
        else:
            print("  Invalid choice.")


if __name__ == "__main__":
    main()