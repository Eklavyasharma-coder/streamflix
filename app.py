import os
from datetime import datetime
from urllib.parse import quote
import requests
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import or_, func

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-change-this-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///streamflix.db").replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
TMDB_KEY = os.getenv("TMDB_API_KEY", "")

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="user", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviews = db.relationship("Review", backref="user", cascade="all, delete-orphan")
    history = db.relationship("WatchHistory", backref="user", cascade="all, delete-orphan")

class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tmdb_id = db.Column(db.Integer, unique=True, nullable=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    overview = db.Column(db.Text, default="")
    year = db.Column(db.Integer, nullable=True, index=True)
    genres = db.Column(db.String(300), default="")
    language = db.Column(db.String(40), default="")
    poster_path = db.Column(db.String(500), default="")
    backdrop_path = db.Column(db.String(500), default="")
    trailer_key = db.Column(db.String(40), default="")
    video_url = db.Column(db.String(1000), default="")
    published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def poster(self):
        if self.poster_path.startswith("http"): return self.poster_path
        return "https://image.tmdb.org/t/p/w500" + self.poster_path if self.poster_path else ""
    @property
    def backdrop(self):
        if self.backdrop_path.startswith("http"): return self.backdrop_path
        return "https://image.tmdb.org/t/p/w1280" + self.backdrop_path if self.backdrop_path else ""
    @property
    def average_rating(self):
        value = db.session.query(func.avg(Review.rating)).filter_by(movie_id=self.id).scalar()
        return round(float(value), 1) if value else None

class WatchHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey("movie.id"), nullable=False)
    position_seconds = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    movie = db.relationship("Movie")
    __table_args__ = (db.UniqueConstraint("user_id", "movie_id", name="uq_history_user_movie"),)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey("movie.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    body = db.Column(db.String(1200), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    movie = db.relationship("Movie")
    __table_args__ = (db.UniqueConstraint("user_id", "movie_id", name="uq_review_user_movie"),)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def admin_required():
    if not current_user.is_authenticated or current_user.role != "admin":
        abort(403)

def tmdb(path, params=None):
    if not TMDB_KEY: return None
    try:
        response = requests.get("https://api.themoviedb.org/3/" + path.lstrip("/"),
                                params={"api_key": TMDB_KEY, **(params or {})}, timeout=8)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None

def import_tmdb_movie(tm):
    movie = Movie.query.filter_by(tmdb_id=tm.get("id")).first()
    if movie: return movie
    details = tmdb(f"movie/{tm['id']}", {"append_to_response": "videos"})
    if not details: details = tm
    videos = (details.get("videos") or {}).get("results", [])
    trailer = next((v.get("key") for v in videos if v.get("site") == "YouTube" and v.get("type") == "Trailer"), "")
    genres = ", ".join(g["name"] for g in details.get("genres", [])) or ", ".join(g["name"] for g in tm.get("genre_ids", []) if isinstance(g, dict))
    release = details.get("release_date", tm.get("release_date", ""))
    movie = Movie(tmdb_id=tm.get("id"), title=details.get("title", tm.get("title", "Untitled")),
                  overview=details.get("overview", tm.get("overview", "")), year=int(release[:4]) if release[:4].isdigit() else None,
                  genres=genres, language=details.get("original_language", tm.get("original_language", "")),
                  poster_path=details.get("poster_path", tm.get("poster_path", "")),
                  backdrop_path=details.get("backdrop_path", tm.get("backdrop_path", "")), trailer_key=trailer)
    db.session.add(movie); db.session.commit()
    return movie

def seed():
    if Movie.query.count(): return
    demo = [
        ("The Sample Adventure", 2024, "Adventure, Action", "A demo title for testing the StreamFlix catalogue.", "https://storage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"),
        ("Midnight Mystery", 2023, "Mystery, Thriller", "A fictional mystery entry. Replace this with licensed content.", ""),
        ("Galaxy Stories", 2025, "Sci-Fi, Adventure", "A science-fiction demo entry for your catalogue.", ""),
        ("Laughing Days", 2022, "Comedy", "A light-hearted demo catalogue entry.", ""),
        ("Anime Horizons", 2024, "Anime, Fantasy", "A fantasy-inspired demo catalogue entry.", ""),
    ]
    for title, year, genres, overview, video in demo:
        db.session.add(Movie(title=title, year=year, genres=genres, overview=overview, video_url=video))
    db.session.commit()

with app.app_context():
    db.create_all()
    seed()
    admin_email = os.getenv("ADMIN_EMAIL", "admin@streamflix.local")
    admin_password = os.getenv("ADMIN_PASSWORD", "ChangeMe123!")
    if not User.query.filter_by(email=admin_email.lower()).first():
        db.session.add(User(name="StreamFlix Admin", email=admin_email.lower(),
                            password_hash=generate_password_hash(admin_password), role="admin"))
        db.session.commit()

@app.route("/")
def home():
    movies = Movie.query.filter_by(published=True).order_by(Movie.created_at.desc()).all()
    trending = sorted(movies, key=lambda m: (m.average_rating or 0), reverse=True)
    recommended = []
    if current_user.is_authenticated:
        watched_ids = [h.movie_id for h in WatchHistory.query.filter_by(user_id=current_user.id).all()]
        watched_genres = set()
        for m in Movie.query.filter(Movie.id.in_(watched_ids)).all():
            watched_genres.update(g.strip().lower() for g in m.genres.split(",") if g.strip())
        recommended = [m for m in movies if m.id not in watched_ids and watched_genres.intersection(g.strip().lower() for g in m.genres.split(","))]
    return render_template("home.html", movies=movies, trending=trending[:8], recommended=recommended[:8])

@app.route("/movies")
def movies():
    q = request.args.get("q", "").strip()
    genre = request.args.get("genre", "").strip()
    language = request.args.get("language", "").strip()
    year = request.args.get("year", "").strip()
    min_rating = request.args.get("rating", "").strip()
    sort = request.args.get("sort", "newest")
    query = Movie.query.filter_by(published=True)
    if q: query = query.filter(or_(Movie.title.ilike(f"%{q}%"), Movie.overview.ilike(f"%{q}%"), Movie.genres.ilike(f"%{q}%")))
    if genre: query = query.filter(Movie.genres.ilike(f"%{genre}%"))
    if language: query = query.filter(Movie.language.ilike(f"%{language}%"))
    if year.isdigit(): query = query.filter_by(year=int(year))
    results = query.all()
    if min_rating:
        try: results = [m for m in results if (m.average_rating or 0) >= float(min_rating)]
        except ValueError: pass
    if sort == "rating": results.sort(key=lambda m: m.average_rating or 0, reverse=True)
    elif sort == "title": results.sort(key=lambda m: m.title.lower())
    else: results.sort(key=lambda m: m.created_at, reverse=True)
    return render_template("movies.html", movies=results, q=q, genre=genre, language=language, year=year, rating=min_rating, sort=sort)

@app.route("/movie/<int:movie_id>")
def detail(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    if not movie.published and (not current_user.is_authenticated or current_user.role != "admin"): abort(404)
    reviews = Review.query.filter_by(movie_id=movie.id).order_by(Review.created_at.desc()).all()
    existing = Review.query.filter_by(movie_id=movie.id, user_id=current_user.id).first() if current_user.is_authenticated else None
    similar = [m for m in Movie.query.filter(Movie.id != movie.id, Movie.published.is_(True)).all()
               if set(g.strip().lower() for g in movie.genres.split(",") if g.strip()).intersection(g.strip().lower() for g in m.genres.split(","))]
    return render_template("detail.html", movie=movie, reviews=reviews, existing=existing, similar=similar[:6])

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name, email, password = request.form.get("name","").strip(), request.form.get("email","").strip().lower(), request.form.get("password","")
        if not name or not email or len(password) < 8:
            flash("Enter your name, a valid email, and a password of at least 8 characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("This email is already registered.", "error")
        else:
            user = User(name=name, email=email, password_hash=generate_password_hash(password))
            db.session.add(user); db.session.commit(); login_user(user)
            return redirect(url_for("home"))
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email, password = request.form.get("email","").strip().lower(), request.form.get("password","")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user); return redirect(request.args.get("next") or url_for("home"))
        flash("Incorrect email or password.", "error")
    return render_template("auth.html", mode="login")

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user(); return redirect(url_for("home"))

@app.route("/profile")
@login_required
def profile():
    history = WatchHistory.query.filter_by(user_id=current_user.id).order_by(WatchHistory.updated_at.desc()).all()
    return render_template("profile.html", history=history)

@app.route("/watch/<int:movie_id>")
@login_required
def watch(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    if not movie.published: abort(404)
    row = WatchHistory.query.filter_by(user_id=current_user.id, movie_id=movie.id).first()
    if not row:
        row = WatchHistory(user_id=current_user.id, movie_id=movie.id); db.session.add(row)
    row.updated_at = datetime.utcnow(); db.session.commit()
    return render_template("watch.html", movie=movie, start_at=row.position_seconds)

@app.post("/api/history/<int:movie_id>")
@login_required
def save_progress(movie_id):
    data = request.get_json(silent=True) or {}
    row = WatchHistory.query.filter_by(user_id=current_user.id, movie_id=movie_id).first()
    if not row:
        row = WatchHistory(user_id=current_user.id, movie_id=movie_id); db.session.add(row)
    row.position_seconds = max(0, min(int(data.get("position", 0)), 10**9))
    row.updated_at = datetime.utcnow(); db.session.commit()
    return jsonify(ok=True)

@app.post("/movie/<int:movie_id>/review")
@login_required
def review(movie_id):
    Movie.query.get_or_404(movie_id)
    try: rating = int(request.form.get("rating", "0"))
    except ValueError: rating = 0
    body = request.form.get("body", "").strip()[:1200]
    if rating not in range(1, 6):
        flash("Choose a rating from 1 to 5.", "error")
    else:
        row = Review.query.filter_by(movie_id=movie_id, user_id=current_user.id).first()
        if not row:
            row = Review(movie_id=movie_id, user_id=current_user.id); db.session.add(row)
        row.rating, row.body, row.created_at = rating, body, datetime.utcnow()
        db.session.commit(); flash("Your review was saved.", "success")
    return redirect(url_for("detail", movie_id=movie_id))

@app.post("/movie/<int:movie_id>/watchlist")
@login_required
def toggle_watchlist(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    key = f"watchlist_{current_user.id}"
    ids = set(map(int, request.cookies.get(key, "").split(","))) if request.cookies.get(key) else set()
    if movie.id in ids: ids.remove(movie.id)
    else: ids.add(movie.id)
    response = redirect(request.referrer or url_for("home"))
    response.set_cookie(key, ",".join(map(str, sorted(ids))), httponly=True, samesite="Lax")
    return response

@app.route("/my-list")
@login_required
def my_list():
    key = f"watchlist_{current_user.id}"
    ids = set(map(int, request.cookies.get(key, "").split(","))) if request.cookies.get(key) else set()
    movies = Movie.query.filter(Movie.id.in_(ids), Movie.published.is_(True)).all() if ids else []
    return render_template("movies.html", movies=movies, q="", genre="", language="", year="", rating="", sort="newest", page_title="My List")

@app.route("/admin")
@login_required
def admin():
    admin_required()
    return render_template("admin.html", movies=Movie.query.order_by(Movie.created_at.desc()).all(),
                           users=User.query.order_by(User.created_at.desc()).all(),
                           views=WatchHistory.query.count(), reviews=Review.query.count())

@app.route("/admin/tmdb")
@login_required
def admin_tmdb_search():
    admin_required()
    q = request.args.get("q", "").strip()
    results = []
    if q:
        data = tmdb("search/movie", {"query": q, "include_adult": "false"})
        results = data.get("results", [])[:10] if data else []
    return render_template("tmdb.html", q=q, results=results)

@app.post("/admin/tmdb/import/<int:tmdb_id>")
@login_required
def admin_tmdb_import(tmdb_id):
    admin_required()
    data = tmdb(f"movie/{tmdb_id}", {"append_to_response": "videos"})
    if not data: flash("TMDB request failed. Check your TMDB_API_KEY and connection.", "error")
    else:
        movie = import_tmdb_movie(data)
        flash(f"Imported or found: {movie.title}", "success")
    return redirect(url_for("admin_tmdb_search"))

@app.route("/admin/movie/new", methods=["GET", "POST"])
@app.route("/admin/movie/<int:movie_id>/edit", methods=["GET", "POST"])
@login_required
def admin_movie_form(movie_id=None):
    admin_required()
    movie = Movie.query.get_or_404(movie_id) if movie_id else Movie()
    if request.method == "POST":
        movie.title = request.form.get("title","").strip()[:200]
        movie.overview = request.form.get("overview","").strip()
        movie.year = int(request.form["year"]) if request.form.get("year","").isdigit() else None
        movie.genres = request.form.get("genres","").strip()[:300]
        movie.language = request.form.get("language","").strip()[:40]
        movie.poster_path = request.form.get("poster_path","").strip()[:500]
        movie.backdrop_path = request.form.get("backdrop_path","").strip()[:500]
        movie.trailer_key = request.form.get("trailer_key","").strip()[:40]
        movie.video_url = request.form.get("video_url","").strip()[:1000]
        movie.published = request.form.get("published") == "on"
        if not movie.title:
            flash("Title is required.", "error")
        else:
            db.session.add(movie); db.session.commit(); flash("Movie saved.", "success")
            return redirect(url_for("admin"))
    return render_template("admin_movie.html", movie=movie)

@app.post("/admin/movie/<int:movie_id>/delete")
@login_required
def admin_movie_delete(movie_id):
    admin_required()
    movie = Movie.query.get_or_404(movie_id)
    WatchHistory.query.filter_by(movie_id=movie.id).delete()
    Review.query.filter_by(movie_id=movie.id).delete()
    db.session.delete(movie); db.session.commit()
    flash("Movie deleted.", "success")
    return redirect(url_for("admin"))

@app.errorhandler(403)
def forbidden(_): return render_template("error.html", code=403, message="Admin access required."), 403

if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "1") == "1")
