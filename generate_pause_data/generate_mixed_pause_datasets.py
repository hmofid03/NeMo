import os
import json
import random
from pathlib import Path
from pydub import AudioSegment
from collections import defaultdict
import argparse
from itertools import permutations

def get_all_pause_combinations(num_pauses):
    """Generate all possible pause type combinations and orderings."""
    pause_types = ["short", "medium", "long"]
    all_combinations = []
    
    if num_pauses == 2:
        # Generate all 2-pause combinations with different types
        for type1 in pause_types:
            for type2 in pause_types:
                if type1 != type2:
                    all_combinations.append([type1, type2])
    elif num_pauses == 3:
        # Generate all 3-pause combinations with at least two different types
        for perm in permutations(pause_types * 2, num_pauses):
            if len(set(perm)) >= 2:  # Ensure at least two different types
                all_combinations.append(list(perm))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_combinations = []
    for combo in all_combinations:
        combo_tuple = tuple(combo)
        if combo_tuple not in seen:
            seen.add(combo_tuple)
            unique_combinations.append(combo)
    
    return unique_combinations

def concat_with_mixed_pauses(clips, pause_types):
    """Concatenate clips with different types of pauses between them."""
    pause_durations = {
        "short": 600,
        "medium": 1000,
        "long": 1300
    }
    
    combined = clips[0]
    for i, clip in enumerate(clips[1:]):
        pause_type = pause_types[i]
        pause = AudioSegment.silent(duration=pause_durations[pause_type])
        combined += pause + clip
    return combined

def total_duration(clips, pause_types):
    """Calculate total duration with varied pause types."""
    pause_durations = {
        "short": 600,
        "medium": 1000,
        "long": 1300
    }
    clip_duration = sum(c.duration_seconds for c in clips)
    pause_duration = sum(pause_durations[ptype] for ptype in pause_types) / 1000.0
    return clip_duration + pause_duration

def get_filename_from_path(path):
    """Extract filename without extension from a path."""
    return Path(path).stem

def get_pause_sequence_from_text(text):
    """Extract pause sequence from text in order of appearance."""
    sequence = []
    parts = text.split("<")
    for part in parts[1:]:  # Skip first part (before first pause)
        pause_type = part.split("_pause>")[0]
        sequence.append(pause_type)
    return sequence

def generate_mixed_pause_dataset(manifest_path, audio_root, output_root, max_duration=20.0):
    """Generate dataset with mixed pause types (2 and 3 pauses only)."""
    print(f"Loading manifest from {manifest_path}...")
    manifest_path = Path(manifest_path)
    with open(manifest_path, "r") as f:
        original_lines = [json.loads(l) for l in f]
    
    print(f"Found {len(original_lines)} entries in original manifest")
    
    # Create output directory
    output_root = Path(output_root)
    output_root.mkdir(exist_ok=True, parents=True)
    
    # Define reuse strategy per number of pauses
    reuse_strategy = {
        2: 2,  # Up to 2 uses for 2-pause samples
        3: 3   # Up to 3 uses for 3-pause samples
    }
    
    # Track global clip usage
    global_clip_usage = defaultdict(int)
    
    # Store all generated entries
    all_entries = []
    
    # Create audio output directory for mixed pauses
    audio_output_dir = output_root / "mixed_pause"
    audio_output_dir.mkdir(exist_ok=True)
    
    # For each number of pauses (2, 3 only)
    for num_pauses in [2, 3]:
        print(f"\nGenerating mixed pause manifest with {num_pauses} pauses...")
        
        # Get all possible pause combinations for this number of pauses
        all_combinations = get_all_pause_combinations(num_pauses)
        print(f"Generated {len(all_combinations)} possible pause combinations")
        
        # Number of clips needed for this configuration
        clips_needed = num_pauses + 1
        
        # Maximum reuse for this configuration
        max_reuse = reuse_strategy[num_pauses]
        
        # Create new manifest for this specific configuration
        manifest_entries = []
        
        # Track clip usage for this specific configuration
        config_clip_usage = defaultdict(int)
        
        # Try to generate samples for each combination
        for pause_combination in all_combinations:
            print(f"Processing combination: {' → '.join(pause_combination)}")
            
            # Counter for generated samples with this combination
            samples_generated = 0
            target_samples = len(original_lines) // (clips_needed * len(all_combinations))
            
            # For random sampling approach
            attempts = 0
            max_attempts = len(original_lines) * 5
            
            while attempts < max_attempts and samples_generated < target_samples:
                attempts += 1
                
                # Group clips by emotion for matching
                emotion_groups = defaultdict(list)
                for idx, line in enumerate(original_lines):
                    clip_path = line["audio_path"]
                    if (global_clip_usage[clip_path] < max_reuse and 
                        config_clip_usage[clip_path] < max_reuse):
                        emotion_groups[line.get("emotion", "")].append(idx)
                
                # Find emotions with enough clips
                valid_emotions = [
                    emotion for emotion, indices in emotion_groups.items()
                    if len(indices) >= clips_needed
                ]
                
                if not valid_emotions:
                    break
                
                # Select a random emotion and get its clips
                emotion = random.choice(valid_emotions)
                available_indices = emotion_groups[emotion]
                
                # Randomly select clips from this emotion
                if len(available_indices) < clips_needed:
                    continue
                    
                selected_indices = random.sample(available_indices, clips_needed)
                
                # Load selected clips
                try:
                    selected_items = [original_lines[idx] for idx in selected_indices]
                    selected_clips = []
                    
                    for item in selected_items:
                        audio_file = Path(item["audio_path"]).name
                        possible_paths = [
                            Path(audio_root) / audio_file,
                            Path(audio_root) / item["audio_path"],
                        ]
                        
                        found = False
                        for path in possible_paths:
                            if path.exists():
                                clip = AudioSegment.from_file(path)
                                selected_clips.append(clip)
                                found = True
                                break
                        
                        if not found:
                            raise FileNotFoundError(f"Could not find audio file: {item['audio_path']}")
                    
                except Exception as e:
                    print(f"Error loading audio: {e}")
                    continue
                
                # Check total duration
                if total_duration(selected_clips, pause_combination) > max_duration:
                    continue
                
                # Create combined audio with mixed pauses
                combined_audio = concat_with_mixed_pauses(selected_clips, pause_combination)
                
                # Generate output filename
                pause_type_str = "_".join(pause_combination)
                original_filenames = [get_filename_from_path(original_lines[idx]["audio_path"]) 
                                    for idx in selected_indices]
                output_filename = f"mixed_{'_'.join(original_filenames)}_{pause_type_str}.wav"
                
                # Ensure filename isn't too long
                if len(output_filename) > 200:
                    output_filename = f"mixed_{num_pauses}pauses_{samples_generated:04d}_{pause_type_str}.wav"
                
                # Full path for output audio file
                output_path = audio_output_dir / output_filename
                
                # Export audio
                combined_audio.export(output_path, format="wav")
                
                # Create text with mixed pause markers
                texts = [original_lines[idx]["text"] for idx in selected_indices]
                combined_text = texts[0]
                for i, (text, pause_type) in enumerate(zip(texts[1:], pause_combination)):
                    combined_text += f" <{pause_type}_pause> {text}"
                
                # Randomly choose one source clip for context information
                context_source = random.choice(selected_items)
                
                # Get speaker from context source
                speaker = context_source.get("speaker", "unknown")
                
                # Create manifest entry
                entry = {
                    "audio_path": f"mixed_pause/{output_filename}",
                    "text": combined_text,
                    "duration": combined_audio.duration_seconds,
                    "emotion": context_source.get("emotion", ""),
                    "speaker": speaker,
                    "gender": context_source.get("gender", "unknown")
                }
                
                # Add context information from chosen source clip
                if "context_audio_codes_path" in context_source:
                    entry["context_audio_codes_path"] = context_source["context_audio_codes_path"]
                if "context_audio_duration" in context_source:
                    entry["context_audio_duration"] = context_source["context_audio_duration"]
                if "context_audio_filepath" in context_source:
                    entry["context_audio_filepath"] = context_source["context_audio_filepath"]
                
                manifest_entries.append(entry)
                all_entries.append(entry)
                samples_generated += 1
                
                # Update usage counters
                for idx in selected_indices:
                    clip_path = original_lines[idx]["audio_path"]
                    global_clip_usage[clip_path] += 1
                    config_clip_usage[clip_path] += 1
        
        # Write manifest for this number of pauses
        manifest_output_path = output_root / f"manifest_mixed_{num_pauses}pauses.json"
        with open(manifest_output_path, "w") as f:
            for entry in manifest_entries:
                f.write(json.dumps(entry) + "\n")
        
        print(f"Created {len(manifest_entries)} entries in {manifest_output_path}")
    
    # Write combined manifest with all entries
    random.shuffle(all_entries)
    combined_path = output_root / "manifest_mixed_all.json"
    with open(combined_path, "w") as f:
        for entry in all_entries:
            f.write(json.dumps(entry) + "\n")
    
    print(f"\nCreated combined manifest with {len(all_entries)} entries")
    
    # Print statistics
    print("\n=== Dataset Statistics ===")
    
    # By exact pause sequences
    pause_sequence_stats = defaultdict(int)
    pause_combo_stats = defaultdict(int)
    
    for entry in all_entries:
        # Get pause sequence in order of appearance
        pause_sequence = get_pause_sequence_from_text(entry["text"])
        
        # Store both the exact sequence and the combination
        sequence_key = " → ".join(pause_sequence)  # Shows exact order
        combo_key = tuple(sorted(pause_sequence))  # For grouping similar combinations
        
        pause_sequence_stats[sequence_key] += 1
        pause_combo_stats[combo_key] += 1
    
    print("\nExact Pause Sequences (showing order):")
    # Group by number of pauses
    sequences_by_count = defaultdict(list)
    for sequence, count in pause_sequence_stats.items():
        num_pauses = len(sequence.split(" → "))
        sequences_by_count[num_pauses].append((sequence, count))
    
    for num_pauses in sorted(sequences_by_count.keys()):
        print(f"\n{num_pauses}-Pause Sequences:")
        total_sequences = sum(count for _, count in sequences_by_count[num_pauses])
        print(f"Total {num_pauses}-pause samples: {total_sequences}")
        for sequence, count in sorted(sequences_by_count[num_pauses]):
            print(f"  {sequence}: {count} samples")
    
    print("\nPause Combinations (ignoring order):")
    for combo, count in sorted(pause_combo_stats.items()):
        print(f"  {' + '.join(combo)}: {count} samples")
    
    # Reuse statistics
    reuse_counts = list(global_clip_usage.values())
    if reuse_counts:
        avg_reuse = sum(reuse_counts) / len(reuse_counts)
        max_reuse = max(reuse_counts)
        reuse_distribution = defaultdict(int)
        for count in reuse_counts:
            reuse_distribution[count] += 1
        
        print("\nClip reuse statistics:")
        print(f"  Average reuse: {avg_reuse:.2f} times")
        print(f"  Maximum reuse: {max_reuse} times")
        print("  Distribution:")
        for count in sorted(reuse_distribution.keys()):
            print(f"    Used {count} times: {reuse_distribution[count]} clips")
    
    return combined_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate TTS training data with mixed pause types")
    parser.add_argument("--manifest", required=True, help="Path to original manifest file")
    parser.add_argument("--audio_root", required=True, help="Directory containing audio files")
    parser.add_argument("--output_root", required=True, help="Output directory for generated files")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    
    args = parser.parse_args()
    
    # Set random seed for reproducibility
    random.seed(args.seed)
    
    # Generate the dataset
    generate_mixed_pause_dataset(
        manifest_path=args.manifest,
        audio_root=args.audio_root,
        output_root=args.output_root
    )

