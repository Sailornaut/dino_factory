"""Video assembler implementations using ffmpeg."""

import subprocess
import tempfile
from pathlib import Path

from providers.base import VideoAssembler
from utils.logging import get_logger

logger = get_logger(__name__)

WIDTH = 1080
HEIGHT = 1920
FPS = 30


class FFmpegAssembler(VideoAssembler):
    """Assembles vertical Shorts using ffmpeg directly."""

    def assemble(
        self,
        image_paths: list[Path],
        scene_durations: list[float],
        audio_path: Path | None,
        captions_path: Path | None,
        output_path: Path,
        music_path: Path | None = None,
        title_text: str = "",
        outro_text: str = "Which dino should we explore next?",
        fps: int = FPS,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        segments = []
        tmp_dir = Path(tempfile.mkdtemp(prefix="dino_vid_"))

        try:
            # Title card
            if title_text:
                title_path = tmp_dir / "title.mp4"
                self._make_text_card(title_text, title_path, duration=3.0,
                                     bg_color="0x2196F3", fps=fps)
                segments.append(title_path)

            # Scene segments (simple scale, fast)
            for i, (img_path, dur) in enumerate(zip(image_paths, scene_durations)):
                seg_path = tmp_dir / f"scene_{i:03d}.mp4"
                if img_path.exists() and img_path.stat().st_size > 100:
                    self._make_scene_clip(img_path, seg_path, dur, fps=fps)
                else:
                    self._make_text_card(f"Scene {i+1}", seg_path, dur, fps=fps)
                segments.append(seg_path)

            # Outro card
            if outro_text:
                outro_path = tmp_dir / "outro.mp4"
                self._make_text_card(outro_text, outro_path, duration=4.0,
                                     bg_color="0x4CAF50", fps=fps)
                segments.append(outro_path)

            if not segments:
                logger.error("No segments to concatenate")
                return output_path

            # Verify all segments exist
            segments = [s for s in segments if s.exists() and s.stat().st_size > 0]
            if not segments:
                logger.error("All video segments failed to render")
                return output_path

            # Concat all segments
            concat_list = tmp_dir / "concat.txt"
            with open(concat_list, "w") as f:
                for seg in segments:
                    f.write(f"file '{seg}'\n")

            # Build final video
            cmd = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(concat_list),
            ]

            if audio_path and audio_path.exists():
                cmd += ["-i", str(audio_path)]
                cmd += ["-map", "0:v", "-map", "1:a", "-shortest"]
            else:
                cmd += ["-an"]

            cmd += [
                "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k",
                str(output_path),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                logger.error("ffmpeg concat error: %s", result.stderr[-300:] if result.stderr else "")
                # Fallback: no audio
                cmd_fb = [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(concat_list), "-an",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    str(output_path),
                ]
                subprocess.run(cmd_fb, capture_output=True, text=True, timeout=120)

            logger.info("Video assembled: %s (%.1f KB)", output_path,
                        output_path.stat().st_size / 1024 if output_path.exists() else 0)
            return output_path

        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _make_scene_clip(self, img_path: Path, output: Path, duration: float, fps: int = 30):
        """Create a video clip from a still image (fast, no zoom)."""
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(img_path),
            "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:black",
            "-t", str(duration),
            "-r", str(fps),
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-an",
            str(output),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            logger.warning("Scene clip failed: %s", result.stderr[-200:] if result.stderr else "")

    def _make_text_card(
        self, text: str, output: Path, duration: float = 3.0,
        bg_color: str = "0x212121", fps: int = 30,
    ):
        """Generate a text card video using ffmpeg drawtext."""
        safe_text = text.replace("'", "").replace(":", " -").replace("%", " pct")

        font_arg = ""
        font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        if font_path.exists():
            font_arg = f":fontfile={font_path}"

        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c={bg_color}:s={WIDTH}x{HEIGHT}:d={duration}:r={fps}",
            "-vf", (
                f"drawtext=text='{safe_text}'"
                f":fontsize=52:fontcolor=white"
                f":x=(w-text_w)/2:y=(h-text_h)/2"
                f"{font_arg}"
            ),
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-an",
            str(output),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            # Ultra-fallback: just a color clip
            cmd_fb = [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", f"color=c={bg_color}:s={WIDTH}x{HEIGHT}:d={duration}:r={fps}",
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-an", str(output),
            ]
            subprocess.run(cmd_fb, capture_output=True, text=True, timeout=30)


def create_video_assembler(cfg: dict) -> VideoAssembler:
    """Factory function."""
    return FFmpegAssembler()
