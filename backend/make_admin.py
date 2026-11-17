"""ينشئ حساب المدير Berra (أو يحدّث كلمة سره). يُشغَّل محليًا فقط. كلمة السر لا تُكتب في أي ملف."""
import getpass
import sys

import accounts

EMAIL = "berramouhcine13@gmail.com"
NAME = "Berra"


def main():
    print("Admin account:", NAME, EMAIL)
    p1 = getpass.getpass("New password (min 10 chars): ")
    p2 = getpass.getpass("Repeat password: ")
    if p1 != p2:
        print("Passwords do not match.")
        return 1
    try:
        uid = accounts.make_admin(EMAIL, p1, NAME)
    except ValueError:
        print("Invalid input: password must be at least 10 characters.")
        return 1
    print("Done. Admin user id:", uid, "- log in with the email and this password.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
