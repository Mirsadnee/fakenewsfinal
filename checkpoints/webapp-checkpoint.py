import os
import requests
from flask import Flask, render_template, request
import pickle
import re
import nltk
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import PassiveAggressiveClassifier
from nltk.stem import WordNetLemmatizer
from nltk.corpus import stopwords
from dotenv import load_dotenv # type: ignore

# Load environment variables from a .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Load the machine learning model and vectorizer
loaded_model = pickle.load(open("model.pkl", 'rb'))
tfidf_v = pickle.load(open("tfidf_vectorizer.pkl", 'rb'))  # Make sure to save the vectorizer with the model

# Initialize the necessary NLTK tools
lemmatizer = WordNetLemmatizer()
stpwrds = set(stopwords.words('english'))

# Helper function for fake news detection
def fake_news_det(news):
    review = news
    review = re.sub(r'[^a-zA-Z\s]', '', review)
    review = review.lower()
    review = nltk.word_tokenize(review)
    corpus = [lemmatizer.lemmatize(y) for y in review if y not in stpwrds]
    input_data = [' '.join(corpus)]
    vectorized_input_data = tfidf_v.transform(input_data)
    prediction = loaded_model.predict(vectorized_input_data)
    return prediction

# Home route
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/predict', methods=['GET', 'POST'])
def predict():
    if request.method == 'POST':
        message = request.form['news']
        pred = fake_news_det(message)

        def predi(pred):
            if pred[0] == 1:
                res = "Fake News📰"
            else:
                res = "Real News📰"
            return res

        result = predi(pred)
        return render_template("prediction.html", prediction_text="{}".format(result))

    return render_template('prediction.html', prediction="Something went wrong")

# New route to test API and get top headlines
@app.route('/test_api')
def test_api():
    api_key = os.getenv('NEWS_API_KEY')  # Retrieve API key from environment variable
    url = f'https://newsapi.org/v2/top-headlines?country=us&apiKey={api_key}'
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        articles = data['articles']
        return render_template('test_api.html', articles=articles)
    else:
        return render_template('error.html', message=f"Error: {response.status_code} - {response.text}")

# Run the app
if __name__ == '__main__':
    app.run(debug=True)
