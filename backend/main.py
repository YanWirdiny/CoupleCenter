from flask import Flask, request, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for cross-origin requests

# Homepage endpoint
@app.route('/')
def homepage():
    return render_template('index.html')  # Serve the homepage template

# "Will You Be My Girlfriend" endpoint
@app.route('/ask-girl', methods=['GET', 'POST'])
def ask_girlfriend():
    if request.method == 'POST':
        answer = request.form.get('answer')
        if answer == 'yes':
            response = "Congratulations! She said YES! 🎉"
        elif answer == 'no':
            response = "Sorry, she said NO. 😢"
        else:
            response = "Invalid response."
        return render_template('ask_girlfriend.html', response=response)
    return render_template('ask_girlfriend.html')  # Serve the form template

if __name__ == '__main__':
    app.run(debug=True)