from flask import Flask, request, render_template
from werkzeug.utils import secure_filename
from datetime import datetime
app = Flask(__name__)

@app.route('/')
def index():
    return render_template('app.html')

@app.route('/upload', methods=['POST'])
def upload():
    for filename in request.files:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        files[filename].save('uploads/' + secure_filename(f'{timestamp}_{filename}'))

    return '上传成功'

if __name__ == '__main__':
    app.run()

