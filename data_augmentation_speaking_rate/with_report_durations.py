import os
import json
import wave
import contextlib
import argparse

def get_wav_duration(wav_path):
    try:
        with contextlib.closing(wave.open(wav_path, 'r')) as f:
            frames = f.getnframes()
            rate = f.getframerate()
            return frames / float(rate)
    except (wave.Error, FileNotFoundError):
        return None

def fix_json_durations(input_json_path, output_json_path, threshold=0.01):
    file_stats = {
        "filename": os.path.basename(input_json_path),
        "lines": 0,
        "updated": 0,
        "missing": 0,
        "unreadable": 0
    }

    with open(input_json_path, 'r', encoding='utf-8') as infile, \
         open(output_json_path, 'w', encoding='utf-8') as outfile:

        for line_num, line in enumerate(infile, 1):
            line = line.strip()
            if not line:
                continue

            file_stats["lines"] += 1
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue  # Skip invalid lines silently

            audio_path = data.get("audio_path")
            if not audio_path:
                file_stats["missing"] += 1
                outfile.write(json.dumps(data, ensure_ascii=False) + '\n')
                continue

            # Strip leading "/speed/" if present
            if audio_path.startswith("/speed/"):
                cleaned_path = audio_path[len("/speed/"):]
            else:
                cleaned_path = audio_path.lstrip("/")

            if not os.path.isfile(cleaned_path):
                file_stats["missing"] += 1
                outfile.write(json.dumps(data, ensure_ascii=False) + '\n')
                continue

            actual_duration = get_wav_duration(cleaned_path)
            if actual_duration is None:
                file_stats["unreadable"] += 1
                outfile.write(json.dumps(data, ensure_ascii=False) + '\n')
                continue

            old_duration = data.get("duration")
            try:
                old_duration = float(old_duration)
            except (TypeError, ValueError):
                old_duration = None

            if old_duration is None or abs(actual_duration - old_duration) > threshold:
                data["duration"] = round(actual_duration, 3)
                file_stats["updated"] += 1

            outfile.write(json.dumps(data, ensure_ascii=False) + '\n')

    return file_stats

def process_all_jsons(input_folder, output_folder, report_path="summary_report.txt", threshold=0.01):
    os.makedirs(output_folder, exist_ok=True)
    all_stats = []

    for filename in os.listdir(input_folder):
        if not filename.endswith('.json'):
            continue

        input_path = os.path.join(input_folder, filename)
        output_path = os.path.join(output_folder, filename)

        print(f"🔧 Processing: {filename}")
        stats = fix_json_durations(input_path, output_path, threshold=threshold)
        all_stats.append(stats)

    # Write summary report
    with open(report_path, 'w', encoding='utf-8') as report_file:
        report_file.write("Duration Fix Summary Report\n")
        report_file.write("=" * 40 + "\n")
        for stat in all_stats:
            report_file.write(
                f"{stat['filename']}\n"
                f"  Lines processed : {stat['lines']}\n"
                f"  Durations fixed : {stat['updated']}\n"
                f"  Missing files   : {stat['missing']}\n"
                f"  Unreadable files: {stat['unreadable']}\n\n"
            )
        report_file.write("✅ Done.\n")

    print(f"\n📄 Summary report saved to: {report_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix 'duration' values in JSON files based on actual WAV durations.")
    parser.add_argument("input_folder", help="Folder containing original JSON files")
    parser.add_argument("output_folder", help="Folder to save updated JSON files")
    parser.add_argument("--threshold", type=float, default=0.01, help="Minimum duration difference (in seconds) to trigger update")
    parser.add_argument("--report", default="summary_report.txt", help="Path to save the summary report")

    args = parser.parse_args()

    process_all_jsons(
        args.input_folder,
        args.output_folder,
        report_path=args.report,
        threshold=args.threshold
    )

