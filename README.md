# Notion Link Archiver Bot

This Telegram bot automates the process of saving links into a Notion database. It extracts and populates metadata from webpages using BeautifulSoup and enhances data entry by leveraging the capabilities of OpenAI's GPT-4.

## Features

- **Automatic Metadata Extraction**: Uses BeautifulSoup to scrape web content and populate metadata like Title, Content Type.
- **AI Generated Tagging, Categorie**: Utilises GPT-4 to generate suitable Tags for easy categorisation.
- **Seamless Integration with Notion**: Directly saves extracted data into a configured Notion table, matching the table's schema and add new page to database via Notion API.

## Prerequisites

Before you begin, ensure you meet the following requirements:
* Python 3.8 or higher installed.
* Access to a Telegram account to create a bot via BotFather.
* An OpenAI API key for using GPT-4.
* A Notion integration token and access to a Notion database.

## Setup

### Environment Variables

Create a `var.env` file in the root directory with the following variables:

```plaintext
TELEGRAM_TOKEN=<your_telegram_bot_token>
NOTION_TOKEN=<your_notion_integration_token>
NOTION_DATABASE_ID=<your_notion_database_id>
OPENAI_API_KEY=<your_openai_api_key>
```

### Usage

Once the bot is configured and running, send any URL to the Telegram bot. The bot will automatically fetch the URL, extract data, generate summaries with GPT-4, and populate your Notion database.