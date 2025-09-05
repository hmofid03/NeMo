import os
import json
import random
from pathlib import Path
from pydub import AudioSegment
from collections import defaultdict
import argparse

def concat_with_pause(clips, pause_duration_ms):
    """Concatenate audio clips with a pause of specified duration between them."""
    pause = AudioSegment.silent(duration=pause_duration_ms)
    combined = clips[0]
    for clip in clips[1:]:
        combined += pause + clip
    return combined

def total_duration(clips, pause_ms, num_pauses):
    """Calculate total duration of concatenated clips with pauses."""
    clip_duration = sum(c.duration_seconds for c in clips)
    pause_duration = (pause_ms * num_pauses) / 1000.0
    return clip_duration + pause_duration

def get_filename_from_path(path):
    """Extract filename without extension from a path."""
    return Path(path).stem

def generate_pause_dataset(manifest_path, audio_root, output_root, max_duration=20.0):
    """Generate dataset with varied pauses based on specified strategy."""
    print(f"Loading manifest from {manifest_path}...")
    manifest_path = Path(manifest_path)
    with open(manifest_path, "r") as f:
        original_lines = [json.loads(l) for l in f]
    
    print(f"Found {len(original_lines)} entries in original manifest")
    
    # Create output directory
    output_root = Path(output_root)
    output_root.mkdir(exist_ok=True, parents=True)
    
    # Define pause configurations
    pause_configs = [
        {"name": "short", "duration_ms": 600},
        {"name": "medium", "duration_ms": 1000},
        {"name": "long", "duration_ms": 1300}
    ]
    
    # Define reuse strategy per number of pauses
    reuse_strategy = {
        1: 1,  # No reuse for 1-pause samples
        2: 2,  # Up to 2 uses for 2-pause samples
        3: 3   # Up to 3 uses for 3-pause samples
    }
    
    # Group clips by emotion for easier matching
    clips_by_emotion = defaultdict(list)
    for i, line in enumerate(original_lines):
        emotion = line.get("emotion", "")
        clips_by_emotion[emotion].append(i)
    
    # Track global clip usage for statistics only
    global_clip_usage = defaultdict(int)
    
    # Store all generated entries for combined manifest
    all_entries = []
    
    # Also store entries by pause type for type-specific combined manifests
    entries_by_type = {
        "short": [],
        "medium": [],
        "long": []
    }
    
    # For statistics tracking only
    stats_by_config = defaultdict(int)
    
    # Process each pause configuration
    for config in pause_configs:
        pause_name = config["name"]
        pause_ms = config["duration_ms"]
        
        print(f"\n=== Processing {pause_name.upper()} pauses ===")
        
        # Reset usage counters for each pause type
        pause_type_clip_usage = defaultdict(int)
        
        # Create audio output directory for this pause type
        audio_output_dir = output_root / f"{pause_name}_pause"
        audio_output_dir.mkdir(exist_ok=True)
        
        # For each number of pauses (1, 2, 3)
        for num_pauses in [1, 2, 3]:
            # Define the pause count directory name (for manifest paths only)
            pause_count_dir = f"{num_pauses}_pause_per"
            
            # Create directory for this pause count - THIS IS THE FIRST NEW LINE
            pause_count_path = audio_output_dir / pause_count_dir
            pause_count_path.mkdir(exist_ok=True)
            
            print(f"\nGenerating {pause_name} pause manifest with {num_pauses} pauses...")
            
            # Number of clips needed for this configuration
            clips_needed = num_pauses + 1
            
            # Maximum reuse for this configuration
            max_reuse = reuse_strategy[num_pauses]
            
            # Create new manifest for this specific configuration
            manifest_entries = []
            
            # Track clip usage for this specific configuration
            config_clip_usage = defaultdict(int)
            
            # Counter for generated samples
            samples_generated = 0
            
            # For random sampling approach
            attempts = 0
            max_attempts = len(original_lines) * 10  # Limit attempts to avoid infinite loops
            
            while attempts < max_attempts and samples_generated < (len(original_lines) // clips_needed):
                attempts += 1
                
                # First, select a random emotion that has enough clips
                valid_emotions = [
                    emotion for emotion, indices in clips_by_emotion.items()
                    if len(indices) >= clips_needed
                ]
                
                if not valid_emotions:
                    print("No emotions with enough clips available")
                    break
                
                emotion = random.choice(valid_emotions)
                emotion_indices = clips_by_emotion[emotion]
                
                # Try to find clips with matching emotion that haven't exceeded reuse limit
                selected_indices = []
                candidate_indices = list(emotion_indices)
                random.shuffle(candidate_indices)
                
                for idx in candidate_indices:
                    clip_path = original_lines[idx]["audio_path"]
                    
                    # Skip if this clip has reached its reuse limit FOR THIS PAUSE TYPE
                    if (pause_type_clip_usage[clip_path] >= max_reuse or 
                        config_clip_usage[clip_path] >= max_reuse):
                        continue
                    
                    # Skip if duration is too long (to ensure combined duration < max_duration)
                    if original_lines[idx].get("duration", 0) > (max_duration / clips_needed):
                        continue
                    
                    selected_indices.append(idx)
                    
                    # Break once we have enough clips
                    if len(selected_indices) == clips_needed:
                        break
                
                # Skip if we couldn't find enough clips
                if len(selected_indices) < clips_needed:
                    continue
                
                # Randomly shuffle the selected indices to avoid position patterns
                random.shuffle(selected_indices)
                
                # Load selected clips
                try:
                    selected_items = [original_lines[idx] for idx in selected_indices]
                    selected_clips = []
                    
                    for item in selected_items:
                        # Try different ways to locate the audio file
                        audio_file = Path(item["audio_path"]).name
                        possible_paths = [
                            Path(audio_root) / audio_file,
                            Path(audio_root) / item["audio_path"],
                        ]
                        
                        # Handle relative paths
                        if not Path(item["audio_path"]).is_absolute():
                            possible_paths.append(Path(audio_root) / item["audio_path"])
                        
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
                
                # Check if total duration is reasonable (< max_duration seconds)
                if total_duration(selected_clips, pause_ms, num_pauses) > max_duration:
                    continue
                
                # Create combined audio with pauses
                combined_audio = concat_with_pause(selected_clips, pause_ms)
                
                # Generate output filename using original filenames
                original_filenames = [
                    get_filename_from_path(original_lines[idx]["audio_path"])
                    for idx in selected_indices
                ]
                output_filename = f"{pause_name}_pause_".join(original_filenames) + ".wav"
                
                # Ensure filename isn't too long (filesystem limits)
                if len(output_filename) > 200:
                    # Use shorter format if original would be too long
                    output_filename = f"{pause_name}_{num_pauses}pauses_{samples_generated:04d}.wav"
                
                # Full path for output audio file - THIS IS THE SECOND NEW LINE
                output_path = pause_count_path / output_filename
                
                # Export audio
                combined_audio.export(output_path, format="wav")
                
                # Create text with pause markers
                texts = [original_lines[idx]["text"] for idx in selected_indices]
                combined_text = f" <{pause_name}_pause> ".join(texts)
                
                # Randomly choose one source clip for context information
                context_source = random.choice(selected_items)
                
                # Get speaker from context source for manifest path
                speaker = context_source.get("speaker", "unknown")
                
                # Create manifest path (doesn't need to match actual file location)
                # Format: /speaker/pause_type/pause_count/filename.wav
                manifest_audio_path = f"/{speaker}/{pause_name}_pause/{pause_count_dir}/{output_filename}"
                
                # Create manifest entry (without the extra parameters)
                entry = {
                    "audio_path": manifest_audio_path,
                    "text": combined_text,
                    "duration": combined_audio.duration_seconds,
                    "emotion": context_source.get("emotion", ""),
                    "speaker": speaker,
                    "gender": context_source.get("gender", "unknown")
                }
                
                # Add context information from the chosen source clip
                if "context_audio_codes_path" in context_source:
                    entry["context_audio_codes_path"] = context_source["context_audio_codes_path"]
                if "context_audio_duration" in context_source:
                    entry["context_audio_duration"] = context_source["context_audio_duration"]
                if "context_audio_filepath" in context_source:
                    entry["context_audio_filepath"] = context_source["context_audio_filepath"]
                
                manifest_entries.append(entry)
                all_entries.append(entry)
                entries_by_type[pause_name].append(entry)
                samples_generated += 1
                
                # For statistics only
                stats_key = f"{pause_name}_{num_pauses}"
                stats_by_config[stats_key] += 1
                
                # Update usage counters
                for idx in selected_indices:
                    clip_path = original_lines[idx]["audio_path"]
                    global_clip_usage[clip_path] += 1  # For statistics only
                    pause_type_clip_usage[clip_path] += 1  # For this pause type
                    config_clip_usage[clip_path] += 1  # For this specific configuration
            
            # Write manifest for this specific configuration
            manifest_output_path = output_root / f"manifest_{pause_name}_{num_pauses}pauses.json"
            with open(manifest_output_path, "w") as f:
                for entry in manifest_entries:
                    f.write(json.dumps(entry) + "\n")
            
            print(f"Created {len(manifest_entries)} entries in {manifest_output_path}")
    
    # Write combined manifest with all entries
    random.shuffle(all_entries)  # Shuffle to avoid patterns
    combined_path = output_root / "manifest_all_pauses.json"
    with open(combined_path, "w") as f:
        for entry in all_entries:
            f.write(json.dumps(entry) + "\n")
    
    print(f"\nCreated combined manifest with {len(all_entries)} entries at {combined_path}")
    
    # Write pause-type specific combined manifests
    for pause_type, entries in entries_by_type.items():
        random.shuffle(entries)  # Shuffle each type
        type_path = output_root / f"manifest_{pause_type}_all.json"
        with open(type_path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        print(f"Created {pause_type} combined manifest with {len(entries)} entries at {type_path}")
    
    # Print statistics
    print("\n=== Dataset Statistics ===")
    
    # By pause type and count
    print("\nSamples by configuration:")
    for key in sorted(stats_by_config.keys()):
        pause_type, num_pauses = key.split('_')
        print(f"  {pause_type} pauses ({num_pauses}): {stats_by_config[key]} samples")
    
    # By emotion
    emotion_stats = defaultdict(int)
    for entry in all_entries:
        emotion_stats[entry.get("emotion", "")] += 1
    
    print("\nSamples by emotion:")
    for emotion, count in sorted(emotion_stats.items()):
        print(f"  {emotion}: {count} samples")
    
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
    parser = argparse.ArgumentParser(description="Generate TTS training data with varied pauses")
    parser.add_argument("--manifest", required=True, help="Path to original manifest file")
    parser.add_argument("--audio_root", required=True, help="Directory containing audio files")
    parser.add_argument("--output_root", required=True, help="Output directory for generated files")
    parser.add_argument("--max_duration", type=float, default=20.0, help="Maximum duration in seconds for generated samples")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    
    args = parser.parse_args()
    
    # Set random seed for reproducibility
    random.seed(args.seed)
    
    # Generate the dataset
    generate_pause_dataset(
        manifest_path=args.manifest,
        audio_root=args.audio_root,
        output_root=args.output_root,
        max_duration=args.max_duration
    )

