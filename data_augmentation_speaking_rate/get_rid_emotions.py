import os
import json
import argparse

def filter_json_files(input_folder, output_folder):
    os.makedirs(output_folder, exist_ok=True)

    for filename in os.listdir(input_folder):
        if filename.endswith('.json'):
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, filename)

            with open(input_path, 'r', encoding='utf-8') as infile, \
                 open(output_path, 'w', encoding='utf-8') as outfile:

                for line in infile:
                    try:
                        data = json.loads(line)
                        emotion = data.get("emotion")
                        if emotion in ["Additional", "Generic"]:
                            outfile.write(json.dumps(data) + '\n')
                    except json.JSONDecodeError:
                        print(f"Skipping invalid JSON in file {filename}: {line.strip()}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Filter JSON files by 'emotion' key.")
    parser.add_argument("input_folder", help="Path to the input folder containing JSON files")
    parser.add_argument("output_folder", help="Path to the output folder to save filtered JSON files")

    args = parser.parse_args()

    filter_json_files(args.input_folder, args.output_folder)
