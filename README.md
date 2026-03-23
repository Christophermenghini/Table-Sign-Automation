# Table-Sign Automation

This project automates the daily creation and updating of table signs using Google services.

The script retrieves event data from Google Calendar, creates a new document from a Google Docs template, replaces placeholders with the correct event names and times, and removes the previous day's document to keep the workflow clean and up to date.

## Overview

Manually updating table signs every day is repetitive and time-consuming. This project streamlines that process by generating updated signs automatically from scheduled calendar events.

It is especially useful for environments where signs need to reflect daily reservations, meetings, or scheduled use of spaces.

## Features

- Pulls event information from Google Calendar
- Copies a Google Docs template for the current day
- Replaces placeholders with event titles and times
- Helps keep signage accurate and consistent
- Removes outdated files from the previous day
- Reduces manual work and repetitive formatting tasks

## How It Works

1. The script connects to Google Calendar and reads the scheduled events for the target date.
2. It creates a copy of a predefined Google Docs table-sign template.
3. It fills the template with the appropriate event names and time ranges.
4. It saves the updated document for use that day.
5. It deletes the previous day's sign document to avoid clutter.

## Tech Stack

- Python
- Google Calendar API
- Google Docs API
- Google Drive API
- OAuth 2.0 authentication

## Use Case

This project was built to automate the creation of daily table signs for a shared space or cafe-style environment where event schedules change regularly.

Instead of manually editing the same document each day, the script handles the process automatically using calendar data as the source of truth.

## Project Structure
├── credentials.json
├── token.json
├── README.md
└── examples/
