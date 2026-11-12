# Point Perucaba Stories — Automação de Instagram Stories

Sistema automatizado, gratuito (orçamento **R$ 0,00**) e *serverless* para publicação diária de Instagram Stories do estabelecimento **Point Perucaba**, utilizando **Python**, **GitHub Actions**, **GitHub Pages** e a **Instagram Graph API (Content Publishing API)** oficial da Meta.

---

## 1. Objetivo do Projeto

Publicar automaticamente, todos os dias às **08h00** (horário de Brasília — `America/Sao_Paulo`), um Instagram Story com a arte correspondente ao dia da semana, repetindo o calendário semanal indefinidamente sem intervenção manual e sem depender do computador do proprietário ligado.

---

## 2. Arquitetura

O sistema é dividido em módulos desacoplados e testáveis:

- **Agendamento (`.github/workflows/daily-story.yml`):** Disparo diário via `cron` (`11:00 UTC` = `08:00 America/Sao_Paulo`) e disparo manual via `workflow_dispatch` com suporte a modo de simulação (`dry_run`).
- **Fuso Horário e Calendário (`src/scheduler.py`):** Resolve a data e o dia da semana estritamente no fuso `America/Sao_Paulo` via `zoneinfo` (nunca utiliza UTC puro para decidir o dia).
- **Seleção de Imagem (`src/image_selector.py`):** Mapeia o dia da semana para o arquivo correspondente em `assets/stories/` e gera a URL pública com *cache-busting* diário (`?v=YYYYMMDD`).
- **Validação de Mídia (`src/image_validator.py`):** Verifica existência local, tamanho (> 0 bytes e ≤ 8 MB), cabeçalho binário JPEG real via `Pillow` e acessibilidade HTTP pública (`status 200`, `Content-Type: image/jpeg`).
- **Controle de Duplicidade (`src/publication_log.py`):** Mantém registro atômico em `data/publication_history.json` versionado no próprio repositório para impedir publicações duplicadas na mesma data.
- **Cliente Meta Graph API (`src/meta_client.py`):** Implementa o fluxo oficial de 2 etapas (`POST /{ig-user-id}/media` com `media_type=STORIES` + verificação de status `FINISHED` + `POST /{ig-user-id}/media_publish`) e mascaramento automático de tokens.
- **Orquestrador e CLI (`src/publisher.py` e `src/main.py`):** Coordena todo o fluxo de execução e tratamento de erros.

---

## 3. Tecnologias Utilizadas

- **Python 3.12+** (`zoneinfo`, `dataclasses`, `logging`, `pathlib`)
- **Requests (`2.32.3`)** — Comunicação HTTP com a Meta Graph API e validação de URLs públicas
- **Pillow (`11.0.0`)** — Validação da integridade e formato binário JPEG das artes
- **Pytest (`8.3.4`)** — Suíte de testes unitários automatizados
- **GitHub Actions** — Execução agendada gratuita em nuvem
- **GitHub Pages** — Hospedagem HTTPS pública e gratuita das 7 artes semanais

---

## 4. Como Funciona o Calendário Semanal

O mapeamento entre o dia da semana (em `America/Sao_Paulo`) e o arquivo em `assets/stories/` é fixo e recorrente:

| Dia da Semana | Arquivo Padrão (`assets/stories/`) | Nome Descritivo Atual Suportado |
|---|---|---|
| Segunda-feira | `segunda.jpg` | `Segunda — Bebida favorita.jpg` |
| Terça-feira | `terca.jpg` | `Terça — Refresque-se.jpg` |
| Quarta-feira | `quarta.jpg` | `Quarta — Pausa e energia.jpg` |
| Quinta-feira | `quinta.jpg` | `Quinta — Prepare o encontro.jpg` |
| Sexta-feira | `sexta.jpg` | `Sexta — Sextou.jpg` |
| Sábado | `sabado.jpg` | `Sabado — Churrasco e bebida gelada (2).jpg` |
| Domingo | `domingo.jpg` | `Domingo — Churrasco e bebida gelada.jpg` |

---

## 5. Como Adicionar ou Substituir Imagens

Para trocar a arte de qualquer dia da semana **sem alterar nenhuma linha de código**:

1. Exporte a nova arte em formato **JPEG real (`.jpg`)** — **Atenção:** a API da Meta **não aceita PNG ou WebP** diretamente (caso você coloque um arquivo com nome correspondente ao dia, o sistema também valida o cabeçalho binário JPEG via `Pillow`).
2. Recomendação de dimensões para Stories: **1080 x 1920 px** ou **1414 x 2000 px**, tamanho máximo de **8 MB**.
3. Salve o arquivo dentro da pasta `assets/stories/` usando o nome padrão do dia (`segunda.jpg`, `terca.jpg`, `quarta.jpg`, `quinta.jpg`, `sexta.jpg`, `sabado.jpg` ou `domingo.jpg`) ou sobrescrevendo o arquivo correspondente daquele dia.
4. Valide localmente antes de subir (opcional):
   ```powershell
   python -m src.main --verify-setup --skip-remote-url-check
   ```
5. Faça **commit e push** para a branch `main` (via terminal Git ou diretamente pela interface web do GitHub clicando em **Add file > Upload files** dentro de `assets/stories/`). O sistema inclui automaticamente o parâmetro `?v=YYYYMMDD` na URL para evitar cache antigo da CDN.

---

## 6. Como Configurar o GitHub Pages

A Meta Graph API exige que a imagem esteja acessível em uma URL pública HTTPS no momento da publicação. O **GitHub Pages** fornece isso gratuitamente:

1. Certifique-se de que o repositório no GitHub é **Public** (nenhuma senha ou token fica no código).
2. No repositório do GitHub, acesse **Settings** (no topo) > **Pages** (no menu lateral esquerdo).
3. Em **Build and deployment > Source**, selecione **Deploy from a branch**.
4. Em **Branch**, selecione `main` e a pasta `/ (root)`, depois clique em **Save**.
5. Aguarde cerca de 1 a 2 minutos. O GitHub exibirá a URL pública do seu site no formato:
   `https://<seu-usuario>.github.io/<nome-do-repositorio>/`
6. A URL base das suas imagens (`IMAGE_BASE_URL`) será:
   `https://<seu-usuario>.github.io/<nome-do-repositorio>/assets/stories`

---

## 7. Como Configurar os Secrets no GitHub

Nunca coloque credenciais no código. Cadastre-as no cofre seguro do GitHub:

1. No repositório do GitHub, acesse **Settings > Secrets and variables > Actions**.
2. Na aba **Secrets**, clique em **New repository secret** e crie:
   - **`META_ACCESS_TOKEN`**: Token de acesso da Meta (veja seções 8 e 10 abaixo).
   - **`META_IG_USER_ID`**: ID numérico da conta Instagram Business do Point Perucaba (ex.: `17841405309211844`).
   - **`IMAGE_BASE_URL`**: `https://<seu-usuario>.github.io/<nome-do-repositorio>/assets/stories` (também pode ser cadastrado na aba **Variables**).

---

## 8. Como Configurar o Aplicativo na Meta

1. Certifique-se de que a conta do Instagram do **Point Perucaba** é uma conta **Comercial (Business)** e está vinculada a uma **Página do Facebook** administrada por você.
2. Acesse [Meta for Developers](https://developers.facebook.com/) e clique em **Meus Aplicativos > Criar Aplicativo**.
3. Escolha **Outro > Avançar** e selecione o tipo **Empresa (Business)**.
4. Dê um nome ao App (ex.: `Point Perucaba Stories Automacao`), associe ao seu Portfólio Empresarial (opcional, mas recomendado) e crie o aplicativo.
5. No painel do aplicativo, adicione o produto **Instagram Graph API** (ou **Facebook Login for Business**).

---

## 9. Como Obter o Instagram Business Account ID (`META_IG_USER_ID`)

1. Acesse o [Graph API Explorer](https://developers.facebook.com/tools/explorer/).
2. No canto superior direito, selecione o seu **Aplicativo Meta** recém-criado.
3. Em **Permissions (Permissões)**, adicione:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_show_list`
   - `pages_read_engagement`
4. Clique em **Generate Access Token** e autorize a Página do Facebook e a conta do Instagram do Point Perucaba.
5. Na barra de consulta (`GET`), digite:
   `me/accounts?fields=id,name,instagram_business_account`
6. No JSON de resposta, localize a Página do Point Perucaba e copie o valor de `instagram_business_account.id`. Esse número é o seu **`META_IG_USER_ID`**.

---

## 10. Como Configurar o Token de Acesso (`META_ACCESS_TOKEN`)

Tokens gerados diretamente no botão padrão do Graph API Explorer duram apenas **1 hora**. Para que a automação funcione continuamente:

1. Com o token de curta duração gerado no passo anterior, acesse a [Ferramenta de Depuração de Token (Access Token Debugger)](https://developers.facebook.com/tools/debug/accesstoken/).
2. Clique em **Clique aqui para ver mais informações** no seu token e role até o final da página.
3. Clique no botão **Estender token de acesso (Extend Access Token)**.
4. Isso gerará um **Token de Longa Duração (60 dias)** ou, se você consultar novamente `GET /me/accounts?fields=name,access_token,instagram_business_account` usando esse token de 60 dias, o campo `access_token` da Página retornado terá **validade indeterminada (não expira por tempo)**.
5. Copie o token obtido e salve-o no GitHub Secret **`META_ACCESS_TOKEN`**.

---

## 11. Como Executar Manualmente (Simulação e Produção)

### Pelo GitHub Actions (Interface Web)
1. Acesse a aba **Actions** no seu repositório do GitHub.
2. No menu lateral esquerdo, clique em **Publicação Diária de Story — Point Perucaba**.
3. Clique no botão **Run workflow** (à direita).
4. Escolha a opção **`dry_run`**:
   - **`true` (Simulação - Padrão):** Valida o dia da semana, a imagem local, a URL remota e os testes, **sem publicar nada no Instagram**.
   - **`false` (Produção):** Executa a publicação real do Story do dia no Instagram.

### Localmente via Terminal
```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Executar suíte de testes unitários (compatível com unittest e pytest)
python -m unittest discover -s tests -v
# ou: pytest -v

# 3. Diagnóstico completo das 7 imagens locais (sem chamar URLs externas)
python -m src.main --verify-setup --skip-remote-url-check

# 4. Diagnóstico completo incluindo URLs públicas do GitHub Pages e Autenticação Meta (sem publicar)
python -m src.main --verify-setup

# 5. Executar em modo simulação do dia atual (offline, sem chamar a Meta)
python -m src.main --dry-run --skip-remote-url-check
```

---

## 12. Como Verificar o Histórico de Publicações

Existem duas formas complementares de auditoria:

1. **Arquivo de Controle no Repositório (`data/publication_history.json`):** Contém o registro estruturado de cada data publicada (`date`, `weekday`, `image_name`, `container_id`, `media_id`, `executed_at` e `status`).
2. **Aba Actions do GitHub:** Exibe o histórico completo de todas as execuções diárias com os logs detalhados de cada etapa.

---

## 13. Como Corrigir Erros Comuns

| Código / Mensagem no Log | Causa Provável | Como Resolver |
|---|---|---|
| `ERRO DE VALIDAÇÃO DE IMAGEM: Formato não suportado 'PNG'` | Um arquivo PNG foi renomeado para `.jpg` | Exporte a imagem como JPEG real (`.jpg`) no editor de imagem e substitua em `assets/stories/`. |
| `A URL pública da imagem retornou HTTP 404` | GitHub Pages desativado ou `IMAGE_BASE_URL` incorreta | Verifique **Settings > Pages** e confirme se `IMAGE_BASE_URL` aponta para `.../assets/stories`. |
| `ERRO DE AUTENTICAÇÃO NA META (code=190)` | Token expirado ou senha do Facebook alterada | Gere um novo token conforme as seções 10 e 14 e atualize o Secret `META_ACCESS_TOKEN`. |
| `SKIPPED_DUPLICATE` | O Story de hoje já foi publicado anteriormente | Comportamento normal de segurança para evitar Stories repetidos no mesmo dia. |

---

## 14. Como Renovar Credenciais

Caso utilize um Token de Usuário de Longa Duração (validade de 60 dias) ou caso altere a senha do Facebook:

1. Acesse o [Graph API Explorer](https://developers.facebook.com/tools/explorer/).
2. Selecione o aplicativo da Meta e clique em **Generate Access Token** (mantendo as permissões `instagram_basic` e `instagram_content_publish`).
3. Abra o [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/), insira o token e clique em **Extend Access Token** no rodapé.
4. No GitHub, vá em **Settings > Secrets and variables > Actions**, edite o secret **`META_ACCESS_TOKEN`** e cole o novo token.

---

## 15. Limitações do Agendamento do GitHub Actions e Consistência

1. **Atraso na Fila de Agendamento (`cron`):** O GitHub Actions opera em fila compartilhada sem garantia de minuto exato. O disparo configurado para `11:00 UTC` (`08:00 America/Sao_Paulo`) pode iniciar entre `08:00` e `08:25`. Como o sistema utiliza `zoneinfo("America/Sao_Paulo")`, o atraso de minutos nunca afeta a seleção correta do dia da semana.
2. **Regra de Inatividade de 60 Dias do GitHub:** Repositórios públicos sem commits por 60 dias têm o `cron` suspenso pelo GitHub. Nossa arquitetura resolve isso automaticamente porque cada publicação diária faz um commit automático no arquivo `data/publication_history.json`, mantendo o repositório sempre ativo.
3. **Limitação de Consistência em Falha de Commit Pós-Publicação:** Se a chamada `media_publish` publicar o Story na Meta com sucesso, mas os servidores do GitHub sofrerem queda antes do passo de `git push` do `data/publication_history.json`, o registro não estaria salvo em uma reexecução manual no mesmo dia. Caso uma execução falhe especificamente no último passo (`Persistir registro de controle de duplicidade`), verifique no aplicativo do Instagram se o Story já entrou no ar antes de disparar uma nova execução manual.

---

## 16. Checklist de Implantação em Produção

- [ ] **1. Imagens Locais Validadas:** As 7 artes semanais estão em `assets/stories/` em formato JPEG real (≤ 8 MB) e passam em `python -m src.main --verify-setup --skip-remote-url-check`.
- [ ] **2. Testes Unitários Aprovados:** `python -m unittest discover -s tests -v` executa os 18 testes com status `OK`.
- [ ] **3. Repositório no GitHub:** Código e pasta `assets/stories/` enviados para a branch `main` de um repositório Público.
- [ ] **4. GitHub Pages Ativo:** Configurado em **Settings > Pages** (`Deploy from a branch: main / root`) e respondendo via HTTPS.
- [ ] **5. Conta Instagram Vinculada:** Conta Instagram Business do Point Perucaba conectada à Página do Facebook.
- [ ] **6. App Meta Configurado:** Aplicativo criado em `developers.facebook.com` com permissões `instagram_basic`, `instagram_content_publish`, `pages_show_list` e `pages_read_engagement`.
- [ ] **7. Secrets Configurados no GitHub (`Settings > Secrets and variables > Actions`):**
  - [ ] `META_ACCESS_TOKEN` (Token de longa duração / Página)
  - [ ] `META_IG_USER_ID` (ID numérico da conta Instagram Business)
  - [ ] `IMAGE_BASE_URL` (`https://<seu-usuario>.github.io/<repo>/assets/stories`)
- [ ] **8. Simulação no GitHub Actions Concluída:** Execução manual (`Run workflow` com `dry_run = true`) finalizada com sucesso (verde).
- [ ] **9. Primeira Publicação Real Autorizada:** Execução manual (`Run workflow` com `dry_run = false`) concluída com Story publicado no Instagram e registro salvo em `data/publication_history.json`.


