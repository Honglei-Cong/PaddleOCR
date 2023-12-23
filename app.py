from flask import Flask, request, render_template
from werkzeug.utils import secure_filename
from datetime import datetime
from tools.invoice_app import InvoiceApp
app = Flask(__name__)
invoice_app = InvoiceApp()

@app.route('/')
def index():
    return render_template('app.html')

@app.route('/upload', methods=['POST'])
def upload():
    for filename in request.files:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        files[filename].save('uploads/' + secure_filename(f'{timestamp}_{filename}'))

    return '上传成功'

@app.route('/api/v1/invoice/ir', methods=['POST'])
def ir():
    params = request.get_json()
    if 'filepath' in params:
        result = invoice_app.Process(params['filepath'])
        return "{}".format(result)
    return ""

if __name__ == '__main__':
    if not invoice_app.Initialize():
        exit(-1)
    app.run()

