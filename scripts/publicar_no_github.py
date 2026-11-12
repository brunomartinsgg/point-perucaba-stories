"""
Script automatizado para criar o repositório no GitHub, enviar todos os arquivos
(incluindo as 7 artes e o workflow) e ativar o GitHub Pages usando a credencial
já salva no Git Credential Manager do Windows (sem depender de lockfiles do OneDrive).
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
import subprocess
import sys
from typing import Any
import unicodedata

from PIL import Image
import requests

REPO_OWNER = "brunomartinsgg"
REPO_NAME = "point-perucaba-stories"
GITHUB_API = "https://api.github.com"

BASE_DIR = Path(__file__).resolve().parent.parent

# Pastas e arquivos que não devem ser enviados ao repositório
EXCLUDED_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", "env"}
EXCLUDED_FILES = {".env", "subir_para_github.bat"}

CANONICAL_RENAMES = {
    "Segunda — Bebida favorita.jpg": "segunda.jpg",
    "Terça — Refresque-se.jpg": "terca.jpg",
    "Quarta — Pausa e energia.jpg": "quarta.jpg",
    "Quinta — Prepare o encontro.jpg": "quinta.jpg",
    "Sexta — Sextou.jpg": "sexta.jpg",
    "Sabado — Churrasco e bebida gelada (2).jpg": "sabado.jpg",
    "Sabado — Churrasco e bebida gelada.jpg": "sabado.jpg",
    "Domingo — Churrasco e bebida gelada.jpg": "domingo.jpg",
}

WEEKDAY_KEYWORDS = [
    ("segunda", "segunda.jpg"),
    ("terca", "terca.jpg"),
    ("quarta", "quarta.jpg"),
    ("quinta", "quinta.jpg"),
    ("sexta", "sexta.jpg"),
    ("sabado", "sabado.jpg"),
    ("domingo", "domingo.jpg"),
]

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _resolve_story_filename_and_bytes(path: Path) -> tuple[str, bytes]:
    """
    Mapeia qualquer arte em `assets/stories/` (mesmo com nome descritivo ou extensão .png/.webp)
    para o nome canônico (`segunda.jpg` .. `domingo.jpg`) e garante formato JPEG real para a Meta.
    """
    raw_bytes = path.read_bytes()
    target_name = CANONICAL_RENAMES.get(path.name)

    if not target_name:
        stem_norm = unicodedata.normalize("NFD", path.stem.lower())
        stem_ascii = "".join(c for c in stem_norm if unicodedata.category(c) != "Mn")
        for keyword, canonical in WEEKDAY_KEYWORDS:
            if keyword in stem_ascii:
                target_name = canonical
                break

    if not target_name:
        return path.name, raw_bytes

    # Garante que a imagem esteja em formato JPEG real (converte PNG/WebP automaticamente)
    with Image.open(io.BytesIO(raw_bytes)) as img:
        if (img.format or "").upper() not in {"JPEG", "MPO"}:
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=95)
            raw_bytes = buf.getvalue()
            print(f"[OK] Convertido para JPEG compatível com a Meta: '{path.name}' -> '{target_name}'")

    return target_name, raw_bytes


def normalize_local_story_filenames() -> None:
    """Tenta renomear localmente as 7 artes; se o OneDrive bloquear, o upload já envia com os nomes canônicos."""
    stories_dir = BASE_DIR / "assets" / "stories"
    if not stories_dir.exists():
        return
    for old_name, new_name in CANONICAL_RENAMES.items():
        old_path = stories_dir / old_name
        new_path = stories_dir / new_name
        if old_path.exists() and not new_path.exists():
            try:
                old_path.rename(new_path)
                print(f"[OK] Renomeado: '{old_name}' -> '{new_name}'")
            except OSError:
                pass


def collect_project_files() -> list[tuple[str, bytes]]:
    """Coleta todos os arquivos do projeto para envio direto via API do GitHub com nomes canônicos."""
    files_map: dict[str, bytes] = {}
    for path in sorted(BASE_DIR.rglob("*")):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(BASE_DIR).parts
        if any(part in EXCLUDED_DIRS for part in rel_parts):
            continue
        if path.name in EXCLUDED_FILES or path.suffix in {".pyc", ".pyo", ".tmp"}:
            continue
        rel_posix = path.relative_to(BASE_DIR).as_posix()
        if rel_posix.startswith("assets/stories/") and path.suffix.lower() in IMAGE_EXTENSIONS:
            canonical_name, jpeg_bytes = _resolve_story_filename_and_bytes(path)
            rel_posix = f"assets/stories/{canonical_name}"
            files_map[rel_posix] = jpeg_bytes
        else:
            files_map[rel_posix] = path.read_bytes()
    return sorted(files_map.items())


def get_git_credential_token() -> str | None:
    """Obtém o token do GitHub já autenticado no Git Credential Manager do Windows."""
    try:
        proc = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
        for line in proc.stdout.splitlines():
            if line.startswith("password="):
                return line.split("=", 1)[1].strip()
    except Exception:
        return None
    return None


def ensure_repository_exists(session: requests.Session) -> dict[str, Any]:
    """Verifica se o repositório existe; caso não exista, cria como Público."""
    url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}"
    resp = session.get(url, timeout=20)
    if resp.status_code == 200:
        print(f"[OK] Repositório já existe: https://github.com/{REPO_OWNER}/{REPO_NAME}")
        return resp.json()

    print(f"[1/4] Criando repositório público '{REPO_OWNER}/{REPO_NAME}' no GitHub...")
    create_resp = session.post(
        f"{GITHUB_API}/user/repos",
        json={
            "name": REPO_NAME,
            "description": "Automação diária de Instagram Stories — Point Perucaba",
            "private": False,
            "auto_init": True,
        },
        timeout=30,
    )
    if create_resp.status_code not in {200, 201}:
        raise RuntimeError(
            f"Falha ao criar repositório no GitHub (HTTP {create_resp.status_code}): {create_resp.text}"
        )
    print(f"[OK] Repositório criado com sucesso: https://github.com/{REPO_OWNER}/{REPO_NAME}")
    return create_resp.json()


def upload_all_files_atomic(session: requests.Session) -> None:
    """
    Envia todos os arquivos do projeto e as 7 imagens em um único commit na branch `main`
    via GitHub Git Data API (evita qualquer bloqueio de .git/index.lock pelo OneDrive).
    """
    files = collect_project_files()
    print(f"[2/4] Enviando {len(files)} arquivos (código, testes, workflow e 7 artes) para o GitHub...")

    # Verifica se já existe commit na branch main (ou cria o primeiro via Contents API se o repo estiver vazio)
    ref_url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/git/ref/heads/main"
    ref_resp = session.get(ref_url, timeout=20)

    if ref_resp.status_code == 404 or ref_resp.status_code == 409:
        # Repositório 100% vazio: cria o README inicial via Contents API para inicializar o repositório Git
        init_resp = session.put(
            f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/contents/README.md",
            json={
                "message": "chore: inicializa repositório",
                "content": base64.b64encode(b"# Point Perucaba Stories\n").decode("ascii"),
                "branch": "main",
            },
            timeout=20,
        )
        if init_resp.status_code not in {200, 201}:
            raise RuntimeError(
                f"Erro ao inicializar branch main (HTTP {init_resp.status_code}): {init_resp.text}"
            )
        ref_resp = session.get(ref_url, timeout=20)

    if ref_resp.status_code != 200:
        raise RuntimeError(
            f"Não foi possível obter referência da branch main (HTTP {ref_resp.status_code}): {ref_resp.text}"
        )

    latest_commit_sha = ref_resp.json()["object"]["sha"]

    # Preserva o histórico remoto (data/publication_history.json) caso já exista no GitHub,
    # evitando sobrescrever registros de publicações já feitas pelo GitHub Actions.
    remote_history_sha: str | None = None
    hist_resp = session.get(
        f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/contents/data/publication_history.json",
        params={"ref": "main"},
        timeout=20,
    )
    if hist_resp.status_code == 200:
        remote_history_sha = hist_resp.json().get("sha")

    # Cria um blob para cada arquivo
    tree_items: list[dict[str, Any]] = []
    for idx, (rel_path, raw_bytes) in enumerate(files, start=1):
        if rel_path == "data/publication_history.json" and remote_history_sha:
            print(f"      -> ({idx}/{len(files)}) Preservando {rel_path} remoto no GitHub...")
            tree_items.append(
                {
                    "path": rel_path,
                    "mode": "100644",
                    "type": "blob",
                    "sha": remote_history_sha,
                }
            )
            continue

        print(f"      -> ({idx}/{len(files)}) Enviando {rel_path} ({len(raw_bytes)} bytes)...")
        blob_resp = session.post(
            f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/git/blobs",
            json={
                "content": base64.b64encode(raw_bytes).decode("ascii"),
                "encoding": "base64",
            },
            timeout=60,
        )
        if blob_resp.status_code not in {200, 201}:
            raise RuntimeError(
                f"Falha ao enviar arquivo '{rel_path}' (HTTP {blob_resp.status_code}): {blob_resp.text}"
            )
        blob_sha = blob_resp.json()["sha"]
        tree_items.append(
            {
                "path": rel_path,
                "mode": "100644",
                "type": "blob",
                "sha": blob_sha,
            }
        )

    # Cria a árvore Git completa
    tree_resp = session.post(
        f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/git/trees",
        json={"tree": tree_items},
        timeout=30,
    )
    if tree_resp.status_code not in {200, 201}:
        raise RuntimeError(
            f"Falha ao criar árvore Git (HTTP {tree_resp.status_code}): {tree_resp.text}"
        )
    new_tree_sha = tree_resp.json()["sha"]

    # Cria o commit apontando para a nova árvore
    commit_resp = session.post(
        f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/git/commits",
        json={
            "message": "feat: sistema completo Point Perucaba Stories com as 7 artes oficiais",
            "tree": new_tree_sha,
            "parents": [latest_commit_sha],
        },
        timeout=30,
    )
    if commit_resp.status_code not in {200, 201}:
        raise RuntimeError(
            f"Falha ao registrar commit no GitHub (HTTP {commit_resp.status_code}): {commit_resp.text}"
        )
    new_commit_sha = commit_resp.json()["sha"]

    # Endpoint de atualização de referência na API do GitHub utiliza '/git/refs/' (no plural)
    update_refs_url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/git/refs/heads/main"
    update_ref_resp = session.patch(
        update_refs_url,
        json={"sha": new_commit_sha, "force": True},
        timeout=20,
    )

    if update_ref_resp.status_code != 200:
        # Caso o token OAuth não possua o escopo 'workflow' para gravar .github/workflows via API,
        # publica os 31 arquivos principais primeiro para não bloquear o envio.
        print(
            "[AVISO] Token sem escopo 'workflow' direto na árvore; enviando arquivos principais e workflow separadamente..."
        )
        tree_without_wf = [t for t in tree_items if not t["path"].startswith(".github/")]
        tree_resp2 = session.post(
            f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/git/trees",
            json={"tree": tree_without_wf},
            timeout=30,
        )
        commit_resp2 = session.post(
            f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/git/commits",
            json={
                "message": "feat: sistema completo Point Perucaba Stories com as 7 artes oficiais",
                "tree": tree_resp2.json()["sha"],
                "parents": [latest_commit_sha],
            },
            timeout=30,
        )
        update_ref_resp = session.patch(
            update_refs_url,
            json={"sha": commit_resp2.json()["sha"], "force": True},
            timeout=20,
        )
        if update_ref_resp.status_code != 200:
            raise RuntimeError(
                f"Falha ao atualizar branch main (HTTP {update_ref_resp.status_code}): {update_ref_resp.text}"
            )

        # Tenta publicar o workflow via Contents API
        wf_path = BASE_DIR / ".github" / "workflows" / "daily-story.yml"
        if wf_path.exists():
            wf_resp = session.put(
                f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/contents/.github/workflows/daily-story.yml",
                json={
                    "message": "ci: adiciona workflow daily-story.yml",
                    "content": base64.b64encode(wf_path.read_bytes()).decode("ascii"),
                    "branch": "main",
                },
                timeout=20,
            )
            if wf_resp.status_code in {200, 201}:
                print("[OK] Workflow .github/workflows/daily-story.yml enviado com sucesso!")
            else:
                print(
                    "[AVISO] O token do Git Windows não tem permissão 'workflow' para criar "
                    "'.github/workflows/daily-story.yml' via API. Você poderá colá-lo em 1 clique na interface web."
                )

    print(f"[OK] Arquivos publicados na branch 'main' com sucesso!")


def enable_github_pages(session: requests.Session) -> None:
    """Ativa o GitHub Pages automaticamente na branch `main` (`/`)."""
    print("[3/4] Ativando GitHub Pages (branch: main, pasta: /)...")
    pages_url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/pages"
    get_resp = session.get(pages_url, timeout=20)
    if get_resp.status_code == 200:
        print(
            f"[OK] GitHub Pages já está ativo: https://{REPO_OWNER}.github.io/{REPO_NAME}/"
        )
        return

    post_resp = session.post(
        pages_url,
        json={"source": {"branch": "main", "path": "/"}},
        timeout=20,
    )
    if post_resp.status_code in {200, 201, 409}:
        print(
            f"[OK] GitHub Pages ativado com sucesso: https://{REPO_OWNER}.github.io/{REPO_NAME}/"
        )
    else:
        print(
            f"[AVISO] Não foi possível ativar o Pages via API (HTTP {post_resp.status_code}). "
            f"Você pode ativar em: https://github.com/{REPO_OWNER}/{REPO_NAME}/settings/pages"
        )


def main() -> int:
    print("============================================================================")
    print("  POINT PERUCABA STORIES — IMPLANTAÇÃO AUTOMÁTICA NO GITHUB")
    print("============================================================================")

    token = get_git_credential_token()
    if not token:
        print(
            "[ERRO] Não foi possível localizar a credencial do GitHub no Git Credential Manager."
        )
        return 1

    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )

    try:
        normalize_local_story_filenames()
        ensure_repository_exists(session)
        upload_all_files_atomic(session)
        enable_github_pages(session)
    except Exception as exc:
        print(f"\n[ERRO] {exc}")
        return 1

    print("\n============================================================================")
    print("  [4/4] TUDO PRONTO NO GITHUB!")
    print(f"  Repositório:  https://github.com/{REPO_OWNER}/{REPO_NAME}")
    print(
        f"  GitHub Pages: https://{REPO_OWNER}.github.io/{REPO_NAME}/assets/stories/"
    )
    print(
        f"  Secrets Meta: https://github.com/{REPO_OWNER}/{REPO_NAME}/settings/secrets/actions"
    )
    print("============================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
