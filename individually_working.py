import asyncio
import sys
import logging
import random
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

BOT_TOKEN = "7795003413:AAG2O5kha7zXxWyr-5jw9ycpmBo5SbWQMMA"
# List of group IDs where the bot should enforce verification
ALLOWED_GROUPS = [-1002467254560, -1002326984314, -1002318229714, -1002306910120, -1002417438112, -1002313480533, -1002343574565, -1002259052372] 
EMAIL_ADDRESS = "peppzzonsbot@gmail.com"
EMAIL_PASSWORD = "mkmp bnkb qimf ejye"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
# ==========================

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# In-memory dictionaries:
# pending_verifications: maps user_id -> set of group_chat_ids where the user is pending verification
pending_verifications = {}
# email_verification: maps user_id -> dict with "state", "email", and "code"
email_verification = {}

def send_email(recipient_email: str, subject: str, body: str):
    """
    Sends an email using SMTP with a MIMEMultipart message.
    """
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.sendmail(EMAIL_ADDRESS, recipient_email, msg.as_string())
        logger.info(f"Sent verification email to {recipient_email}")
    except Exception as e:
        logger.error(f"Error sending email: {e}")

async def new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles new members joining a group.
    If the group is in ALLOWED_GROUPS, restrict the new member from sending messages,
    add the group id to the user's pending set, and send a welcome message with a verify button.
    """
    chat_id = update.effective_chat.id
    if chat_id not in ALLOWED_GROUPS:
        return

    logger.info(f"New member in group {chat_id}: {update.message.new_chat_members}")

    for member in update.message.new_chat_members:
        if member.is_bot:
            continue

        try:
            await context.bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=member.id,
                permissions=ChatPermissions(can_send_messages=False)
            )
            # Add group id to pending_verifications set for this user
            if member.id in pending_verifications:
                pending_verifications[member.id].add(chat_id)
            else:
                pending_verifications[member.id] = {chat_id}

            # Create an inline button linking to the bot's DM with the parameter /start verify
            button = InlineKeyboardButton(
                "Verify",
                url=f"https://t.me/{context.bot.username}?start=verify"
            )
            keyboard = InlineKeyboardMarkup([[button]])
            await update.message.reply_text(
                f"Welcome {member.first_name}! Click below to verify.",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Restriction error for user {member.id}: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the /start command in the bot's DM.
    When used with the argument "verify", it initiates the email verification process.
    """
    user_id = update.message.from_user.id

    if user_id not in pending_verifications:
        await update.message.reply_text("No pending verification found. You might already be verified.")
        return

    if context.args and context.args[0] == "verify":
        # Begin the verification process by asking for the user's IIIT email address
        email_verification[user_id] = {"state": "awaiting_email"}
        await update.message.reply_text("Please enter your IIIT email (e.g., yourname@students.iiit.ac.in or @research.iiit.ac.in):")
    else:
        await update.message.reply_text("To verify, click the verify button in your group.")

async def handle_verification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Processes messages in the bot's DM for the verification process.
    Depending on the user's current state, it either:
      - Accepts the email and sends a verification code, or
      - Checks the entered code.
    """
    user_id = update.message.from_user.id
    if user_id not in email_verification:
        await update.message.reply_text("Start verification with /start verify.")
        return

    state = email_verification[user_id]["state"]
    text = update.message.text.strip()

    if state == "awaiting_email":
        # Check for a valid IIIT email domain (here, simply checking if it ends with "iiit.ac.in")
        if text.endswith("iiit.ac.in"):
            code = str(random.randint(1000, 9999))
            email_verification[user_id].update({
                "state": "awaiting_code",
                "email": text,
                "code": code
            })

            # Send the verification code by email asynchronously
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                send_email,
                text,
                "Hello from the IIIT Community!",
                f"Your verification code is {code}"
            )
            await update.message.reply_text("A verification code has been sent to your email. Please enter the code here:")
        else:
            await update.message.reply_text("Invalid email domain. Please ensure your email ends with 'iiit.ac.in'.")
    elif state == "awaiting_code":
        expected_code = email_verification[user_id]["code"]
        logger.info(f"User {user_id} entered code: '{text}' (expected: '{expected_code}')")
        if text == expected_code:
            # Retrieve all group ids where the user is pending verification
            group_ids = pending_verifications.get(user_id, set())
            if group_ids:
                errors = []
                for group_id in group_ids:
                    try:
                        await context.bot.restrict_chat_member(
                            chat_id=group_id,
                            user_id=user_id,
                            permissions=ChatPermissions(
                                can_send_messages=True,
                            )
                        )
                        # Notify each group that the user has been verified
                        await context.bot.send_message(
                            chat_id=group_id,
                            text=f"{update.effective_user.first_name} has been verified!"
                        )
                    except Exception as e:
                        errors.append(str(e))
                        logger.error(f"Error unrestricting user {user_id} in group {group_id}: {e}")
                if errors:
                    await update.message.reply_text("Some groups could not be updated. Please contact the group admins.")
                else:
                    await update.message.reply_text("✅ Verification successful! You are now verified in all your groups. Please return to the groups.")
            else:
                await update.message.reply_text("No pending group data found. Please contact the group admins.")
            # Clean up verification data
            pending_verifications.pop(user_id, None)
            email_verification.pop(user_id, None)
        else:
            await update.message.reply_text("Incorrect verification code. Please try again.")

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Handler for new chat members in groups
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member))
    # Handler for the /start command (for DM verification)
    application.add_handler(CommandHandler("start", start))
    # Handler for DM text messages to process email and code
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, handle_verification))

    application.run_polling()

if __name__ == "__main__":
    main()
