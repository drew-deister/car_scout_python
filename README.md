# Car Scout - Python/Streamlit Version

A Python application built with FastAPI backend and Streamlit frontend for automated car buying conversations via SMS.

## Features

- SMS webhook handling via Mobile Text Alerts
- AI-powered car buying agent using OpenAI GPT-4o
- Automated conversation flow that collects car information and schedules visits
- Web scraping and data extraction from car listing URLs
- Thread and message management
- Car listings visualization with scatter plots
- Real-time conversation tracking
- Visit scheduling with availability checking

## Tech Stack

- **FastAPI** - Backend API framework
- **Streamlit** - Frontend framework
- **MongoDB** - Database (using pymongo)
- **OpenAI** - AI agent and data extraction
- **Mobile Text Alerts** - SMS integration
- **BeautifulSoup** - Web scraping
- **Plotly** - Data visualization
- **ngrok** - Public tunnel for webhooks

## Prerequisites

- **macOS** (script is optimized for Mac)
- Python 3.8 or higher
- MongoDB (local or cloud instance)
- OpenAI API key
- Mobile Text Alerts API key
- Homebrew (for automatic ngrok installation - will be installed automatically if missing)

## Quick Start

### Single Command Setup

Clone the repository and run:

```bash
./start.sh
```

This single command will:
1. ✅ Detect and use the correct Python/pip commands (python3/pip3 or python/pip)
2. ✅ Create `.env` file template if missing
3. ✅ Install all required dependencies
4. ✅ Automatically install ngrok via Homebrew (if needed)
5. ✅ Start the backend server (FastAPI)
6. ✅ Start the frontend (Streamlit)
7. ✅ Start ngrok tunnel
8. ✅ Display all URLs and webhook information

**That's it!** The application will be running and ready to receive SMS webhooks.

### First Time Setup

1. **Run the startup script** - it handles everything automatically:
```bash
./start.sh
```

The script will:
- ✅ Detect and use the correct Python/pip commands
- ✅ Create `.env` file template if missing (you'll be prompted to edit it)
- ✅ Install all Python dependencies
- ✅ Automatically install ngrok via Homebrew if needed
- ✅ Start backend, frontend, and ngrok
- ✅ Display all URLs and webhook information

2. **Edit `.env` file** with your credentials:
```bash
PORT=5001
MONGODB_URI=mongodb://localhost:27017/test
OPENAI_API_KEY=your_openai_api_key_here
MTA_API_KEY=your_mobile_text_alerts_api_key_here
MTA_AUTO_REPLY_TEMPLATE_ID=
MTA_WEBHOOK_SECRET=your_secret_key_here
MTA_ALERT_EMAIL=
```

3. **Configure Mobile Text Alerts webhook**:
   - Copy the ngrok URL displayed by the script
   - Set webhook URL to: `https://your-ngrok-url.ngrok.io/api/webhook/sms`

**Note:** If Homebrew is not installed, the script will prompt you. Install it from https://brew.sh or install ngrok manually.

## Application URLs

Once running, you'll have access to:

- **Frontend Dashboard**: http://localhost:8501
- **Backend API**: http://localhost:5001
- **API Health Check**: http://localhost:5001/api
- **ngrok Dashboard**: http://localhost:4040 (if ngrok is running)
- **Webhook Endpoint**: `https://your-ngrok-url.ngrok.io/api/webhook/sms`

## Manual Start (Alternative)

If you prefer to start services manually:

**Terminal 1 - Backend:**
```bash
python3 server.py
```

**Terminal 2 - Frontend:**
```bash
python3 -m streamlit run app.py
```

**Terminal 3 - ngrok:**
```bash
ngrok http 5001
```

## API Endpoints

- `GET /api` - Health check
- `GET /api/test-db` - Test MongoDB connection
- `GET /api/threads` - Get all text threads
- `GET /api/threads/{thread_id}/messages` - Get messages for a thread
- `GET /api/car-listings` - Get all car listings
- `GET /api/threads/{thread_id}/car-listing` - Get car listing for a thread
- `GET /api/visits` - Get scheduled visits
- `GET /api/visits/{visit_id}` - Get specific visit
- `POST /api/webhook/sms` - Mobile Text Alerts webhook endpoint
- `GET /api/templates` - List Mobile Text Alerts templates
- `POST /api/register-webhook` - Register webhook with Mobile Text Alerts

## Project Structure

```
Python/
├── app.py                    # Streamlit frontend
├── server.py                 # FastAPI backend
├── models.py                 # MongoDB models
├── utils.py                  # Utility functions (AI, SMS, scraping, scheduling)
├── requirements.txt          # Python dependencies
├── start.sh                  # Single-command startup script
├── helper_scripts/
│   ├── create_sample_visits.py
│   └── delete_thread_data.py
└── README.md                 # This file
```

## Environment Variables

Required environment variables (in `.env` file):

- `PORT` - Server port (default: 5001)
- `MONGODB_URI` - MongoDB connection string
- `OPENAI_API_KEY` - OpenAI API key for AI agent
- `MTA_API_KEY` - Mobile Text Alerts API key
- `MTA_AUTO_REPLY_TEMPLATE_ID` - Optional template ID for auto-replies
- `MTA_WEBHOOK_SECRET` - Secret for webhook verification
- `MTA_ALERT_EMAIL` - Email for webhook alerts

## How It Works

1. **SMS Webhook**: Mobile Text Alerts sends incoming SMS to `/api/webhook/sms`
2. **AI Agent**: Processes the message and responds based on conversation state
3. **Information Collection**: Agent collects car details (make, model, year, miles, price, etc.)
4. **Negotiation**: Agent negotiates price and doc fee when appropriate
5. **Scheduling**: Once all info is collected, agent schedules a visit using availability checking
6. **Completion**: Conversation ends after visit is successfully scheduled

## Helper Scripts

### Delete Thread Data
```bash
python3 helper_scripts/delete_thread_data.py +1234567890
```
Deletes all data (thread, messages, car listing, visits) for a phone number.

### Create Sample Visits
```bash
python3 helper_scripts/create_sample_visits.py
```
Creates sample visits for testing the calendar view.

## Troubleshooting

**Python/pip not found:**
- Make sure Python 3.8+ is installed
- Try `python3 --version` and `pip3 --version`
- On macOS, install via Homebrew: `brew install python3`

**MongoDB connection error:**
- Check your `MONGODB_URI` in `.env`
- Ensure MongoDB is running (if local)
- Install MongoDB via Homebrew: `brew install mongodb-community`

**ngrok installation fails:**
- The script automatically installs ngrok via Homebrew
- If Homebrew is missing, install from https://brew.sh
- Or install ngrok manually: `brew install ngrok/ngrok/ngrok`
- The script will continue without ngrok if installation fails (webhooks won't work)

**Homebrew not found:**
- Install Homebrew: `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
- Or continue without ngrok (webhooks won't work)

**Port already in use:**
- Change `PORT` in `.env` file
- Or stop the process using that port: `lsof -ti:5001 | xargs kill`

**Dependencies fail to install:**
- The script handles this automatically
- If issues persist, try manually: `pip3 install --upgrade pip && pip3 install -r requirements.txt`

**Services fail to start:**
- Check log files: `/tmp/car_scout_backend.log` and `/tmp/car_scout_frontend.log`
- Ensure MongoDB is running
- Check that all environment variables in `.env` are set correctly

## Notes

- The application uses MongoDB for persistent storage
- All conversations are stored in the database
- The AI agent automatically manages conversation flow
- Visit scheduling checks availability to avoid conflicts
- ngrok URL changes on each restart (unless using paid static domain)

## Stopping the Application

Press `Ctrl+C` in the terminal where `start.sh` is running. This will stop all services (backend, frontend, and ngrok).
