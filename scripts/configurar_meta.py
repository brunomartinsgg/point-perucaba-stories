"""
Assistente interativo local para:
1. Receber o Token da Meta localmente no seu terminal (nunca pelo chat).
2. Descobrir automaticamente o META_IG_USER_ID e o Token da Página via Graph API.
3. Salvar no arquivo .env local (protegido pelo .gitignore).
4. Validar as 7 URLs públicas do GitHub Pages e a autenticação na Meta.
"""

from __future__ import annotations

from pathlib import Path
import sys
import webbrowser

import requests

from src.config import DEFAULT_IMAGE_BASE_URL, DEFAULT_META_API_VERSION
from src.main import main as run_main

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
SECRETS_URL = "https://github.com/brunomartinsgg/point-perucaba-stories/settings/secrets/actions"
EXPLORER_URL = "https://developers.facebook.com/tools/explorer/"


def discover_instagram_account(user_token: str) -> tuple[str, str, str]:
    """
    Descobre automaticamente o ID da conta do Instagram (META_IG_USER_ID) e o username,
    suportando tanto tokens 'IG...' (Instagram Login) quanto 'EAA...' (Facebook Login).
    """
    cleaned = user_token.strip()

    # Caso 1: Token gerado direto pelo Instagram Login (começa com 'IG')
    if cleaned.startswith("IG"):
        url = f"https://graph.instagram.com/{DEFAULT_META_API_VERSION}/me"
        params = {
            "fields": "id,user_id,username",
            "access_token": cleaned,
        }
        resp = requests.get(url, params=params, timeout=20)
        data = resp.json()
        if resp.status_code >= 400 or "error" in data:
            err_msg = data.get("error", {}).get("message", resp.text)
            raise RuntimeError(f"Erro ao consultar conta no Instagram Graph API: {err_msg}")
        ig_id = str(data.get("user_id") or data.get("id"))
        ig_user = str(data.get("username", "desconhecido"))
        print(
            f"[OK] Conta Instagram encontrada via Instagram Login: @{ig_user} (META_IG_USER_ID = {ig_id})"
        )
        return ig_id, ig_user, cleaned

    # Caso 2: Token gerado pelo Facebook Login (começa com 'EAA')
    graph = f"https://graph.facebook.com/{DEFAULT_META_API_VERSION}"
    ig_fields = "instagram_business_account{id,username}"

    def _get(path: str, fields: str | None = None) -> dict:
        params = {"access_token": cleaned}
        if fields:
            params["fields"] = fields
        return requests.get(f"{graph}/{path}", params=params, timeout=20).json()

    # Diagnóstico: identidade e permissões concedidas
    me = _get("me", "id,name")
    if "error" in me:
        raise RuntimeError(f"Token rejeitado pela Meta: {me['error'].get('message')}")
    print(f"[INFO] Token pertence a: {me.get('name')} (ID {me.get('id')})")

    perms = _get("me/permissions")
    granted = sorted(p["permission"] for p in perms.get("data", []) if p.get("status") == "granted")
    declined = sorted(p["permission"] for p in perms.get("data", []) if p.get("status") != "granted")
    print(f"[INFO] Permissões concedidas: {granted}")
    if declined:
        print(f"[AVISO] Permissões recusadas: {declined}")

    # Tentativa A: Páginas diretas do usuário
    pages = _get("me/accounts", f"id,name,access_token,{ig_fields}").get("data", [])

    # Tentativa B: Páginas dentro de Portfólios Empresariais (requer business_management)
    if not pages:
        businesses = _get(
            "me/businesses", f"id,name,owned_pages{{id,name,access_token,{ig_fields}}}"
        ).get("data", [])
        for biz in businesses:
            pages.extend(biz.get("owned_pages", {}).get("data", []))

    print(f"[INFO] Páginas visíveis para o token: {[p.get('name') for p in pages] or 'nenhuma'}")

    for page in pages:
        ig_acc = page.get("instagram_business_account")
        if ig_acc and ig_acc.get("id"):
            ig_id = str(ig_acc["id"])
            ig_user = str(ig_acc.get("username", "desconhecido"))
            page_token = str(page.get("access_token") or cleaned)
            print(
                f"[OK] Instagram encontrado na Página '{page.get('name')}': "
                f"@{ig_user} (META_IG_USER_ID = {ig_id})"
            )
            return ig_id, ig_user, page_token

    required = {"instagram_basic", "instagram_content_publish", "pages_show_list", "pages_read_engagement"}
    missing = sorted(required - set(granted))
    if missing:
        raise RuntimeError(f"Faltam permissões no token: {missing}. Gere o token novamente incluindo-as.")
    if not pages:
        raise RuntimeError(
            "O token não enxerga nenhuma Página do Facebook. Na janela de login da Meta, clique em "
            "'Editar acesso / Editar configurações' e marque a Página do Point Perucaba. "
            "Se a Página está em um Portfólio Empresarial, adicione também a permissão 'business_management'."
        )
    raise RuntimeError(
        "As Páginas foram encontradas, mas nenhuma tem uma conta Instagram Profissional vinculada. "
        "Vincule em: Facebook > sua Página > Configurações > Contas vinculadas > Instagram."
    )


def main() -> int:
    print("============================================================================")
    print("  ASSISTENTE DE CONFIGURAÇÃO META — POINT PERUCABA STORIES")
    print("============================================================================")
    print("1. Testando primeiro se as 7 imagens já estão no ar no seu GitHub Pages...\n")

    rc = run_main(["--verify-setup"])
    if rc == 0:
        print("\n[OK] As 7 imagens locais e as 7 URLs do GitHub Pages estão 100% online!")
    else:
        print(
            "\n[AVISO] O GitHub Pages pode levar de 1 a 2 minutos após a ativação para publicar as imagens."
        )

    print("\n----------------------------------------------------------------------------")
    print("Agora vamos configurar a conexão com o Instagram (localmente no seu PC):")
    print(f"Caso ainda não esteja com o Graph API Explorer aberto, acesse:\n  {EXPLORER_URL}")
    print("Permissões necessárias: instagram_basic, instagram_content_publish, pages_show_list, pages_read_engagement")
    print("----------------------------------------------------------------------------\n")

    token = input("Cole aqui no terminal o Access Token gerado na Meta (ou Enter para sair): ").strip()
    if not token:
        print("Operação cancelada pelo usuário.")
        return 0

    try:
        ig_id, ig_username, best_token = discover_instagram_account(token)
    except Exception as exc:
        print(f"\n[ERRO] {exc}")
        return 1

    env_content = (
        f"META_ACCESS_TOKEN={best_token}\n"
        f"META_IG_USER_ID={ig_id}\n"
        f"IMAGE_BASE_URL={DEFAULT_IMAGE_BASE_URL}\n"
        f"META_API_VERSION={DEFAULT_META_API_VERSION}\n"
        f"TIMEZONE=America/Sao_Paulo\n"
        f"DRY_RUN=false\n"
    )
    ENV_FILE.write_text(env_content, encoding="utf-8")
    print(f"[OK] Arquivo '.env' local criado com sucesso (protegido pelo .gitignore).")

    print("\n============================================================================")
    print("  CADASTRE ESTES 2 SECRETS NO SEU GITHUB PARA EXECUÇÃO DIÁRIA EM NUVEM:")
    print(f"  Página: {SECRETS_URL}")
    print("----------------------------------------------------------------------------")
    print(f"  1) Nome:  META_IG_USER_ID")
    print(f"     Valor: {ig_id}")
    print("----------------------------------------------------------------------------")
    print(f"  2) Nome:  META_ACCESS_TOKEN")
    print(f"     Valor: (use o token gerado / salvo no seu arquivo .env local)")
    print("============================================================================\n")

    try:
        webbrowser.open(SECRETS_URL)
    except Exception:
        pass

    print("Executando validação completa (Imagens Locais + GitHub Pages + Autenticação Meta)...")
    return run_main(["--verify-setup"])


if __name__ == "__main__":
    sys.exit(main())

