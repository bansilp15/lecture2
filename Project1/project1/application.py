import os
import requests

from flask import Flask, session, render_template, request, redirect, url_for, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Configure session to use filesystem
app.config['JSON_SORT_KEYS'] = False
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["SECRET_KEY"] = "thisismysecretkeyusedforsession"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

@app.route("/", methods=["GET", "POST"])
def index():

	#for POST method.
	if request.method == "POST":
		email = request.form.get("email")
		password = request.form.get("password")
		
		user = db.execute("SELECT id, email, password FROM users WHERE email = :email",{"email":email}).fetchone()
		
		if user.email != email or user.password != password:
			return render_template("index.html", msg = True, message="Invalid email or password.")
		
		session["user_id"] = user.id
		return redirect(url_for('search'))
	
	#for GET method.
	return render_template("index.html")
	
@app.route("/signup", methods=["GET","POST"])
def signup():
	#only execute if method is POST.
	if request.method == "POST":
		fname = request.form.get("fname")
		lname = request.form.get("lname")
		email = request.form.get("email")
		password = request.form.get("password")
	
		#Check if the user already  exists or not.	
		if db.execute("SELECT email FROM users WHERE email=:email", {"email":email}).rowcount != 0:
			return render_template("signup.html", msg = True, message="Account already exists. Please login using the email id.")
	
		db.execute("INSERT INTO users(fname, lname, email, password) VALUES(:fname, :lname, :email, :password)", {"fname":fname, "lname":lname, "email":email, "password":password})
		db.commit()
		return redirect(url_for('index'))
		
	#executes when method is get.
	return render_template("signup.html")
	
@app.route("/search", methods=["GET","POST"])
def search():	
	if session.get("user_id", None) is not None: 
		username = session.get("user_id")
		user = db.execute("SELECT fname from users WHERE id= :id", {"id":username}).fetchone()
		if request.method == "POST":
			id = request.form.get("book")
			search_by = request.form.get("search_by")
			
			#nested if else to search by different options
			if search_by == "title":
				books = db.execute("SELECT * FROM books where title like concat('%', :title, '%')", {"title":id}).fetchall()
			elif search_by == "author":
				books = db.execute("SELECT * FROM books where author like concat('%', :author, '%')", {"author":id}).fetchall()
			else:
				books = db.execute("SELECT * FROM books where isbn like concat('%', :isbn, '%')", {"isbn":id}).fetchall()
			if len(books) == 0:
				return render_template("search.html", user= user, msg="No book found. Please enter valid title, isbn or author.", condition=False)
			else:
				return render_template("search.html", user=user, books=books, condition=True)
		else:
			return render_template("search.html", user=user)
	else:
		return redirect(url_for('index'))
	
@app.route("/book/<string:book_isbn>", methods=["GET", "POST"])
def book(book_isbn):
	if session.get("user_id", None) is not None:
		book = db.execute("SELECT * from books where isbn=:isbn", {"isbn":book_isbn}).fetchone()
		review = db.execute("SELECT * FROM reviews WHERE user_id in (SELECT id FROM users WHERE id=:user_id) AND book_id in (SELECT id FROM books WHERE id=:book_id)", {"user_id":session["user_id"], "book_id":book.id}).fetchone()
		res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "PYzS80nGW9DvLzTlrsTVUw", "isbns": book.isbn})
		if res.status_code != 200:
			#Set false when no review is found.
			goodread_review = False
			#Default values are given when no data is found on goodread api.
			work_ratings_count = "Not available"
			average_rating = "Not available"
			
		else:
			#Set true when goodread api reviews are available.
			goodread_review = True
			data = res.json()
			work_ratings_count = data ["books"][0]["work_ratings_count"]
			average_rating = data["books"][0]["average_rating"]
			
		if request.method == "POST":
			rating = request.form.get("rating")
			opinion = request.form.get("opinion")
			db.execute("INSERT INTO reviews(user_id, book_id, user_rating, user_opinion) VALUES(:user_id, :book_id, :rating, :opinion)", {"user_id":session["user_id"], "book_id":book.id, "rating":rating, "opinion":opinion})
			db.commit()
			#Getting the value of rating and opinion from database after it has been updated to show updated data. 
			review = db.execute("SELECT * FROM reviews WHERE user_id in (SELECT id FROM users WHERE id=:user_id) AND book_id in (SELECT id FROM books WHERE id=:book_id)", {"user_id":session["user_id"], "book_id":book.id}).fetchone()
			return render_template("book.html", condition=False, book=book, review=review, goodread_review=goodread_review, work_ratings_count=work_ratings_count, average_rating=average_rating)
		
		elif review is not None:	
			return render_template("book.html", book=book, review=review, goodread_review=goodread_review, work_ratings_count=work_ratings_count, average_rating=average_rating)
		else:
			return render_template("book.html", book=book, review=review, condition=True, goodread_review=goodread_review, work_ratings_count=work_ratings_count, average_rating=average_rating)
	else:
		return redirect(url_for('index'))
	
@app.route("/signout")
def signout():
	session.pop("user_id", None)
	return redirect(url_for('index'))

@app.route("/api/<string:isbn>")
def book_api(isbn):
	
	#Checking if book isbn is valid or not.
	book = db.execute("SELECT * FROM books WHERE isbn=:book_isbn", {"book_isbn": isbn}).fetchone()
	if book is None:
		return jsonify({"error 404":"Book not found"}), 404
		
		
	res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "PYzS80nGW9DvLzTlrsTVUw", "isbns": book.isbn})
	if res.status_code != 200:
		#Default values are given when no data is found on goodread api.
		work_ratings_count = "Not available"
		average_rating = "Not available"
			
	else:
		data = res.json()
		work_ratings_count = data ["books"][0]["work_ratings_count"]
		average_rating = data["books"][0]["average_rating"]
			
	return jsonify({
			"title": book.title,
			"author": book.author,
			"year": book.year,
			"isbn": book.isbn,
			"review_count": work_ratings_count,
			"average_score": average_rating
		})
