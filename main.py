from fastapi import FastAPI, Request, HTTPException, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import requests
import os
import base64
import urllib.parse
from dotenv import load_dotenv
import re

load_dotenv()

app = FastAPI()

templates = Jinja2Templates(directory="templates")

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
SCOPES = os.getenv("SCOPES", "user-top-read user-follow-read playlist-read-private")

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"

user_tokens = {}

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login")
def spotify_login(artist_name: str):
    auth_url = 'https://accounts.spotify.com/authorize'
    params = {
        'client_id': CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'scope': SCOPES,
        'state': artist_name
    }
    url = f"{auth_url}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url)

@app.get("/callback")
def spotify_callback(code: str, state: str):
    token_url = 'https://accounts.spotify.com/api/token'
    auth_header = base64.urlsafe_b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    headers = {
        'Authorization': f'Basic {auth_header}',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
    }
    response = requests.post(token_url, headers=headers, data=data)
    response_data = response.json()
    access_token = response_data.get('access_token')

    if not access_token:
        raise HTTPException(status_code=400, detail='Error obtaining access token')

    user_tokens['access_token'] = access_token
    return RedirectResponse(url=f"/calculate-fan-score?artist_name={urllib.parse.quote(state)}")

@app.get("/calculate-fan-score", response_class=HTMLResponse)
def calculate_fan_score(request: Request, artist_name: str):
    access_token = user_tokens.get('access_token')

    if not access_token:
        return RedirectResponse(url="/login")

    user_data = get_spotify_data(access_token, artist_name)

    if user_data is None:
        return templates.TemplateResponse("error.html", {"request": request, "message": "Artist not found"})

    algorithmic_score, factor_scores = calculate_fan_score_algorithm(user_data)
    mistral_analysis_score = factor_scores.pop('mistral_analysis')
    weighted_fan_score = algorithmic_score

    response_data = {
        'algorithmic_score': f'{algorithmic_score:.2f}%',
        'mistral_analysis_score': f'{mistral_analysis_score:.2f}%',
        'weighted_fan_score': f'{weighted_fan_score:.2f}%',
        'factor_scores': {k.replace('_', ' ').title(): f'{v:.2f}%' for k, v in factor_scores.items()},
        'artist_name': artist_name
    }

    return templates.TemplateResponse("fan_score.html", {"request": request, "data": response_data})

def calculate_fan_score_algorithm(user_data):
    factor_scores = {}
    weights = {
        'top_artist_rank': 0.20,
        'top_tracks': 0.15,
        'follows_artist': 0.15,
        'songs_in_playlists': 0.10,
        'overlapping_tracks': 0.10,
        'similar_genres': 0.10,
        'mistral_analysis': 0.20
    }

    top_artists = user_data['top_artists']
    artist_id = user_data['artist_id']
    artist_ids = [artist['id'] for artist in top_artists]
    if artist_id in artist_ids[:5]:
        rank = artist_ids.index(artist_id) + 1
        factor_scores['top_artist_rank'] = (6 - rank) / 5
    else:
        factor_scores['top_artist_rank'] = 0.0

    top_tracks = user_data['top_tracks'][:10]
    total_top_tracks = len(top_tracks)
    artist_tracks_in_top = [track for track in top_tracks if artist_id in track['artist_ids']]
    factor_scores['top_tracks'] = (len(artist_tracks_in_top) / total_top_tracks if total_top_tracks > 0 else 0.0)
    factor_scores['follows_artist'] = 1.0 if user_data['follows_artist'] else 0.0
    artist_songs_in_playlists = [track for track in user_data['playlist_tracks'] if artist_id in track['artist_ids']]
    num_songs_in_playlists = len(artist_songs_in_playlists)
    factor_scores['songs_in_playlists'] = min(num_songs_in_playlists / 20.0, 1.0)

    artist_top_track_ids = get_artist_top_tracks(artist_id, user_data['access_token'])
    user_top_track_ids = [track['id'] for track in top_tracks]
    overlapping_tracks = set(user_top_track_ids).intersection(set(artist_top_track_ids))
    factor_scores['overlapping_tracks'] = min(len(overlapping_tracks) / 10.0, 1.0)
    factor_scores['similar_genres'] = 1.0 if user_data['listens_to_similar_genres'] else 0.0

    mistral_score = mistral_ai_analysis(user_data)
    factor_scores['mistral_analysis'] = mistral_score

    total_weight = sum(weights.values())
    normalized_weights = {k: v / total_weight for k, v in weights.items()}
    fan_score = sum(factor_scores[factor] * normalized_weights[factor] for factor in factor_scores)
    fan_score_percentage = fan_score * 100
    factor_scores_percentage = {factor: score * 100 for factor, score in factor_scores.items()}

    return fan_score_percentage, factor_scores_percentage

def mistral_ai_analysis(user_data):
    prompt = generate_mistral_prompt(user_data)
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mistral-large-latest",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 150
    }

    response = requests.post(MISTRAL_API_URL, json=payload, headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Error connecting to Mistral AI")

    response_data = response.json()
    output_text = response_data['choices'][0]['message']['content']
    mistral_score = parse_mistral_output(output_text)
    return mistral_score

def generate_mistral_prompt(user_data):
    top_artists = ', '.join([artist['name'] for artist in user_data['top_artists'][:5]])
    top_tracks = ', '.join([track['name'] for track in user_data['top_tracks'][:5]])
    artist_genres = ', '.join(user_data['artist_genres'])
    prompt = (f"Analyze the following user data:\n"
              f"User's top artists: {top_artists}.\n"
              f"User's top tracks: {top_tracks}.\n"
              f"Artist genres: {artist_genres}.\n"
              f"Provide a fan engagement score between 0 and 1 based on how closely the user's listening habits align with the artist's style and genres.")
    return prompt

def parse_mistral_output(output_text):
    match = re.search(r"([0-1]\.\d+)", output_text)
    if match:
        score = float(match.group(1))
        return min(max(score, 0.0), 1.0)
    return 0.5

def get_spotify_data(access_token, artist_name):
    headers = {"Authorization": f"Bearer {access_token}"}
    search_response = requests.get(
        "https://api.spotify.com/v1/search",
        headers=headers,
        params={'q': artist_name, 'type': 'artist', 'limit': 1}
    )
    search_results = search_response.json()
    if not search_results.get('artists', {}).get('items'):
        return None
    artist_info = search_results['artists']['items'][0]
    artist_id = artist_info['id']
    artist_genres = artist_info.get('genres', [])
    top_artists_response = requests.get(
        "https://api.spotify.com/v1/me/top/artists?limit=50",
        headers=headers
    )
    top_artists_items = top_artists_response.json().get('items', [])
    top_artists = [
        {
            'name': artist['name'],
            'id': artist['id'],
            'genres': artist.get('genres', [])
        }
        for artist in top_artists_items
    ]
    top_tracks_response = requests.get(
        "https://api.spotify.com/v1/me/top/tracks?limit=50",
        headers=headers
    )
    top_tracks_items = top_tracks_response.json().get('items', [])
    top_tracks = []
    for track in top_tracks_items:
        artist_ids = [artist['id'] for artist in track['artists']]
        top_tracks.append({
            'name': track['name'],
            'id': track['id'],
            'artist_names': [artist['name'] for artist in track['artists']],
            'artist_ids': artist_ids
        })
    follows_response = requests.get(
        "https://api.spotify.com/v1/me/following/contains",
        headers=headers,
        params={'type': 'artist', 'ids': artist_id}
    )
    follows_artist = follows_response.json()[0]
    playlists = []
    next_url = "https://api.spotify.com/v1/me/playlists?limit=20"
    while next_url:
        playlists_response = requests.get(next_url, headers=headers).json()
        playlists.extend(playlists_response.get('items', []))
        next_url = playlists_response.get('next')
        if len(playlists) >= 30:
            playlists = playlists[:30]
            break
    playlist_tracks = []
    for playlist in playlists:
        playlist_id = playlist['id']
        tracks_url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks?limit=100"
        while tracks_url:
            tracks_response = requests.get(tracks_url, headers=headers).json()
            items = tracks_response.get('items', [])
            for item in items:
                track = item.get('track')
                if track and track.get('id'):
                    artist_ids = [artist['id'] for artist in track['artists']]
                    playlist_tracks.append({
                        'name': track['name'],
                        'id': track['id'],
                        'artist_names': [artist['name'] for artist in track['artists']],
                        'artist_ids': artist_ids
                    })
            tracks_url = tracks_response.get('next')
    user_genres = set()
    for artist in top_artists:
        user_genres.update(artist.get('genres', []))
    listens_to_similar_genres = bool(
        user_genres.intersection(artist_genres)
    )
    return {
        'access_token': access_token,
        'artist_id': artist_id,
        'artist_genres': artist_genres,
        'top_artists': top_artists,
        'top_tracks': top_tracks,
        'follows_artist': follows_artist,
        'playlist_tracks': playlist_tracks,
        'listens_to_similar_genres': listens_to_similar_genres
    }

def get_artist_top_tracks(artist_id, access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(
        f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks",
        headers=headers,
        params={'market': 'from_token'}
    )
    tracks = response.json().get('tracks', [])
    track_ids = [track['id'] for track in tracks]
    return track_ids