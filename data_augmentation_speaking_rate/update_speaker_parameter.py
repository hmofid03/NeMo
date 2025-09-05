import os
import json
import argparse

# Fixed speaker value
FIXED_SPEAKER = "| Language:en Dataset:RivaTTS Speaker:Sean |"

def fix_speaker_field(input_folder):
    # Create output folder name
    output_folder = f"{input_folder}_speaker_fixed"
    os.makedirs(output_folder, exist_ok=True)

    # Iterate through all files in the input folder
    for filename in os.listdir(input_folder):
        if filename.endswith(".json"):
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, filename)

            with open(input_path, 'r', encoding='utf-8') as infile, \
                 open(output_path, 'w', encoding='utf-8') as outfile:
                
                for line in infile:
                    try:
                        # Parse the JSON object per line
                        data = json.loads(line.strip())

                        # Update the speaker field
                        data['speaker'] = FIXED_SPEAKER

                        # Write updated line to output
                        outfile.write(json.dumps(data) + '\n')
                    except json.JSONDecodeError as e:
                        print(f"Skipping line in {filename} due to JSON error: {e}")

    print(f"Finished. Fixed files saved to: {output_folder}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix speaker field in JSON files.")
    parser.add_argument("input_folder", help="Path to folder containing JSON files.")
    args = parser.parse_args()

    fix_speaker_field(args.input_folder)

