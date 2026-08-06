"""Build the sub-90-second TARCS-Mem v0.7 demo from verified UI screenshots."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


WIDTH, HEIGHT = 1280, 720
FONT_PATH = Path("/System/Library/Fonts/STHeiti Light.ttc")
BACKGROUND = (19, 17, 68)
PURPLE = (89, 72, 237)
AQUA = (51, 220, 197)
WHITE = (248, 249, 255)
MUTED = (191, 199, 225)


def font(size: int):
    return ImageFont.truetype(str(FONT_PATH), size=size)


def gradient() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    pixels = image.load()
    for x in range(WIDTH):
        ratio = x / WIDTH
        for y in range(HEIGHT):
            vertical = 1 - 0.18 * (y / HEIGHT)
            pixels[x, y] = (
                int((25 + 50 * ratio) * vertical),
                int((20 + 45 * ratio) * vertical),
                int((80 + 115 * ratio) * vertical),
            )
    return image


def centered(draw: ImageDraw.ImageDraw, text: str, y: int, text_font, fill=WHITE) -> None:
    box = draw.textbbox((0, 0), text, font=text_font)
    draw.text(((WIDTH - (box[2] - box[0])) / 2, y), text, font=text_font, fill=fill)


def title_slide(title: str, subtitle: str, eyebrow: str) -> Image.Image:
    image = gradient()
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((80, 68, 1200, 652), radius=42, outline=(118, 110, 255), width=2)
    centered(draw, eyebrow, 150, font(25), AQUA)
    centered(draw, title, 238, font(62))
    centered(draw, subtitle, 340, font(28), MUTED)
    draw.rounded_rectangle((440, 456, 840, 524), radius=34, fill=PURPLE)
    centered(draw, "企业可信记忆治理 · 可追溯 · 有边界", 471, font(24))
    return image


def screenshot_slide(path: Path, heading: str, caption: str) -> Image.Image:
    source = Image.open(path).convert("RGB")
    source = ImageOps.fit(source, (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((0, 560, WIDTH, HEIGHT), fill=(12, 14, 38, 226))
    draw.rounded_rectangle((54, 535, 442, 588), radius=25, fill=PURPLE)
    draw.text((78, 546), heading, font=font(26), fill=WHITE)
    draw.text((64, 610), caption, font=font(24), fill=WHITE)
    return Image.alpha_composite(source.convert("RGBA"), overlay).convert("RGB")


def metrics_slide() -> Image.Image:
    image = gradient()
    draw = ImageDraw.Draw(image)
    draw.text((72, 55), "真实FiQA评测与消融实验", font=font(46), fill=WHITE)
    draw.text((75, 118), "120 queries · 610 documents · 1,000 bootstrap", font=font(24), fill=AQUA)
    rows = [
        ("Lexical", 0.3624, 0.3748, 0.2988, (132, 141, 179)),
        ("Hashed Semantic", 0.2799, 0.3203, 0.2474, (114, 134, 200)),
        ("RRF", 0.4058, 0.4071, 0.3273, (65, 169, 214)),
        ("TARCS", 0.4446, 0.4839, 0.3783, AQUA),
    ]
    draw.text((415, 180), "Recall@10", font=font(22), fill=MUTED)
    draw.text((685, 180), "MRR@10", font=font(22), fill=MUTED)
    draw.text((940, 180), "NDCG@10", font=font(22), fill=MUTED)
    for index, (name, recall, mrr, ndcg, color) in enumerate(rows):
        y = 240 + index * 92
        draw.text((74, y + 10), name, font=font(24), fill=WHITE)
        for x, value in ((415, recall), (685, mrr), (940, ndcg)):
            draw.rounded_rectangle((x, y, x + 205, y + 45), radius=22, fill=(46, 47, 92))
            draw.rounded_rectangle(
                (x, y, x + int(205 * value / 0.55), y + 45), radius=22, fill=color
            )
            draw.text((x + 72, y + 8), f"{value:.4f}", font=font(21), fill=WHITE)
    draw.text(
        (74, 638),
        "可信度提升，同时如实报告P95延迟：15.6ms → 83.7ms",
        font=font(23),
        fill=(244, 194, 103),
    )
    return image


def integrations_slide() -> Image.Image:
    return title_slide(
        "接入现有 Agent，只需一行",
        "MCP v2 · LangChain · LlamaIndex · Confluence · OpenAI-Compatible API",
        "Governed evidence in · auditable answers out",
    )


def build_frames(project: Path, frame_dir: Path) -> list[tuple[Path, int]]:
    assets = project / "docs" / "demo" / "assets"
    slides = [
        (
            title_slide(
                "TARCS-Mem",
                "企业可信记忆治理与对话式RAG Agent",
                "v0.7 Integration Release",
            ),
            8,
        ),
        (
            screenshot_slide(
                assets / "01-home-v07.jpg", "治理闭环", "写入、版本、检索、拒答与审计统一在一个工作台"
            ),
            10,
        ),
        (
            screenshot_slide(
                assets / "02-answer-v07.jpg", "可信问答", "业务日期 · 来源引用 · TARCS裁决 · Trace ID"
            ),
            14,
        ),
        (
            screenshot_slide(
                assets / "03-governance-v07.jpg",
                "企业治理",
                "凭证阻断 · PII脱敏 · 租户/角色ACL · 人工审核",
            ),
            12,
        ),
        (
            screenshot_slide(
                assets / "04-observability-v07.jpg",
                "可观测性",
                "隐私安全的指标、P95延迟和 Trace ID 链路追踪",
            ),
            10,
        ),
        (metrics_slide(), 14),
        (integrations_slide(), 10),
        (
            title_slide(
                "可运行 · 可测试 · 可复现",
                "Tests · MCP v2 · OpenAI API · Docker · GitHub Release",
                "v0.7 Open-source Release",
            ),
            7,
        ),
    ]
    output: list[tuple[Path, int]] = []
    for index, (image, duration) in enumerate(slides, 1):
        path = frame_dir / f"slide-{index:02d}.png"
        image.save(path, optimize=True)
        output.append((path, duration))
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ffmpeg", required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tarcsmem-video-") as temporary:
        frame_dir = Path(temporary)
        frames = build_frames(args.project, frame_dir)
        manifest = frame_dir / "slides.txt"
        lines: list[str] = []
        for path, duration in frames:
            lines.extend([f"file '{path}'", f"duration {duration}"])
        lines.append(f"file '{frames[-1][0]}'")
        manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
        command = [
            args.ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(manifest),
        ]
        if args.audio:
            command.extend(["-i", str(args.audio)])
        command.extend(
            [
                "-t",
                str(sum(duration for _, duration in frames)),
                "-r",
                "30",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
            ]
        )
        if args.audio:
            command.extend(["-c:a", "aac", "-b:a", "160k", "-af", "apad"])
        command.append(str(args.output))
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
