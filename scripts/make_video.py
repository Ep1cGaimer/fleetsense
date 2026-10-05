from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml

from media_common import PS, ROOT


def command(arguments):
    subprocess.run(arguments, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)


def seconds(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)], capture_output=True, text=True, check=True)
    return float(json.loads(result.stdout)["format"]["duration"])


def stamp(value):
    milliseconds = round(value * 1000)
    hours, rest = divmod(milliseconds, 3600000)
    minutes, rest = divmod(rest, 60000)
    whole_seconds, remainder = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{remainder:03d}"


def main():
    folder = ROOT / "tmp/demo"
    shots = json.loads((folder / "shots.json").read_text(encoding="utf-8"))
    narration = [{"shot": shot["shot"], "text": shot["text"]} for shot in shots]
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs/narration.yaml").write_text(yaml.safe_dump(narration, allow_unicode=True, sort_keys=False), encoding="utf-8")
    voice_error = None
    try:
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        if not voices:
            raise RuntimeError("No SAPI voice is available")
        engine.setProperty("rate", 165)
        engine.setProperty("volume", .95)
        for shot in shots:
            engine.save_to_file(shot["text"], str(folder / (shot["shot"] + ".wav")))
        engine.runAndWait()
        engine.stop()
        if not all((folder / (shot["shot"] + ".wav")).exists() for shot in shots):
            raise RuntimeError("SAPI did not produce every audio segment")
        if any(seconds(folder / (shot["shot"] + ".wav")) <= 0 for shot in shots):
            raise RuntimeError("SAPI produced an empty audio segment")
    except Exception as error:
        voice_error = str(error)
        with (ROOT / "DEVIATIONS.md").open("a", encoding="utf-8") as stream:
            stream.write("\n- Video narration: captions-only fallback. " + voice_error + "\n")
    lengths = []
    for shot in shots:
        audio = folder / (shot["shot"] + ".wav")
        length = seconds(audio) + 1 if voice_error is None else max(12, len(shot["text"].split()) / 2.7)
        lengths.append(length)
    total = sum(lengths)
    if total > 193:
        raise RuntimeError("Narration exceeds the submission duration limit. Shorten generated copy, retaining the result and caveats.")
    segments = []
    offset = 0.0
    captions = []
    for index, (shot, length) in enumerate(zip(shots, lengths)):
        target = folder / (shot["shot"] + ".mp4")
        arguments = ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(shot.get("ready_offset_seconds", 0)), "-i", str(ROOT / shot["path"])]
        if voice_error is None:
            arguments += ["-i", str(folder / (shot["shot"] + ".wav"))]
        else:
            arguments += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        arguments += ["-t", str(length), "-map", "0:v:0", "-map", "1:a:0", "-vf", f"tpad=stop_mode=clone:stop_duration={length},scale=1920:1080,setsar=1", "-r", "30", "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", str(target)]
        command(arguments)
        segments.append(target)
        words = shot["text"].split()
        groups = [" ".join(words[start:start + 16]) for start in range(0, len(words), 16)]
        group_length = length / len(groups)
        for group_index, group in enumerate(groups):
            captions.append(str(len(captions) + 1) + "\n" + stamp(offset + group_index * group_length) + " --> " + stamp(offset + (group_index + 1) * group_length) + "\n" + group + "\n")
        offset += length
    (folder / "captions.srt").write_text("\n".join(captions), encoding="utf-8")
    (folder / "concat.txt").write_text("\n".join("file '" + item.name + "'" for item in segments), encoding="utf-8")
    combined = folder / "combined.mp4"
    command(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(folder / "concat.txt"), "-c", "copy", str(combined)])
    final = ROOT / "submission" / (PS + "_demo.mp4")
    command(["ffmpeg", "-y", "-loglevel", "error", "-i", str(combined), "-vf", "subtitles=tmp/demo/captions.srt:force_style='FontName=Segoe UI,FontSize=22,Outline=2,MarginV=28'", "-c:v", "libx264", "-crf", "20", "-preset", "fast", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(final)])
    manifest = {"duration_seconds": seconds(final), "captions_only": voice_error is not None, "voice_error": voice_error, "shots": [{"shot": shot["shot"], "offset": sum(lengths[:index]), "length": lengths[index]} for index, shot in enumerate(shots)]}
    (ROOT / "results/video_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(final)


if __name__ == "__main__":
    main()
