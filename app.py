from flask import Flask, render_template, request, jsonify, send_file
from log_splitter import LogProcessor
import os
import tempfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Global variable to store the current log processor instance
log_processor = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    global log_processor
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Initialize log processor with the uploaded file
        log_processor = LogProcessor(filepath)
        num_chunks = log_processor.split_by_second()
        log_processor.compress_files()
        size_comparison = log_processor.get_total_size_comparison()
        
        return jsonify({
            'message': 'File processed successfully',
            'chunks': num_chunks,
            'size_comparison': size_comparison
        })

@app.route('/view_logs', methods=['GET'])
def view_logs():
    global log_processor
    if not log_processor:
        return jsonify({'error': 'No log file has been processed yet'}), 400
    
    start_timestamp = request.args.get('start_timestamp')
    end_timestamp = request.args.get('end_timestamp')
    log_type = request.args.get('log_type', None)
    
    if not start_timestamp:
        return jsonify({'error': 'Start timestamp is required'}), 400
    
    try:
        # Create a temporary file to store the output
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_output = os.path.join(temp_dir, 'output.txt')
            with open(temp_output, 'w') as f:
                # Redirect stdout to the file temporarily
                import sys
                original_stdout = sys.stdout
                sys.stdout = f
                if end_timestamp:
                    log_processor.view_logs_by_timerange(start_timestamp, end_timestamp, log_type)
                else:
                    log_processor.view_logs_by_timestamp(start_timestamp, log_type)
                sys.stdout = original_stdout
            
            # Read the contents of the temporary file
            with open(temp_output, 'r') as f:
                logs = f.read().splitlines()
        
        return jsonify({'logs': logs})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/reset', methods=['POST'])
def reset():
    global log_processor
    if not log_processor:
        return jsonify({'error': 'No log file has been processed yet'}), 400
    
    try:
        log_processor.reset_processing()
        return jsonify({'message': 'Processing reset successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 