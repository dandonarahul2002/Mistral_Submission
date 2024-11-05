# Fan Score Calculator App

## About the App
The Fan Score Calculator App is a web-based application that allows users to connect their Spotify accounts and view personalized fan scores for their favorite artists. The app uses data from the Spotify API to analyze user listening habits and leverages the Mistral AI model to enhance engagement scoring. Users can see detailed factor scores, Mistral AI analysis, and an overall weighted fan score.

## Tech Stack
- **Backend Framework**: FastAPI
- **Frontend**: Jinja2 Templates, HTML, CSS
- **Programming Language**: Python 3.12
- **Database**: (Not applicable; uses in-memory storage)
- **APIs & Libraries**:
  - `requests`
  - `dotenv`
  - `uvicorn`
  - `Jinja2`
  - `HuggingFace Transformers`

- **External APIs**:
  - Spotify Web API (OAuth 2.0 authentication)
  - Mistral AI API

## Requirements
- **Python Version**: Python 3.12 
- **Virtual Environment**: Recommended for package isolation
- **Packages**:
  - FastAPI
  - uvicorn
  - requests
  - python-dotenv
  - Jinja2
  - transformers

## Installation & Setup
1. **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/yourproject.git
    cd yourproject
    ```

2. **Set up a virtual environment**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3. **Install the required dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4. **Create a `.env` file** in the root directory and add your credentials get my spotify Client_id and secret [here](https://drive.google.com/file/d/1LDnwg1469pbOPkD4pZYzoSzYmwESYApb/view?usp=sharing):
    ```env
    CLIENT_ID=your_spotify_client_id
    CLIENT_SECRET=your_spotify_client_secret
    REDIRECT_URI=http://localhost:8000/callback
    MISTRAL_API_KEY=your_mistral_api_key
    ```

5. **Run the application**:
    ```bash
    uvicorn main:app --reload
    ```

6. **Access the app** at:
    ```
    http://127.0.0.1:8000
    ```

## Features
- **User Authentication**: Secure OAuth 2.0 flow for connecting with Spotify.
- **Personalized Fan Score**: Calculate how engaged a user is with an artist based on listening history.
- **Mistral AI Analysis**: Enhances fan scoring using AI-driven analysis.
- **Detailed Breakdown**: View individual factor scores contributing to the overall fan score.

## Usage
- Visit the home page and enter the name of your favorite artist.
- Click "Connect with Spotify" to authorize access.
- The app fetches data from Spotify and displays the calculated fan score along with a detailed breakdown.

