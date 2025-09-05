import argparse
import json
import os

def process_json_file(input_path, output_path, rate_value):
    with open(input_path, 'r', encoding='utf-8') as infile, open(output_path, 'w', encoding='utf-8') as outfile:
        for line in infile:
            if not line.strip():
                continue

            data = json.loads(line.strip())

            # Extract speaker from original context_text (optional; here hardcoded as Sean)
            original_context = data.get('context_text', '')

            # Build new context_text
            data['context_text'] = f"Rate:{rate_value} | Speaker and Emotion: | Language:en Dataset:RivaTTS Speaker:Sean"

            # Remove 'target_audio_codes_path'
            data.pop('target_audio_codes_path', None)

            # Build new audio_filepath
            original_path = data.get('audio_filepath', '')
            filename = os.path.basename(original_path)
            data['audio_filepath'] = f"/speed/{rate_value}/{filename}"

            outfile.write(json.dumps(data) + '\n')

def process_folder(input_folder, output_folder, rate_value):
    os.makedirs(output_folder, exist_ok=True)

    for filename in os.listdir(input_folder):
        if filename.endswith('.json'):
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, filename)
            process_json_file(input_path, output_path, rate_value)
            print(f"Processed: {filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process JSON files and modify fields.")
    parser.add_argument('input_folder', help="Folder containing input JSON files")
    parser.add_argument('output_folder', help="Folder to save modified JSON files")
    parser.add_argument('rate_value', help="Rate value to insert into context_text and path")

    args = parser.parse_args()
    process_folder(args.input_folder, args.output_folder, args.rate_value)

