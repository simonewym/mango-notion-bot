import os
import aiohttp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime
from openai import OpenAI

# Check if the code is running on Heroku
if 'DYNO' in os.environ:
    # on Heroku, no need to load the .env file
    print("Running on Heroku. Skipping .env file.")
else:
    from dotenv import load_dotenv
    load_dotenv('var.env')  # Load environment variables from .env file for local development

client = OpenAI()

# Initialize environment variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
NOTION_TOKEN = os.getenv('NOTION_TOKEN')
NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Notion API endpoint and headers
NOTION_API_ENDPOINT = "https://api.notion.com/v1/pages"
NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2021-08-16"
}

# List of subjects with emojis
SUBJECTS = ["💸 Economy", "🍑 Sexuality", "🗳 Politics", "📺 Media", "🧠 Mental Health", "🧬 Genetics", "📱 Technology", "💬 Other"]

async def start(update, context):
    await update.message.reply_text('Enter the URL of the resource.')

def is_research_paper(url: str, content: str, soup: BeautifulSoup) -> bool:
    # Check URL for academic domains or keywords
    academic_domains = ['.edu', '.ac.uk', 'arxiv.org', 'researchgate.net', 'scholar.google.com', 'ncbi.nlm.nih.gov', 'sciencedirect.com']
    if any(domain in url for domain in academic_domains):
        return True

    # Check for PDF links that often indicate research papers
    if url.lower().endswith('.pdf'):
        return True

    # Check for common research paper sections in the content
    research_keywords = ['abstract', 'introduction', 'methodology', 'results', 'conclusion', 'references', 'doi:']
    if any(keyword in content.lower() for keyword in research_keywords):
        return True

    # Check for meta tags that might indicate a research paper
    if soup.find('meta', {'name': 'citation_title'}) or soup.find('meta', {'name': 'citation_author'}):
        return True

    return False

# Helper - Format properties object passed to Notion
def format_notion_properties(entry):
    properties = {
        "Link": {
            "url": entry['Link']
        },
        "Name": {
            "title": [
                {
                    "text": {
                        "content": entry['Name']
                    }
                }
            ]
        },
        "Subject": {
            "select": {
                "name": entry['Subject']
            }
        },
        "Type": {
            "select": {
                "name": entry['Type']
            }
        },
        "Tags": {
            "multi_select": [
                {"name": tag} for tag in entry['Tags']
            ]
        },
        "Added on": {
            "date": {
                "start": datetime.now().isoformat()
            }
        }
    }
    return properties

# Helper - Returns Type of resource
def determine_resource_type(url: str, content: str, soup: BeautifulSoup) -> str:
    domain = urlparse(url).netloc
    if any(site in domain for site in ['youtube.com', 'youtu.be', 'vimeo.com']):
        return 'Video'
    elif any(site in domain for site in ['twitter.com', 'x.com', 'linkedin.com', 'facebook.com', 'instagram.com', 'threads.net']):
        return 'Social Media Post'
    elif 'amazon.com' in domain and '/dp/' in url:
        return 'Book'
    elif 'goodreads.com' in domain and '/dp/' in url:
        return 'Book'
    elif soup.find('meta', property='og:type', content='article') or len(soup.find_all('article')) > 0:
        return 'Article'
    elif soup.find('meta', property='og:type', content='book'):
        return 'Book'
    elif is_research_paper(url, content, soup):
        return 'Research'
    return 'Other'

# Helper - Reach Gpt-4 and returns Subject and Tags of resource
def determine_subject_and_tags(content: str) -> tuple:
    print("Reaching GPT-4o...")
    prompt = f"""Analyze the following content and determine
    1. The most appropriate subject from this list: {', '.join(SUBJECTS)}
    2. Five relevant tags (e.g. Finance) for the content that helps to categorise them in a knowledge database. The tags preferably describe higher level, abstract concepts rather than specific person, or object mentioned.Tag and subject should not repeat.

    Content: {content[:1000]}  # Limiting to 1000 characters for API efficiency

    Please respond in the following format:
    Subject: [chosen subject]
    Tags: [Tag1], [Tag2], [Tag3], [Tag4], [Tag5]
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Specify the correct model
            messages=[{"role": "system", "content": "Analyze the text and provide the required information."},
                      {"role": "user", "content": prompt}],
            max_tokens=150,  # Adjust based on your needs
            temperature=0.7,  # Adjust how creative you want the output to be
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        
        openai_response = response.choices[0].message.content.strip()
        print(openai_response)
        subject_line = next((line for line in openai_response.split('\n') if line.startswith('Subject:')), None)
        tags_line = next((line for line in openai_response.split('\n') if line.startswith('Tags:')), None)
        
        if not subject_line or not tags_line:
            raise ValueError("The response did not contain a valid 'Subject:' or 'Tags:' line.")
        
        subject = subject_line.split(': ')[1].strip()
        tags = [tag.strip() for tag in tags_line.split(': ')[1].split(',')]
        
        return subject, tags

    except Exception as e:
        print(f"An error occurred: {e}")
        return None, None

# Returns Title, Content, Type, Tags, Subject of resource
async def extract_metadata(url: str) -> dict:
    request_headers = {
        'referer': 'https://www.scrapingcourse.com/ecommerce/',
        'accept-language': 'en-GB,en;q=0.9,de-DE;q=0.8,de;q=0.7,yue-HK;q=0.6,yue;q=0.5,en-US;q=0.4,zh-TW;q=0.3,zh;q=0.2',
        'content-type': 'application/json',
        'accept-encoding': 'gzip, deflate, br, zstd',
        'sec-ch-device-memory': '8',
        'sec-ch-ua': '"Not)A;Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
        'sec-ch-ua-platform': "Android",
        'sec-ch-viewport-width': '792',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=request_headers) as response:
                if response.status == 403:
                    print("Blocked by the website")
                    return {'title': "Blocked", 'content': "", 'type': "Blocked", 'tags': [], 'subject': "💬 Blocked"}
                html = await response.text()

        soup = BeautifulSoup(html, 'html.parser')
        formatted_date = datetime.now().strftime("%d/%m/%Y")
        title = soup.title.string if soup.title else "Title" + formatted_date
        content = ' '.join([p.text for p in soup.find_all('p')])

        subject, tags = determine_subject_and_tags(content)
        resource_type = determine_resource_type(url, content, soup)

        return {
            'title': title.strip(),
            'content': content,
            'type': resource_type,
            'tags': tags,
            'subject': subject
        }
    except Exception as e:
        print(f"Error extracting metadata: {e}")
        return {'title': "Error extracting metadata", 'content': "", 'type': "Other", 'tags': [], 'subject': "💬 Other"}

# Telegram response when user provided a non-URL
async def handle_non_url(update, context):
    await update.message.reply_text("That doesn't look right. Please send a valid URL.")

# Chat flow in Telegram after URL is received
async def handle_url(update, context):
    url = update.message.text
    try:
        metadata = await extract_metadata(url)
        entry = {
            'Name': metadata['title'],
            'Subject': metadata['subject'],
            'Type': metadata['type'],
            'Tags': metadata['tags'],
            'Link': url
        }

        # Debug logging
        print(f"Debug: Saving pending_entry: {entry}")
        context.user_data['pending_entry'] = entry
        print(f"Debug: User data after saving: {context.user_data}")

        # Create a preview message
        preview = "\n".join([f"{k}: {v}" for k, v in entry.items()])
        keyboard = [
            [InlineKeyboardButton('🟢 Confirm', callback_data='confirm'),
            InlineKeyboardButton('🔴 Cancel', callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"{preview}\n\n🧐 Send this to Notion?", reply_markup=reply_markup)

    except Exception as e:
        print(f"Error in handle_url: {e}")
        await update.message.reply_text("Hmm, something went wrong as I was parsing the URL. Please try again.")

# Chat flow after message preview is shown to user before sending to Notion
async def button_callback(update, context):
    query = update.callback_query
    await query.answer()
    
    try:
        if 'pending_entry' in context.user_data:
            entry = context.user_data['pending_entry']
            if query.data == 'confirm':
                await add_to_notion(update, entry)
                await query.edit_message_text(text="Sending source to Notion...🥭")
            elif query.data == 'cancel':
                await query.edit_message_text(text="Got it. Operation cancelled. 🥭")
            # Clear the pending entry after processing
            del context.user_data['pending_entry']
            print("Debug: pending_entry cleared after processing")
        else:
            print("Debug: pending_entry not found in user_data")
            print(f"Debug: user_data contents: {context.user_data}")
            await query.edit_message_text(text="Sorry, I don't have the entry data. Please try again.")
    
    except Exception as e:
        print(f"Error in button_callback: {e}")
        await query.edit_message_text(text="Oops, something went wrong. Please try again.")

    # Print debug information
    print(f"Debug: Callback query data: {query.data}")
    print(f"Debug: User data after callback: {context.user_data}")

# Send new resource object to Notion API
async def add_to_notion(update, entry: dict) -> None:
    data = {
        "parent": { "database_id": NOTION_DATABASE_ID },
        "properties": format_notion_properties(entry)
        }

    async with aiohttp.ClientSession() as session:
        async with session.post(NOTION_API_ENDPOINT, headers=NOTION_HEADERS, json=data) as response:
            if response.status != 200:
                error_text = await response.text()
                print(f"Error adding to Notion: {error_text}")
                reply_text = "Hmm, that didn't work. Please try again."
            else:
                reply_text = "New source successfully added to Notion."
                print("Successfully added to Notion")

    # Check if the update comes from a callback query
    if hasattr(update, 'callback_query'):
        await update.callback_query.message.reply_text(reply_text)
    elif hasattr(update, 'message'):
        await update.message.reply_text(reply_text)
    else:
        print("Update does not contain a message or callback query.")

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))

    # Message handler for URLs
    url_pattern = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(url_pattern), handle_url))

    # Generic message handler for non-URL text
    non_url_filter = ~filters.Regex(url_pattern)
    application.add_handler(MessageHandler(non_url_filter, handle_non_url))

    application.add_handler(CallbackQueryHandler(button_callback))
    application.run_polling()

if __name__ == '__main__':
    main()