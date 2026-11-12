"""Script utilitário para gerar as 7 imagens JPEG iniciais (placeholders 1080x1920) em assets/stories/."""

from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw

DAYS_SPEC: list[tuple[str, str, tuple[int, int, int]]] = [
    ("segunda.jpg", "SEGUNDA-FEIRA — ARTE 01", (25, 45, 85)),
    ("terca.jpg", "TERÇA-FEIRA — ARTE 02", (35, 65, 95)),
    ("quarta.jpg", "QUARTA-FEIRA — ARTE 03", (45, 85, 75)),
    ("quinta.jpg", "QUINTA-FEIRA — ARTE 04", (75, 55, 35)),
    ("sexta.jpg", "SEXTA-FEIRA — ARTE 05", (95, 35, 45)),
    ("sabado.jpg", "SÁBADO — ARTE 06", (85, 45, 95)),
    ("domingo.jpg", "DOMINGO — ARTE 07", (40, 70, 50)),
]


def generate_placeholders(target_dir: Path | None = None) -> list[Path]:
    base_dir = Path(__file__).resolve().parent.parent
    out_dir = target_dir or (base_dir / "assets" / "stories")
    out_dir.mkdir(parents=True, exist_ok=True)

    created: list[Path] = []
    for filename, label, bg_color in DAYS_SPEC:
        file_path = out_dir / filename
        img = Image.new("RGB", (1080, 1920), color=bg_color)
        draw = ImageDraw.Draw(img)
        draw.text(
            (180, 900),
            f"POINT PERUCABA\n\n{label}\n(Substitua por sua arte oficial)",
            fill=(255, 255, 255),
        )
        img.save(file_path, format="JPEG", quality=90)
        created.append(file_path)

    return created


if __name__ == "__main__":
    paths = generate_placeholders()
    print(f"{len(paths)} imagens JPEG geradas com sucesso em: {paths[0].parent}")

