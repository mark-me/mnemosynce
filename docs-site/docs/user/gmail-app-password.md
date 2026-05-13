---
icon: lucide/mail
---

# Gmail app password

Mnemosynce sends backup reports via Gmail's SMTP server. Gmail does not allow
your regular Google account password to be used for this — you must generate a
dedicated **app password** instead. App passwords are 16-character strings that
give a single application access to your Gmail account without exposing your
main password.

!!! info "Why an app password?"
    Google blocks sign-in attempts from apps that use only a username and
    password, treating them as less secure. App passwords are the approved way
    to grant SMTP access to a specific application while keeping your main
    account credentials safe.

## Prerequisites

App passwords require **2-Step Verification** to be enabled on your Google
account. If you have not set it up yet, do that first:

1. Go to [myaccount.google.com](https://myaccount.google.com).
2. Click **Security** in the left sidebar.
3. Under *How you sign in to Google*, click **2-Step Verification**.
4. Follow the prompts to enable it.

Once 2-Step Verification is active, app passwords become available.

## Generating an app password

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
   You may be asked to sign in again.

2. In the **App name** field, enter a recognisable label such as `Mnemosynce`.

3. Click **Create**.

4. Google displays a 16-character password in a yellow box, formatted as four
   groups of four letters (e.g. `abcd efgh ijkl mnop`). **Copy it now** —
   Google will never show it again.

5. Click **Done**.

!!! warning "Store the password immediately"
    Once you close the confirmation dialog, the app password cannot be retrieved.
    If you lose it, delete it and generate a new one.

## Adding the password to Mnemosynce

The app password is supplied as an environment variable, never stored in
`backup_config.yml`.

**Docker Compose** — add it to your `.env` file:

```ini title=".env"
GMAIL_ADDRESS=your.account@gmail.com
GMAIL_PASSWORD=abcdefghijklmnop
```

Enter the password as a single 16-character string with no spaces.

**Docker run** — pass it directly:

```bash
docker run ... \
  -e GMAIL_ADDRESS=your.account@gmail.com \
  -e GMAIL_PASSWORD=abcdefghijklmnop \
  ghcr.io/mark-me/mnemosynce:latest
```

**File-based secret** (sops-nix or similar):

```bash
echo "abcdefghijklmnop" > /etc/mnemosynce/gmail-password
chmod 600 /etc/mnemosynce/gmail-password
export GMAIL_PASSWORD_FILE=/etc/mnemosynce/gmail-password
```

## Verifying the password

Once Mnemosynce is running, go to **Settings → Connections** and use the
**Email** test panel. Enter a recipient address and click **Send test email**.
A successful test confirms the app password is correct and SMTP access is
working.

If the test fails, check:

- The `GMAIL_ADDRESS` matches the Google account the app password belongs to.
- The password was copied without spaces.
- 2-Step Verification is still active on the account (disabling it invalidates
  all app passwords immediately).

## Revoking an app password

If you suspect the password has been compromised, or you no longer need
Mnemosynce to send email:

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
2. Find the **Mnemosynce** entry and click the trash icon next to it.
3. Generate a new one and update `GMAIL_PASSWORD` in your `.env` file if needed.
