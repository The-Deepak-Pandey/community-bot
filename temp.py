import logging
import threading
import requests
from flask import Flask, request, redirect
from telegram import Update, Bot, ChatPermissions
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Replace with your actual bot token and server details
BOT_TOKEN = "7795003413:AAG2O5kha7zXxWyr-5jw9ycpmBo5SbWQMMA"
CAS_LOGIN_URL = "https://login.iiit.ac.in/cas/login"
CAS_VALIDATE_URL = "https://login.iiit.ac.in/cas/validate"
SERVER_URL = "http://127.0.0.1:5000"  # Flask server URL
ALLOWED_GROUPS = [-1002326984314]     # Replace with your actual group chat IDs

# Initialize Flask app
app = Flask(__name__)

# In-memory store for verified users
verified_users = set()

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)

# --- Telegram Bot Handlers (Async) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Sends a welcome message along with a CAS verification link.
    """
    user_id = update.message.from_user.id
    verification_link = f"{SERVER_URL}/verify?user_id={user_id}"
    await update.message.reply_text(
        f"Welcome! To join the group, you must verify yourself via IIIT Hyderabad CAS.\n"
        f"Click this link to verify: [Verify Now]({verification_link})",
        parse_mode="Markdown"
    )

async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Restricts new members in allowed groups until they verify via CAS.
    """
    chat_id = update.effective_chat.id

    # Only enforce verification in allowed groups
    if chat_id not in ALLOWED_GROUPS:
        return

    new_members = update.message.new_chat_members
    for member in new_members:
        if member.id in verified_users:
            continue  # Already verified; no need to restrict again.

        # Restrict new member from sending messages until verified.
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=member.id,
            permissions=ChatPermissions(can_send_messages=False)
        )

        verification_link = f"{SERVER_URL}/verify?user_id={member.id}"
        try:
            await context.bot.send_message(
                chat_id=member.id,
                text=(
                    f"Welcome! Please verify yourself via IIIT Hyderabad CAS.\n"
                    f"Click here to verify: [Verify Now]({verification_link})"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Error sending verification message to {member.id}: {e}")

# --- Flask Routes ---

@app.route("/verify", methods=["GET"])
def verify():
    """
    Redirects the user to the CAS login page.
    """
    user_id = request.args.get("user_id")
    if not user_id:
        return "Invalid request", 400

    # Build CAS login URL with the callback service parameter.
    cas_redirect_url = f"{CAS_LOGIN_URL}?service={SERVER_URL}/callback?user_id={user_id}"
    return redirect(cas_redirect_url)

@app.route("/callback", methods=["GET"])
def callback():
    """
    Handles the CAS login response and validates the user.
    """
    user_id = request.args.get("user_id")
    ticket = request.args.get("ticket")
    if not user_id or not ticket:
        return "Invalid verification attempt", 400

    # Validate the CAS ticket.
    validate_url = f"{CAS_VALIDATE_URL}?ticket={ticket}&service={SERVER_URL}/callback"
    response = requests.get(validate_url)

    # If validation is successful, CAS typically responds with a string starting with "yes"
    if "yes" in response.text.lower():
        verified_users.add(int(user_id))

        # Notify the user via Telegram that verification was successful.
        bot = Bot(token=BOT_TOKEN)
        bot.send_message(
            chat_id=int(user_id),
            text="✅ You have been verified! You can now participate in the group."
        )
        return "Verification successful! You can now join the group.", 200
    else:
        return "Verification failed. Please try again.", 403

def run_flask():
    """
    Runs the Flask web server.
    """
    app.run(port=5000)

def main():
    # Run the Flask server in a separate thread.
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # Build the Telegram application (v20+ uses Application.builder())
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers for the /start command and new chat member events.
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member))

    # Run the bot using long polling.
    application.run_polling()

if __name__ == "__main__":
    main()
