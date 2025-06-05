from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
import os
import json
from datetime import datetime
import pprint
from werkzeug.utils import secure_filename
from neotech_reader.processing_module import process_document, extract_structured_data
import re
from typing import Dict, Any, Tuple
import logging

# Configure logging
logging.basicConfig(level = logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['RESULTS_FOLDER'] = 'results'
app.config['CANDIDATES_FOLDER'] = 'candidates'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'png', 'jpg', 'jpeg', 'tiff'}
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max file size
app.secret_key = 'use_a_strong_random_secret_key_here'

# Create necessary directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok = True)
os.makedirs(app.config['RESULTS_FOLDER'], exist_ok = True)
os.makedirs(app.config['CANDIDATES_FOLDER'], exist_ok = True)

# Dictionary to store results
results_dict: Dict[str, Any] = {}

# Dictionary to store candidates
candidates_dict: Dict[str, Any] = {}

# Load existing results if available
results_json_path = os.path.join(app.config['RESULTS_FOLDER'], 'results.json')
if os.path.exists(results_json_path):
    try:
        with open(results_json_path, 'r') as f:
            results_dict = json.load(f)
    except json.JSONDecodeError:
        results_dict = {}

# Load existing candidates if available
candidates_json_path = os.path.join(app.config['CANDIDATES_FOLDER'], 'candidates.json')
if os.path.exists(candidates_json_path):
    try:
        with open(candidates_json_path, 'r') as f:
            candidates_dict = json.load(f)
    except json.JSONDecodeError:
        candidates_dict = {}

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def validate_candidate_data(data: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate candidate data before saving"""
    if not data.get('first_name', '').strip() or not data.get('last_name', '').strip():
        return False, "First and last name are required"
    if not data.get('contact_numbers', []):
        return False, "At least one contact number is required"
    
    # Validate email addresses if provided
    if data.get('email_ids'):
        for email in data.get('email_ids', []):
            if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
                return False, f"Invalid email format: {email}"
    
    return True, ""

def cleanup_temp_files(file_path: str) -> None:
    """Clean up temporary files"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        logging.warning(f"Failed to remove temporary file {file_path}: {str(e)}")

@app.route('/', methods = ['GET', 'POST'])
def upload_file():
    if request.method == 'GET':
        return render_template('upload.html')

    if 'files' not in request.files:
        flash('No file part', 'danger')
        return render_template('upload.html')
    
    files = request.files.getlist('files')
    
    if not files or files[0].filename == '':
        flash('No selected files', 'danger')
        return render_template('upload.html')
    
    processed_files = []
    
    for file in files:
        if not allowed_file(file.filename):
            processed_files.append({
                'filename': file.filename,
                'status': 'error',
                'error': 'File type not allowed'
            })
            continue

        if file.content_length > app.config['MAX_CONTENT_LENGTH']:
            processed_files.append({
                'filename': file.filename,
                'status': 'error',
                'error': 'File too large (max 10MB)'
            })
            continue

        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        try:
            file.save(file_path)
            error, text = process_document(file_path)
            
            if error:
                processed_files.append({
                    'filename': filename,
                    'status': 'error',
                    'error': error
                })
                cleanup_temp_files(file_path)
                continue
            
            # Save the extracted text to a text file
            text_filename = os.path.splitext(filename)[0] + '.txt'
            text_path = os.path.join(app.config['RESULTS_FOLDER'], text_filename)
            with open(text_path, 'w', encoding = 'utf-8') as f:
                f.write(text)
            
            # Add to the results dictionary with updated structure
            results_dict[filename] = {
                'formatted_text': text,
                'plaintext': ' '.join(text.split()),
                'date_processed': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'text_file': text_filename,
                'cleaned_data': {
                    'first_name': '',
                    'middle_name': '',
                    'last_name': '',
                    'contact_numbers': [],
                    'email_ids': [],
                    'education': {
                        'class_12': '',
                        'college': '',
                        'higher_studies': ''
                    },
                    'work_experience': '',
                    'skillset': [],
                    'toolset': [],
                    'programming_languages': [],
                    'projects': [],
                    'certifications': [],
                    'relevant_links': {
                        'linkedin': '',
                        'github': '',
                        'portfolio': '',
                        'other': []
                    }
                }
            }
            
            # Extract basic information
            email_matches = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)
            phone_matches = re.findall(r'(?:\+\d{1,3}[-\s]?)?\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}', text)
            
            if email_matches:
                results_dict[filename]['cleaned_data']['email_ids'] = email_matches
            
            if phone_matches:
                results_dict[filename]['cleaned_data']['contact_numbers'] = phone_matches
            
            # Extract structured data using LLM API
            try:
                structured_data = extract_structured_data(text)
                results_dict[filename]['cleaned_data'].update(structured_data)
            except Exception as e:
                logger.error(f"Failed to extract structured data: {str(e)}")
                # Continue processing even if structured data extraction fails
            
            processed_files.append({
                'filename': filename,
                'status': 'success',
                'text_preview': text[:100] + '...' if len(text) > 100 else text
            })
            
        except Exception as e:
            processed_files.append({
                'filename': filename,
                'status': 'error',
                'error': str(e)
            })
        finally:
            cleanup_temp_files(file_path)
    
    # Save the updated results dictionary
    with open(results_json_path, 'w', encoding = 'utf-8') as f:
        json.dump(results_dict, f, indent = 4)
    
    return render_template('upload.html', processed_files = processed_files)

@app.route('/results', methods = ['GET'])
def results():
    return render_template('results.html', results_dict = results_dict, candidates_dict = candidates_dict)

@app.route('/candidates/new', methods = ['GET', 'POST'])
def new_candidate():
    if request.method == 'GET':
        # Display form to create a new candidate
        return render_template(
            'candidate.html', 
            candidate = None, 
            filename = None,
            is_edit_mode = True,
            is_new = True
        )
    # if the request method is POST, then we need to save the candidate data
    # Generate a unique filename for the new candidate
    new_filename = f"manual_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    
    # Build the candidate data structure from form data
    candidate_data = process_candidate_form_data(request.form)
    
    # Validate candidate data
    is_valid, error_msg = validate_candidate_data(candidate_data)
    if not is_valid:
        return render_template(
            'candidate.html',
            candidate = candidate_data,
            filename = new_filename,
            is_edit_mode = True,
            is_new = True,
            error = error_msg
        )
    
    # Save to candidates_dict
    candidates_dict[new_filename] = candidate_data
    
    # Save the updated candidates dictionary
    with open(candidates_json_path, 'w', encoding = 'utf-8') as f:
        json.dump(candidates_dict, f, indent = 4)
    
    flash('Candidate created successfully', 'success')
    return redirect(url_for('view_candidate', filename = new_filename))

@app.route('/candidates/view/<path:filename>', methods = ['GET'])
def view_candidate(filename):
    if filename in candidates_dict:
        return render_template(
            'candidate.html', 
            candidate = candidates_dict[filename], 
            filename = filename,
            is_edit_mode = False,
            is_new = False
        )
    elif filename in results_dict and 'cleaned_data' in results_dict[filename]:
        candidate_data = results_dict[filename]['cleaned_data'].copy()
        candidate_data['date_processed'] = results_dict[filename]['date_processed']
        return render_template(
            'candidate.html', 
            candidate = candidate_data, 
            filename = filename,
            is_edit_mode = False,
            is_new = False
        )
    else:
        flash('Candidate not found', 'danger')
        return redirect(url_for('results'))

@app.route('/candidates/edit/<path:filename>', methods = ['GET'])
def edit_candidate(filename):
    if filename in candidates_dict:
        return render_template(
            'candidate.html', 
            candidate = candidates_dict[filename], 
            filename = filename,
            is_edit_mode = True,
            is_new = False
        )
    elif filename in results_dict and 'cleaned_data' in results_dict[filename]:
        candidate_data = results_dict[filename]['cleaned_data'].copy()
        candidate_data['date_processed'] = results_dict[filename]['date_processed']
        return render_template(
            'candidate.html', 
            candidate = candidate_data, 
            filename = filename,
            is_edit_mode = True,
            is_new = False
        )
    else:
        flash('Candidate not found', 'danger')
        return redirect(url_for('results'))

@app.route('/candidates/extract/<path:filename>', methods = ['GET'])
def extract_candidate(filename):
    if filename not in results_dict:
        flash('Document not found', 'danger')
        return redirect(url_for('results'))
    
    if filename in candidates_dict:
        flash('Candidate already exists', 'info')
        return redirect(url_for('view_candidate', filename = filename))
    
    try:
        # Get the raw text from results_dict
        raw_text = results_dict[filename]['formatted_text']
        if not raw_text:
            flash('No text content found in document', 'danger')
            return redirect(url_for('results'))
        
        # Call the LLM API to extract structured data
        structured_data = extract_structured_data(raw_text)
        
        # Format the extracted data to match our data structure
        extracted_data = {
            'first_name': structured_data.get('first_name', ''),
            'middle_name': structured_data.get('middle_name', ''),
            'last_name': structured_data.get('last_name', ''),
            'contact_numbers': structured_data.get('contact_numbers', []),
            'email_ids': structured_data.get('email_ids', []),
            'education': structured_data.get('education', {
                'class_12': '',
                'college': '',
                'higher_studies': ''
            }),
            'work_experience': structured_data.get('work_experience', ''),
            'skillset': structured_data.get('skillset', []),
            'toolset': structured_data.get('toolset', []),
            'programming_languages': structured_data.get('programming_languages', []),
            'projects': structured_data.get('projects', []),
            'certifications': structured_data.get('certifications', []),
            'relevant_links': structured_data.get('relevant_links', {
                'linkedin': '',
                'github': '',
                'portfolio': '',
                'other': []
            }),
            'date_processed': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Save temporarily in session
        session['temp_extracted_candidate'] = extracted_data
        session['temp_extracted_filename'] = filename
        
        flash('Candidate information extracted successfully', 'success')
        return render_template(
            'candidate.html', 
            candidate = extracted_data,
            filename = filename,
            is_edit_mode = True,
            is_new = False
        )
        
    except Exception as e:
        logger.error(f"Error extracting candidate information: {str(e)}")
        flash(f'Error extracting candidate information: {str(e)}', 'danger')
        return redirect(url_for('results'))

@app.route('/candidates/confirm_extraction', methods = ['POST'])
def confirm_extraction():
    if 'temp_extracted_candidate' not in session or 'temp_extracted_filename' not in session:
        flash('No candidate data to confirm', 'danger')
        return redirect(url_for('results'))
    
    if 'confirm' in request.form:
        extracted_data = session['temp_extracted_candidate']
        filename = session['temp_extracted_filename']
        
        # Validate candidate data
        is_valid, error_msg = validate_candidate_data(extracted_data)
        if not is_valid:
            flash(error_msg, 'danger')
            return render_template(
                'candidate.html',
                candidate = extracted_data,
                filename = filename,
                is_edit_mode = True,
                is_new = False,
                error = error_msg
            )
        
        # Save to candidates_dict
        candidates_dict[filename] = extracted_data
        
        # Save the updated candidates dictionary
        with open(candidates_json_path, 'w', encoding = 'utf-8') as f:
            json.dump(candidates_dict, f, indent = 4)
        
        # Clear session data
        session.pop('temp_extracted_candidate', None)
        session.pop('temp_extracted_filename', None)
        
        flash('Candidate extracted successfully', 'success')
        return redirect(url_for('view_candidate', filename = filename))
    else:
        # User cancelled
        session.pop('temp_extracted_candidate', None)
        session.pop('temp_extracted_filename', None)
        flash('Candidate extraction cancelled', 'info')
        return redirect(url_for('results'))

@app.route('/candidates/save/<path:filename>', methods = ['POST'])
def save_candidate(filename):
    # Process form data into structured candidate data
    candidate_data = process_candidate_form_data(request.form)
    
    # Validate candidate data
    is_valid, error_msg = validate_candidate_data(candidate_data)
    if not is_valid:
        return render_template(
            'candidate.html',
            candidate = candidate_data,
            filename = filename,
            is_edit_mode = True,
            is_new = False,
            error = error_msg
        )
    
    # Save to candidates_dict
    candidates_dict[filename] = candidate_data
    
    # Save the updated candidates dictionary
    with open(candidates_json_path, 'w', encoding = 'utf-8') as f:
        json.dump(candidates_dict, f, indent = 4)
    
    flash('Candidate saved successfully', 'success')
    return redirect(url_for('view_candidate', filename = filename))

@app.route('/candidates/delete/<path:filename>', methods = ['GET'])
def delete_candidate(filename):
    if filename in candidates_dict:
        del candidates_dict[filename]
        with open(candidates_json_path, 'w', encoding = 'utf-8') as f:
            json.dump(candidates_dict, f, indent = 4)
        flash('Candidate deleted successfully', 'success')
    else:
        flash('Candidate not found', 'danger')
    
    return redirect(url_for('results'))

@app.route('/reset', methods = ['POST'])
def reset_data():
    """Reset all data and intermediate files"""
    try:
        # Clear dictionaries
        global results_dict, candidates_dict
        results_dict = {}
        candidates_dict = {}
        
        # Reset JSON files
        with open(results_json_path, 'w', encoding = 'utf-8') as f:
            json.dump({}, f, indent = 4)
            
        with open(candidates_json_path, 'w', encoding = 'utf-8') as f:
            json.dump({}, f, indent = 4)
        
        # Delete all files in results folder except results.json
        for filename in os.listdir(app.config['RESULTS_FOLDER']):
            file_path = os.path.join(app.config['RESULTS_FOLDER'], filename)
            if os.path.isfile(file_path) and filename != 'results.json':
                os.remove(file_path)
        
        # Delete all files in uploads folder
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
        
        flash('All data has been reset successfully', 'success')
    except Exception as e:
        flash(f'Error resetting data: {str(e)}', 'danger')
        logging.error(f"Error resetting data: {str(e)}")
    
    return redirect(url_for('results'))

# Add a helper function to process form data

def process_candidate_form_data(form_data: Dict) -> Dict[str, Any]:
    """Process form data into structured candidate data"""
    
    # Process project data from form arrays
    projects = []
    project_names = form_data.getlist('project_names[]')
    project_descriptions = form_data.getlist('project_descriptions[]')
    project_tech_stacks = form_data.getlist('project_tech_stacks[]')
    
    for i in range(len(project_names)):
        if i < len(project_names) and project_names[i].strip():
            tech_stack = []
            if i < len(project_tech_stacks):
                tech_stack = [item.strip() for item in project_tech_stacks[i].split(',') if item.strip()]
            
            project = {
                'name': project_names[i].strip(),
                'description': project_descriptions[i].strip() if i < len(project_descriptions) else '',
                'tech_stack': tech_stack
            }
            projects.append(project)
    
    # Build structured candidate data
    return {
        'first_name': form_data.get('first_name', '').strip(),
        'middle_name': form_data.get('middle_name', '').strip(),
        'last_name': form_data.get('last_name', '').strip(),
        'contact_numbers': [item.strip() for item in form_data.get('contact_numbers', '').split(',') if item.strip()],
        'email_ids': [item.strip() for item in form_data.get('email_ids', '').split(',') if item.strip()],
        'education': {
            'class_12': form_data.get('education_class_12', '').strip(),
            'college': form_data.get('education_college', '').strip(),
            'higher_studies': form_data.get('education_higher_studies', '').strip()
        },
        'work_experience': form_data.get('work_experience', '').strip(),
        'skillset': [item.strip() for item in form_data.get('skillset', '').split(',') if item.strip()],
        'toolset': [item.strip() for item in form_data.get('toolset', '').split(',') if item.strip()],
        'programming_languages': [item.strip() for item in form_data.get('programming_languages', '').split(',') if item.strip()],
        'projects': projects,
        'certifications': [item.strip() for item in form_data.get('certifications', '').split(',') if item.strip()],
        'relevant_links': {
            'linkedin': form_data.get('linkedin', '').strip(),
            'github': form_data.get('github', '').strip(),
            'portfolio': form_data.get('portfolio', '').strip(),
            'other': [item.strip() for item in form_data.get('other_links', '').split(',') if item.strip()]
        },
        'date_processed': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'source': 'manual'
    }

if __name__ == '__main__':
    app.run(debug = True)
