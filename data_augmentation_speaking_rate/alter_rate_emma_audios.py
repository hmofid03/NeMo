import os
import subprocess
import argparse

# Speed tags and corresponding atempo values
speed_map = {
  "slow": 0.84,
  "x-slow": 0.78,
  "fast": 1.14,
  "x-fast": 1.3
}


# Speed tags and corresponding atempo values
#speed_map = {
 # "slow": 0.84,
 # "x-slow": 0.78,
  #"fast": 1.14,
 # "x-fast": 1.28
#}




#speed_map = {
 # "x-slow": 0.84,
  #"slow": 0.85,
  #"fast": 1.18,
  #"x-fast": 1.28
#}
def apply_speed(input_path, output_path, speed):
    # FFmpeg supports atempo values between 0.5 and 2.0
    if 0.5 <= speed <= 2.0:
        atempo_filter = f"atempo={speed}"
    else:
        raise ValueError("Speed must be between 0.5 and 2.0 for FFmpeg atempo")

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-filter:a", atempo_filter,
        output_path
    ]
    subprocess.run(cmd, check=True)

def process_folder(input_folder):
    # Get absolute input folder name to build derived folder names
    input_folder = os.path.abspath(input_folder)
    folder_base = os.path.basename(input_folder)

    # Gather all .wav files
    wav_files = [
        f for f in os.listdir(input_folder)
        if f.lower().endswith('.wav') and os.path.isfile(os.path.join(input_folder, f))
    ]

    if not wav_files:
        print("No .wav files found in the input folder.")
        return

    for tag, speed in speed_map.items():
        output_folder = os.path.join(os.path.dirname(input_folder), f"{folder_base}_{tag}")
        os.makedirs(output_folder, exist_ok=True)

        print(f"\n🔧 Processing for speed tag: {tag} ({speed}x)...")
        for filename in wav_files:
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, filename)
            try:
                print(f"   - {filename} → {output_path}")
                apply_speed(input_path, output_path, speed)
            except subprocess.CalledProcessError as e:
                print(f"     ❌ Failed to process {filename}: {e}")

    print("\n✅ All files processed for all speed settings.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply speed variations to all WAV files in a folder using FFmpeg.")
    parser.add_argument("input_folder", help="Path to the folder containing original WAV files")
    args = parser.parse_args()

    process_folder(args.input_folder)

