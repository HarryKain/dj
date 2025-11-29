"""
This Flask application provides a simple party‑playlist manager.  Guests can
submit songs with a title and artist, other guests can like songs, and the DJ can
mark songs as played (removing them from the queue).  The queue is stored in
memory; persisting to disk would require additional work.

Endpoints
---------
GET `/`                     → Show the queue and song submission form.
POST `/add`                 → Add a new song to the queue.
POST `/like/<int:song_id>`   → Increment the like counter on the song with the
                              given ID.
GET `/login`                → Display a login form for the DJ.
POST `/login`               → Process the DJ login, setting a session flag when
                              the password matches 2911.
POST `/logout`              → Remove the DJ session flag.
POST `/remove/<int:song_id>` → Remove a song (DJ only).

To run the app locally:
    pip install -r requirements.txt
    flask run

"""

from __future__ import annotations

import functools
from typing import List, Dict

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)


app = Flask(__name__)

# A secret key is required to use sessions.  In a production environment you
# should generate a random secret and keep it secret.  Here we use a fixed
# string for simplicity.
app.config['SECRET_KEY'] = 'replace-with-a-random-secret'


# Song queue.  Each entry is a dict with keys: id, title, artist, likes.
# In a real application you might use a database instead of an in‑memory list.
songs: List[Dict] = []


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
    # Sort songs by likes descending, then by id ascending (to keep older songs
    # earlier if likes tie).  This ensures the most liked song appears at the
    # top of the queue.
    sorted_songs = sorted(songs, key=lambda s: (-s['likes'], s['id']))
    return render_template(
        'index.html',
        songs=sorted_songs,
        dj_logged_in=session.get('dj_logged_in', False),
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
    }
    songs.append(song)
    flash('Song hinzugefügt!', category='success')
    return redirect(url_for('index'))


@app.route('/like/<int:song_id>', methods=['POST'])
def like_song(song_id: int):
    for song in songs:
        if song['id'] == song_id:
            song['likes'] += 1
            break
    return redirect(url_for('index'))


@app.route('/remove/<int:song_id>', methods=['POST'])
@require_dj
def remove_song(song_id: int):
    global songs
    songs = [s for s in songs if s['id'] != song_id]
    flash('Song aus der Warteschlange entfernt.', category='success')
    return redirect(url_for('index'))


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


if __name__ == '__main__':
    app.run(debug=True)