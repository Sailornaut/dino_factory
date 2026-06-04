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

# Ken Burns: zoom from 100% to ~115% over the clip duration, with a slight pan.
# This is the core "motion" that makes stills feel cinematic.
ZOOM_START = 1.0
ZOOM_END = 1.15


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
            # Title card: first scene image with title text burned on top
            if title_text and image_paths:
                title_img = tmp_dir / "title_card.png"
                self._burn_text_on_image(image_paths[0], title_img, title_text,
                                         position="center", darken=0.55)
                title_path = tmp_dir / "title.mp4"
                self._make_ken_burns_clip(title_img, title_path, duration=3.0, fps=fps,
                                          zoom_start=1.0, zoom_end=1.08)
                segments.append(title_path)

            # Scene segments with Ken Burns motion
            for i, (img_path, dur) in enumerate(zip(image_paths, scene_durations)):
                seg_path = tmp_dir / f"scene_{i:03d}.mp4"
                if img_path.exists() and img_path.stat().st_size > 100:
                    # Alternate zoom direction for variety
                    if i % 2 == 0:
                        self._make_ken_burns_clip(img_path, seg_path, dur, fps=fps,
                                                  zoom_start=ZOOM_START, zoom_end=ZOOM_END)
                    else:
                        self._make_ken_burns_clip(img_path, seg_path, dur, fps=fps,
                                                  zoom_start=ZOOM_END, zoom_end=ZOOM_START)
                else:
                    self._make_color_clip(seg_path, dur, fps=fps)
                segments.append(seg_path)

            # Outro card: last scene image with CTA text
            if outro_text and image_paths:
                outro_img = tmp_dir / "outro_card.png"
                self._burn_text_on_image(image_paths[-1], outro_img, outro_text,
                                         position="center", darken=0.55)
                outro_path = tmp_dir / "outro.mp4"
                self._make_ken_burns_clip(outro_img, outro_path, duration=4.0, fps=fps,
                                          zoom_start=1.08, zoom_end=1.0)
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
                "-c:v", "libx264", "-preset", "fast",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                str(output_path),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                logger.error("ffmpeg concat error: %s", result.stderr[-500:] if result.stderr else "")
                # Fallback: no audio
                cmd_fb = [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(concat_list), "-an",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    str(output_path),
                ]
                subprocess.run(cmd_fb, capture_output=True, text=True, timeout=300)

            logger.info("Video assembled: %s (%.1f KB)", output_path,
                        output_path.stat().st_size / 1024 if output_path.exists() else 0)
            return output_path

        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _make_ken_burns_clip(
        self, img_path: Path, output: Path, duration: float,
        fps: int = 30, zoom_start: float = 1.0, zoom_end: float = 1.15,
    ):
        """Create a video clip with Ken Burns zoom + pan effect."""
        # We need to work at a higher resolution then crop to target.
        # Scale image up, then use zoompan filter.
        # zoompan: z = zoom level over time, d = number of frames
        total_frames = int(duration * fps)

        # zoompan interpolates z from zoom_start to zoom_end across all frames
        # x/y pan toward center as we zoom in
        zp_filter = (
            f"scale=8000:-1,"
            f"zoompan="
            f"z='min({zoom_start}+({zoom_end}-{zoom_start})*on/{total_frames},{zoom_end})':"
            f"x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':"
            f"d={total_frames}:s={WIDTH}x{HEIGHT}:fps={fps},"
            f"setsar=1"
        )

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(img_path),
            "-vf", zp_filter,
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-an",
            str(output),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.warning("Ken Burns clip failed, falling back to static: %s",
                           result.stderr[-300:] if result.stderr else "")
            self._make_static_clip(img_path, output, duration, fps)

    def _make_static_clip(self, img_path: Path, output: Path, duration: float, fps: int = 30):
        """Fallback: simple scale-and-pad static clip."""
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(img_path),
            "-vf", (
                f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
                f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:black"
            ),
            "-t", str(duration),
            "-r", str(fps),
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-an",
            str(output),
        ]
        subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    def _make_color_clip(self, output: Path, duration: float, fps: int = 30):
        """Create a plain dark clip as a last resort."""
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"color=c=0x212121:s={WIDTH}x{HEIGHT}:d={duration}:r={fps}",
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-an", str(output),
        ]
        subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    def _burn_text_on_image(
        self, src_image: Path, out_image: Path,
        text: str, position: str = "center", darken: float = 0.5,
    ):
        """Use Pillow to create an image with text overlay (reliable on all platforms)."""
        try:
            from PIL import Image, ImageDraw, ImageFont

            img = Image.open(str(src_image)).convert("RGB")
            img = img.resize((WIDTH, HEIGHT), Image.LANCZOS)

            # Dark overlay so text is readable
            overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, int(255 * darken)))
            img = img.convert("RGBA")
            img = Image.alpha_composite(img, overlay)
            img = img.convert("RGB")

            draw = ImageDraw.Draw(img)

            # Try to find a good font
            font = self._find_font(size=56)
            small_font = self._find_font(size=32)

            # Word-wrap the text
            lines = self._wrap_text(text, font, draw, max_width=WIDTH - 120)

            if position == "center":
                total_h = sum(draw.textbbox((0, 0), ln, font=font)[3] + 16 for ln in lines)
                y = (HEIGHT - total_h) // 2
            else:
                y = HEIGHT - 300

            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                tw = bbox[2] - bbox[0]
                x = (WIDTH - tw) // 2
                # Text shadow for depth
                draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 180))
                draw.text((x, y), line, font=font, fill="white")
                y += bbox[3] + 16

            img.save(str(out_image), quality=95)

        except Exception as e:
            logger.warning("Text overlay failed, copying original: %s", e)
            import shutil
            shutil.copy2(str(src_image), str(out_image))

    def _find_font(self, size: int = 56):
        """Find a usable font across platforms."""
        from PIL import ImageFont
        # Try common font paths
        candidates = [
            # Windows
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            # Linux
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            # macOS
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFNSDisplay.ttf",
        ]
        for fp in candidates:
            try:
                return ImageFont.truetype(fp, size)
            except (OSError, IOError):
                continue
        return ImageFont.load_default()

    def _wrap_text(self, text: str, font, draw, max_width: int) -> list[str]:
        """Word-wrap text to fit within max_width pixels."""
        words = text.split()
        lines = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines or [text]


def create_video_assembler(cfg: dict) -> VideoAssembler:
    """Factory function."""
    return FFmpegAssembler()
