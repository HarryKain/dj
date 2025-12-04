from __future__ import annotations

import functools
from typing import List, Dict
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
)


app = Flask(__name__)

# A secret key is required to use sessions.  In a production environment you
# should generate a random secret and keep it secret.  Here we use a fixed
# string for simplicity.
app.config['SECRET_KEY'] = 'replace-with-a-random-secret'


# Song queue.  Each entry is a dict with keys: id, title, artist, likes.
# In a real application you might use a database instead of an in‑memory list.
songs: List[Dict] = []

# List of genres available for voting and a dict to track vote counts.  Feel free
# to modify the genre names to suit your party.
genres: List[str] = [
    "Pop",
    "Rock",
    "Hip-Hop",
    "Elektronisch",
    "Dance",
    "Schlager",
    "R&B",
    "Reggae",
    "Latin",
    "Alternative",
]

# Initialize vote counts for each genre.  When users vote, the counts are
# incremented or decremented accordingly.
genre_votes: Dict[str, int] = {genre: 0 for genre in genres}


def get_next_id() -> int:
    """Return the next song id based on the highest existing id."""
    return (max((s['id'] for s in songs), default=0) + 1)


def require_dj(view):
    """Decorator that restricts access to views requiring DJ privileges."""
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('dj_logged_in'):
            flash('DJ login required', category='error')
            return redirect(url_for('login'))
        return view(*args, **kwargs)

    return wrapped


@app.route('/')
def index():
    # Sort songs by likes descending, then by id ascending.  This ensures the
    # most liked song appears at the top of the queue.
    sorted_songs = sorted(songs, key=lambda s: (-s['likes'], s['id']))
    # List of song IDs this user has already liked (stored in session).  Used to
    # disable like buttons so each person can only like a song once.
    liked_songs = session.get('liked_songs', [])
    disliked_songs = session.get('disliked_songs', [])
    # Compute genre vote data for initial rendering
    total_votes = sum(genre_votes.values())
    genre_data = []
    for genre in genres:
        count = genre_votes.get(genre, 0)
        percentage = (count / total_votes * 100) if total_votes > 0 else 0
        genre_data.append({'genre': genre, 'votes': count, 'percentage': percentage})
    top_genre = None
    if total_votes > 0:
        top_genre = max(genre_votes.items(), key=lambda item: item[1])[0]
    return render_template(
        'index.html',
        songs=sorted_songs,
        dj_logged_in=session.get('dj_logged_in', False),
        liked_songs=liked_songs,
        disliked_songs=disliked_songs,
        genres=genres,
        genre_data=genre_data,
        total_votes=total_votes,
        top_genre=top_genre,
        voted_genre=session.get('voted_genre'),
    )


@app.route('/add', methods=['POST'])
def add_song():
    title = request.form.get('title', '').strip()
    artist = request.form.get('artist', '').strip()
    if not title:
        flash('Bitte gib einen Songtitel ein.', category='error')
        return redirect(url_for('index'))
    if not artist:
        flash('Bitte gib einen Künstlernamen ein.', category='error')
        return redirect(url_for('index'))

    song = {
        'id': get_next_id(),
        'title': title,
        'artist': artist,
        'likes': 0,
        'dislikes': 0,
        # Timestamp for when the song was added; used in the DJ interface.
        'timestamp': datetime.now().strftime('%H:%M:%S'),
    }
    songs.append(song)
    flash('Song hinzugefügt!', category='success')
    return redirect(url_for('index'))


@app.route('/like/<int:song_id>', methods=['POST'])
def toggle_like(song_id: int):
    """
    Toggle a like on a song.  Users can like as many different songs as they
    want but only once per song.  If they have already liked this song,
    clicking again will remove their like (dislike) and decrement the song's
    like counter.  The list of song IDs a user has liked is stored in the
    session under 'liked_songs'.
    """
    liked = session.get('liked_songs', [])
    disliked = session.get('disliked_songs', [])
    # Find the song by ID
    for song in songs:
        if song['id'] == song_id:
            song.setdefault('dislikes', 0)
            if song_id in liked:
                # User has already liked this song – remove the like
                if song['likes'] > 0:
                    song['likes'] -= 1
                liked.remove(song_id)
                flash('Dein Daumen hoch wurde entfernt.', category='success')
            else:
                # Add a like to this song
                song['likes'] += 1
                liked.append(song_id)
                # Remove a potential dislike to keep the states exclusive
                if song_id in disliked:
                    if song['dislikes'] > 0:
                        song['dislikes'] -= 1
                    disliked.remove(song_id)
                flash('Daumen hoch abgegeben!', category='success')
            break
    session['liked_songs'] = liked
    session['disliked_songs'] = disliked
    return redirect(url_for('index'))


@app.route('/dislike/<int:song_id>', methods=['POST'])
def toggle_dislike(song_id: int):
    """
    Toggle a dislike on a song.  A dislike removes a previous like from the same
    user to avoid double‑voting.  Disliked song IDs are stored in the session.
    """
    liked = session.get('liked_songs', [])
    disliked = session.get('disliked_songs', [])
    for song in songs:
        if song['id'] == song_id:
            song.setdefault('likes', 0)
            song.setdefault('dislikes', 0)
            if song_id in disliked:
                if song['dislikes'] > 0:
                    song['dislikes'] -= 1
                disliked.remove(song_id)
                flash('Dein Daumen runter wurde entfernt.', category='success')
            else:
                song['dislikes'] += 1
                disliked.append(song_id)
                # Remove like if it exists to keep states exclusive
                if song_id in liked:
                    if song['likes'] > 0:
                        song['likes'] -= 1
                    liked.remove(song_id)
                flash('Daumen runter abgegeben.', category='success')
            break
    session['liked_songs'] = liked
    session['disliked_songs'] = disliked
    return redirect(url_for('index'))


@app.route('/remove/<int:song_id>', methods=['POST'])
@require_dj
def remove_song(song_id: int):
    global songs
    songs = [s for s in songs if s['id'] != song_id]
    flash('Song aus der Warteschlange entfernt.', category='success')
    return redirect(url_for('index'))


# Expose the current queue as JSON for client-side refreshing.
# Returns a list of song objects sorted by likes and id.
@app.route('/data')
def data():
    sorted_songs = sorted(songs, key=lambda s: (-s['likes'], s['id']))
    # Build a serialisable response.  For each song, include id, title, artist,
    # likes, and timestamp.
    song_list = [
        {
            'id': s['id'],
            'title': s['title'],
            'artist': s['artist'],
            'likes': s['likes'],
            'dislikes': s.get('dislikes', 0),
            'timestamp': s.get('timestamp', ''),
        }
        for s in sorted_songs
    ]
    # Prepare genre vote data
    total_votes = sum(genre_votes.values())
    # To avoid division by zero, handle case when total_votes is 0
    genre_data = []
    for genre in genres:
        count = genre_votes.get(genre, 0)
        percentage = (count / total_votes * 100) if total_votes > 0 else 0
        genre_data.append({
            'genre': genre,
            'votes': count,
            'percentage': percentage,
        })
    # Determine the top genre(s)
    top_genre = None
    if total_votes > 0:
        top_genre = max(genre_votes.items(), key=lambda item: item[1])[0]
    response = {
        'songs': song_list,
        'genres': genre_data,
        'total_votes': total_votes,
        'top_genre': top_genre,
    }
    return jsonify(response)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password', '')
        # Hard‑coded DJ password; in production you would securely store a hashed
        # password instead of plain text.
        if password == '2911':
            session['dj_logged_in'] = True
            flash('Erfolgreich als DJ eingeloggt.', category='success')
            return redirect(url_for('index'))
        flash('Falsches Passwort.', category='error')
    return render_template('login.html')


@app.route('/logout', methods=['POST'])
def logout():
    session.pop('dj_logged_in', None)
    flash('Abgemeldet.', category='success')
    return redirect(url_for('index'))


@app.route('/vote', methods=['POST'])
def vote_genre():
    """
    Handle genre voting.  Users can vote for one genre at a time.  If they have
    previously voted for another genre, that vote is removed before applying the new one.
    The selected genre is stored in the session under 'voted_genre'.
    """
    selected = request.form.get('genre')
    if not selected or selected not in genres:
        flash('Bitte wähle ein gültiges Genre aus.', category='error')
        return redirect(url_for('index'))
    # Retrieve the previously voted genre for this session
    previous = session.get('voted_genre')
    # Remove previous vote
    if previous and previous in genre_votes and genre_votes[previous] > 0:
        genre_votes[previous] -= 1
    # Add new vote
    genre_votes[selected] += 1
    # Store the new selection in the session
    session['voted_genre'] = selected
    flash(f'Deine Stimme für {selected} wurde gezählt!', category='success')
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True)
